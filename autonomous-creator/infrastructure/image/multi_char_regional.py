# -*- coding: utf-8 -*-
"""
MultiCharRegionalGenerator - Regional Cross-Attention + ControlNet

다중 인물 이미지 생성기. UNet의 cross-attention 레이어에 영역 마스크를 적용하여
각 캐릭터의 프롬프트가 지정된 영역에만 영향을 미치도록 제어합니다.

3축 구조:
  [텍스트 제어] → Regional Cross-Attention (attention 단계에서 분리)
  [구조 제어] → ControlNet OpenPose (위치/포즈 강제)
  [아이덴티티] → IP-Adapter / LoRA (선택)

RTX 3060 6GB VRAM 최적화:
  - mid_block + up_blocks 일부만 hook (down block은 건드리지 않음)
  - attention_slicing + CPU offload
  - ControlNet low strength + guess_mode
"""
import torch
import torch.nn.functional as F
import logging
import time
import numpy as np
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from PIL import Image

logger = logging.getLogger(__name__)

# ================================================================== #
#  Regional Attention Processor (핵심)
# ================================================================== #


class RegionalAttnProcessor:
    """
    Cross-attention 레이어에 영역 마스크를 적용하는 커스텀 프로세서.

    attn_probs 계산 후, 각 영역의 토큰 범위에 대해 공간 마스크를 곱하여
    해당 영역의 프롬프트가 지정된 위치에만 attention 하도록 제한합니다.

    attn_probs shape: (batch, heads, spatial_len, token_len)
    - spatial_len: feature map의 픽셀 수 (H*W)
    - token_len: 프롬프트 토큰 수
    """

    def __init__(self, region_masks: torch.Tensor, token_ranges: List[Tuple[int, int]]):
        """
        Args:
            region_masks: (num_regions, 1, orig_H, orig_W) - latent 기준 공간 마스크
            token_ranges: [(start, end), ...] - 각 영역의 토큰 인덱스 범위
        """
        self.region_masks = region_masks  # (num_regions, 1, orig_H, orig_W)
        self.token_ranges = token_ranges
        self._cached_hw = None  # (H, W) 캐시
        self._cached_masks = None  # (num_regions, H*W) 캐시

    def _get_masks_for_spatial(self, spatial_len: int, device, dtype) -> torch.Tensor:
        """
        현재 UNet feature map 해상도에 맞게 마스크 리사이즈 + flatten.

        spatial_len이 같으면 캐시 재사용. 다르면 2D bilinear로 리사이즈 후 flatten.
        Returns: (num_regions, spatial_len) 텐서
        """
        # 원본 마스크 해상도에서 spatial_len 유추 시도
        orig_h, orig_w = self.region_masks.shape[2], self.region_masks.shape[3]

        # 캐시 hit (동일 spatial 크기)
        if self._cached_masks is not None and self._cached_masks.shape[1] == spatial_len:
            return self._cached_masks.to(device=device, dtype=dtype)

        # 2D bilinear 보간으로 각 마스크 리사이즈
        # 가능한 (H, W) 조합 찾기 (H*W ≈ spatial_len, 비율 유지)
        # UNet feature map은 원본 latent의 (H, W) = (lat_h, lat_w) 기준
        # mid_block: (lat_h, lat_w), up_blocks: (lat_h*2^n, lat_w*2^n) 등
        ratio = orig_h / orig_w if orig_w > 0 else 1.0
        # spatial_len = new_h * new_w, new_h/new_w ≈ ratio
        new_w = int((spatial_len / ratio) ** 0.5)
        new_h = spatial_len // new_w if new_w > 0 else spatial_len

        # 정확한 면적이 아니면 가장 가까운 근사치 사용
        if new_h * new_w != spatial_len:
            # 정사각형 가정
            import math
            sq = int(math.sqrt(spatial_len))
            new_h, new_w = sq, sq
            if new_h * new_w != spatial_len:
                # 가장 가까운 인수 분해
                for h in range(sq, 0, -1):
                    if spatial_len % h == 0:
                        new_h, new_w = h, spatial_len // h
                        break

        resized_masks = []
        for i in range(self.region_masks.shape[0]):
            m = self.region_masks[i : i + 1]  # (1, 1, orig_H, orig_W)
            m_resized = F.interpolate(
                m.float(), size=(new_h, new_w), mode="bilinear", align_corners=False
            )
            resized_masks.append(m_resized.reshape(1, -1))  # (1, spatial_len)

        result = torch.cat(resized_masks, dim=0)  # (num_regions, spatial_len)

        # 길이가 정확히 맞지 않으면 pad/trim
        if result.shape[1] < spatial_len:
            pad = torch.zeros(result.shape[0], spatial_len - result.shape[1])
            result = torch.cat([result, pad], dim=1)
        elif result.shape[1] > spatial_len:
            result = result[:, :spatial_len]

        self._cached_masks = result
        return result.to(device=device, dtype=dtype)

    def __call__(self, attn, hidden_states, encoder_hidden_states=None, **kwargs):
        """
        Cross-attention forward with regional masking.

        SDXL의 Attention 모듈에서 호출됨.
        """
        batch_size, spatial_len, _ = hidden_states.shape

        # Query from hidden_states (spatial features)
        query = attn.to_q(hidden_states)

        # Key, Value from encoder_hidden_states (prompt embeddings)
        if encoder_hidden_states is None:
            encoder_hidden_states = hidden_states
        key = attn.to_k(encoder_hidden_states)
        value = attn.to_v(encoder_hidden_states)

        # Multi-head reshape
        inner_dim = key.shape[-1]
        head_dim = inner_dim // attn.heads

        query = query.view(batch_size, -1, attn.heads, head_dim).transpose(1, 2)
        key = key.view(batch_size, -1, attn.heads, head_dim).transpose(1, 2)
        value = value.view(batch_size, -1, attn.heads, head_dim).transpose(1, 2)

        # Attention scores: (batch, heads, spatial_len, token_len)
        attn_scores = torch.matmul(query, key.transpose(-1, -2)) * attn.scale

        # ============================================================ #
        #  Regional masking: 각 영역의 토큰에만 attention 허용
        # ============================================================ #
        # 마스크를 softmax 전에 적용 (logits 단계에서 -inf 마스킹)
        token_len = attn_scores.shape[3]
        masks_2d = self._get_masks_for_spatial(
            spatial_len, attn_scores.device, attn_scores.dtype
        )  # (num_regions, spatial_len)

        for region_idx, (tok_start, tok_end) in enumerate(self.token_ranges):
            if tok_start >= token_len:
                continue
            actual_end = min(tok_end, token_len)

            # 이 영역의 공간 마스크: (spatial_len,)
            region_mask = masks_2d[region_idx]

            # 마스크가 0인 위치의 attention을 -inf로 설정
            # (spatial_len,) → (1, 1, spatial_len, 1) for broadcasting
            mask_val = region_mask.unsqueeze(0).unsqueeze(0).unsqueeze(-1)

            # 0인 곳은 -inf (해당 토큰 영역에 attention 하지 않음)
            block_mask = (1.0 - mask_val).bool().expand(
                -1, -1, -1, actual_end - tok_start
            )
            attn_scores[:, :, :, tok_start:actual_end] = (
                attn_scores[:, :, :, tok_start:actual_end].masked_fill(
                    block_mask, float("-inf")
                )
            )

        # Softmax (마스킹 후)
        attn_probs = attn_scores.softmax(dim=-1)
        # NaN 처리 (모든 값이 -inf인 경우)
        attn_probs = torch.nan_to_num(attn_probs, nan=0.0)

        # Value aggregation
        hidden_states = torch.matmul(attn_probs, value)
        hidden_states = hidden_states.transpose(1, 2).reshape(
            batch_size, -1, attn.heads * head_dim
        )

        # Output projection
        hidden_states = attn.to_out[0](hidden_states)
        if len(attn.to_out) > 1:
            hidden_states = attn.to_out[1](hidden_states)

        return hidden_states


# ================================================================== #
#  MultiCharRegionalGenerator (메인)
# ================================================================== #


class MultiCharRegionalGenerator:
    """
    Regional Cross-Attention + ControlNet 기반 다중 인물 이미지 생성기.

    3축 구조:
    1. Regional Cross-Attention: attention 단계에서 프롬프트 분리
    2. ControlNet OpenPose: 인물 위치/포즈 강제
    3. IP-Adapter/LoRA: 아이덴티티 유지 (선택)
    """

    # Regional attention을 적용할 타겟 레이어
    # mid_block: 전역 구조, up_blocks.1: 중간 해상도 디테일
    TARGET_LAYER_PATTERNS = [
        "mid_block.attentions.0.transformer_blocks",
        "up_blocks.1.attentions",
    ]

    def __init__(self, sdxl_generator):
        """
        Args:
            sdxl_generator: SDXLGenerator 인스턴스
        """
        self.gen = sdxl_generator
        self._original_processors = {}  # 복원용 (key = (pipe_id, module_name))

    async def generate_multi_char(
        self,
        scene,
        characters: list,
        output_path: str,
        seed: int = 12345,
        steps: int = 25,
        cfg_scale: float = 7.5,
        width: int = 576,
        height: int = 1024,
        controlnet_scale: float = 0.4,
        use_controlnet: bool = True,
        character_ref_images: dict = None,
    ) -> str:
        """
        Regional Cross-Attention 기반 다중 인물 이미지 생성.
        """
        start_time = time.time()
        pipe = self.gen.pipeline

        if pipe is None:
            raise RuntimeError("SDXL 파이프라인이 로드되지 않았습니다.")

        device = self.gen.device
        dtype = self.gen.dtype
        num_chars = len(scene.characters)

        if num_chars < 2:
            raise ValueError(f"2인물 이상 필요. 현재: {num_chars}")

        logger.info(
            f"[Regional] 시작: scene={scene.id}, chars={num_chars}, "
            f"size={width}x{height}, steps={steps}, seed={seed}"
        )

        # ------------------------------------------------------------------
        # 1. 캐릭터별 프롬프트 구성
        # ------------------------------------------------------------------
        char_prompts = self._build_character_prompts(scene, characters)
        negative_prompt = self._build_negative_prompt()

        logger.info(f"[Regional] 프롬프트 수: {len(char_prompts)}")
        for cp in char_prompts:
            logger.info(f"[Regional]   {cp['id']} ({cp['region']}): {cp['prompt'][:80]}...")

        # ------------------------------------------------------------------
        # 2. 개별 인코딩 → 토큰 범위 추적
        # ------------------------------------------------------------------
        combined_embeds, token_ranges, pooled_embeds = (
            self._encode_region_prompts(char_prompts, negative_prompt, device)
        )

        logger.info(f"[Regional] 토큰 범위: {token_ranges}")
        logger.info(
            f"[Regional] combined prompt_embeds: {combined_embeds['prompt_embeds'].shape}"
        )

        # ------------------------------------------------------------------
        # 3. 영역 마스크 생성 (latent 기준)
        # ------------------------------------------------------------------
        lat_h, lat_w = height // 8, width // 8
        region_masks = self._create_region_masks(
            num_chars=len(char_prompts),
            lat_h=lat_h,
            lat_w=lat_w,
        )
        # device/dtype 맞추기
        region_masks = [m.to(device=device) for m in region_masks]
        region_masks_tensor = torch.cat(region_masks, dim=0)  # (num_regions, 1, H, W)

        logger.info(
            f"[Regional] 마스크 생성: {len(region_masks)}개, "
            f"latent 크기: {lat_h}x{lat_w}"
        )

        # ------------------------------------------------------------------
        # 4. Regional Attention Processor 설치
        # ------------------------------------------------------------------
        self._install_regional_processors(
            pipe, region_masks_tensor, token_ranges
        )

        # ------------------------------------------------------------------
        # 5. ControlNet 준비 (필요시 로드)
        # ------------------------------------------------------------------
        pose_image = None
        active_pipe = pipe  # 기본: standard SDXL

        if use_controlnet:
            pose_image = self._generate_pose_image(
                num_chars, width, height, char_prompts
            )
            if pose_image is not None:
                # ControlNet 파이프라인 로드 (SDXLGenerator 내장)
                logger.info("[Regional] ControlNet 로드 중...")
                if self.gen._load_controlnet():
                    active_pipe = self.gen._controlnet_pipeline
                    logger.info("[Regional] ControlNet 파이프라인 사용")
                else:
                    logger.warning("[Regional] ControlNet 로드 실패, standard 파이프라인 사용")
            else:
                logger.info("[Regional] Pose 이미지 없음, ControlNet 없이 진행")

        # Regional processor를 active_pipe의 UNet에 설치
        if active_pipe is not pipe:
            # ControlNet 파이프라인으로 전환 → processor 재설치
            self._install_regional_processors(
                active_pipe, region_masks_tensor, token_ranges
            )

        # ------------------------------------------------------------------
        # 6. 파이프라인 실행 (attention_slicing 활용)
        # ------------------------------------------------------------------
        try:
            active_pipe.enable_attention_slicing()

            gen_kwargs = {
                "prompt_embeds": combined_embeds["prompt_embeds"],
                "negative_prompt_embeds": combined_embeds["negative_prompt_embeds"],
                "pooled_prompt_embeds": pooled_embeds["pooled_prompt_embeds"],
                "negative_pooled_prompt_embeds": pooled_embeds["negative_pooled_prompt_embeds"],
                "width": width,
                "height": height,
                "num_inference_steps": steps,
                "guidance_scale": cfg_scale,
                "generator": torch.Generator(device="cpu").manual_seed(seed),
                "output_type": "pil",
            }

            # ControlNet 입력
            if pose_image is not None and active_pipe is not pipe:
                gen_kwargs["image"] = pose_image
                gen_kwargs["controlnet_conditioning_scale"] = controlnet_scale
                gen_kwargs["guess_mode"] = True

            # IP-Adapter: ControlNet 파이프라인에는 IP-Adapter가 없으므로
            # standard 파이프라인일 때만 dummy embeds 전달
            if active_pipe is pipe and self.gen._ip_adapter_loaded:
                dummy = self.gen._create_dummy_ip_adapter_embeds()
                if dummy is not None:
                    pipe.set_ip_adapter_scale(0.0)
                    gen_kwargs["ip_adapter_image_embeds"] = dummy

            result = active_pipe(**gen_kwargs)
            image = result.images[0]

        except Exception as e:
            logger.error(f"[Regional] 파이프라인 실행 실패: {e}")
            raise
        finally:
            # Regional processors 복원 (두 파이프라인 모두)
            self._restore_processors(active_pipe)
            if active_pipe is not pipe:
                self._restore_processors(pipe)

        # ------------------------------------------------------------------
        # 7. 저장
        # ------------------------------------------------------------------
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, quality=95)

        elapsed = time.time() - start_time
        logger.info(f"[Regional] 완료: {output_path} ({elapsed:.1f}s)")

        return output_path

    # ================================================================== #
    #  프롬프트 구성
    # ================================================================== #

    def _build_character_prompts(self, scene, characters: list) -> List[Dict]:
        """캐릭터별 개별 프롬프트 구성"""
        char_map = {c.id: c for c in characters}

        # 공통 요소
        common_parts = []
        if scene.location:
            common_parts.append(f"in {scene.location}")
        mood_token = self._mood_to_prompt(scene.mood)
        if mood_token:
            common_parts.append(mood_token)
        camera_token = self._camera_to_prompt(scene.camera)
        if camera_token:
            common_parts.append(camera_token)
        common_suffix = ", ".join(common_parts)

        style_suffix = (
            "Disney 3D style, Pixar quality, soft lighting, "
            "cinematic, ultra detailed, 4k, masterpiece, "
            "no text, no letters, no watermark"
        )
        trigger = "MG_ip, pixar"

        char_prompts = []
        for idx, char_id in enumerate(scene.characters):
            char_spec = char_map.get(char_id)
            if char_spec is None:
                continue

            appearance = char_spec.appearance if char_spec.appearance else ""

            parts = [trigger]
            if scene.action:
                parts.append(scene.action)
            if appearance:
                parts.append(appearance)
            if common_suffix:
                parts.append(common_suffix)
            parts.append(style_suffix)

            prompt = ", ".join(p for p in parts if p)

            region_labels = ["left", "center", "right"]
            region = region_labels[idx] if idx < len(region_labels) else f"region_{idx}"

            char_prompts.append({
                "id": char_id,
                "name": char_spec.name,
                "prompt": prompt,
                "region": region,
            })

        return char_prompts

    def _encode_region_prompts(
        self,
        char_prompts: List[Dict],
        negative_prompt: str,
        device: str,
    ) -> Tuple[Dict, List[Tuple[int, int]], Dict]:
        """
        각 영역의 프롬프트를 개별 인코딩 후 시퀀스 차원으로 연결.
        Negative prompt는 긍정 임베딩과 동일 길이로 반복하여 패딩.

        Returns:
            combined_embeds: {prompt_embeds, negative_prompt_embeds}
            token_ranges: [(start, end), ...]
            pooled_embeds: {pooled_prompt_embeds, negative_pooled_prompt_embeds}
        """
        all_prompt_embeds = []
        token_ranges = []
        current_pos = 0

        for cp in char_prompts:
            # 개별 인코딩 (청킹 사용)
            prompt_emb, _, _, _ = (
                self.gen._encode_prompt_with_chunking(
                    prompt=cp["prompt"],
                    negative_prompt=negative_prompt,
                    device=device,
                )
            )

            # 토큰 범위 기록
            seq_len = prompt_emb.shape[1]
            token_ranges.append((current_pos, current_pos + seq_len))
            current_pos += seq_len

            all_prompt_embeds.append(prompt_emb)

        # 시퀀스 차원으로 연결: (1, total_seq_len, embed_dim)
        combined_prompt = torch.cat(all_prompt_embeds, dim=1)
        total_seq_len = combined_prompt.shape[1]
        embed_dim = combined_prompt.shape[2]

        # Negative: 단일 인코딩 후 total_seq_len에 맞게 반복 패딩
        _, neg_emb, _, neg_pooled_emb = (
            self.gen._encode_prompt_with_chunking(
                prompt=char_prompts[0]["prompt"],  # dummy (실제 neg 사용)
                negative_prompt=negative_prompt,
                device=device,
            )
        )
        neg_seq_len = neg_emb.shape[1]

        # 반복하여 길이 맞추기
        if neg_seq_len < total_seq_len:
            repeats = (total_seq_len + neg_seq_len - 1) // neg_seq_len
            neg_padded = neg_emb.repeat(1, repeats, 1)[:, :total_seq_len, :]
        elif neg_seq_len > total_seq_len:
            neg_padded = neg_emb[:, :total_seq_len, :]
        else:
            neg_padded = neg_emb

        # Pooled: 첫 번째 영역의 것 사용 (SDXL global conditioning)
        _, _, pooled_emb, _ = (
            self.gen._encode_prompt_with_chunking(
                prompt=char_prompts[0]["prompt"],
                negative_prompt=negative_prompt,
                device=device,
            )
        )

        combined_embeds = {
            "prompt_embeds": combined_prompt,
            "negative_prompt_embeds": neg_padded,
        }
        pooled_embeds = {
            "pooled_prompt_embeds": pooled_emb,
            "negative_pooled_prompt_embeds": neg_pooled_emb,
        }

        logger.info(
            f"[Regional] 인코딩: pos seq_len={total_seq_len}, "
            f"neg seq_len={neg_padded.shape[1]}, ranges={token_ranges}"
        )

        return combined_embeds, token_ranges, pooled_embeds

    def _build_negative_prompt(self) -> str:
        """네거티브 프롬프트"""
        parts = [
            "blurry, deformed, bad anatomy, different person",
            "extra limbs, low quality, distorted face, watermark",
            "text, letters, words, signature, logo, font",
            "butterflies, insects, birds, flying objects",
            "extra objects, background clutter",
            "asymmetric eyes, cross-eyed, deformed eyes",
            "cropped, worst quality, normal quality, jpeg artifacts",
        ]
        return ", ".join(parts)

    # ================================================================== #
    #  영역 마스크 생성
    # ================================================================== #

    def _create_region_masks(
        self, num_chars: int, lat_h: int, lat_w: int
    ) -> List[torch.Tensor]:
        """
        영역 마스크 생성. 각 마스크는 (1, 1, lat_h, lat_w) 형태.
        마스크 합은 1.0 (모든 위치에서).
        """
        masks = []
        segment_width = lat_w / num_chars
        feather_pixels = max(1, int(segment_width * 0.15))

        for i in range(num_chars):
            mask = torch.zeros(1, 1, lat_h, lat_w)
            center = (i + 0.5) * segment_width
            left = i * segment_width
            right = (i + 1) * segment_width

            for x in range(lat_w):
                # 소속감: 이 영역 중심에 가까울수록 1.0
                if x < left:
                    dist = left - x
                    val = max(0, 1.0 - dist / feather_pixels) if feather_pixels > 0 else 0
                elif x >= right:
                    dist = x - right + 1
                    val = max(0, 1.0 - dist / feather_pixels) if feather_pixels > 0 else 0
                else:
                    # 영역 내부
                    dist_to_edge = min(x - left, right - 1 - x)
                    if dist_to_edge < feather_pixels:
                        val = 0.5 + 0.5 * (dist_to_edge / feather_pixels)
                    else:
                        val = 1.0

                mask[0, 0, :, x] = val

            masks.append(mask)

        # 정규화: 합이 1.0
        total = sum(masks)
        total = torch.where(total > 0, total, torch.ones_like(total))
        masks = [m / total for m in masks]

        return masks

    # ================================================================== #
    #  Regional Processor 설치/복원
    # ================================================================== #

    def _install_regional_processors(
        self,
        pipe,
        region_masks: torch.Tensor,
        token_ranges: List[Tuple[int, int]],
    ):
        """UNet의 cross-attention 레이어에 RegionalAttnProcessor 설치"""
        pipe_id = id(pipe)

        processor = RegionalAttnProcessor(region_masks, token_ranges)

        installed_count = 0
        for name, module in pipe.unet.named_modules():
            # attn2 = cross-attention
            if not name.endswith(".attn2"):
                continue

            # 타겟 레이어 패턴 확인
            if not any(p in name for p in self.TARGET_LAYER_PATTERNS):
                continue

            # 원래 프로세서 백업 (파이프라인별로 분리)
            key = (pipe_id, name)
            if key not in self._original_processors:
                self._original_processors[key] = module.processor

            # Regional 프로세서 설치
            module.set_processor(
                RegionalAttnProcessor(region_masks, token_ranges)
            )
            installed_count += 1

        logger.info(
            f"[Regional] 프로세서 설치: {installed_count}개 레이어 "
            f"(pipe_id={pipe_id}, 패턴: {self.TARGET_LAYER_PATTERNS})"
        )

    def _restore_processors(self, pipe):
        """원래 프로세서로 복원"""
        pipe_id = id(pipe)
        keys_to_remove = []

        for (pid, name), original_proc in self._original_processors.items():
            if pid != pipe_id:
                continue
            parts = name.split(".")
            module = pipe.unet
            for part in parts:
                if part.isdigit():
                    module = module[int(part)]
                else:
                    module = getattr(module, part)
            module.set_processor(original_proc)
            keys_to_remove.append((pid, name))

        for key in keys_to_remove:
            del self._original_processors[key]

        restored = len(keys_to_remove)
        logger.info(f"[Regional] 프로세서 복원: {restored}개 (pipe_id={pipe_id})")

    # ================================================================== #
    #  ControlNet + Pose
    # ================================================================== #

    def _generate_pose_image(
        self,
        num_chars: int,
        width: int,
        height: int,
        char_prompts: List[Dict],
    ) -> Optional[Image.Image]:
        """
        프로그래밍 방식으로 간단한 포즈 이미지 생성.

        인물 수와 위치에 맞춰 스켈레톤 형태의 포즈 이미지를 생성합니다.
        ControlNet OpenPose 입력용 (검은 배경 + 흰색 스켈레톤).
        """
        try:
            return self._draw_simple_poses(num_chars, width, height, char_prompts)
        except Exception as e:
            logger.warning(f"[Regional] Pose 이미지 생성 실패: {e}")
            return None

    def _draw_simple_poses(
        self,
        num_chars: int,
        width: int,
        height: int,
        char_prompts: List[Dict],
    ) -> Image.Image:
        """
        간단한 스틱 피규어 포즈 이미지 생성.
        OpenPose 형식 (검은 배경, 컬러 스켈레톤).
        """
        img = np.zeros((height, width, 3), dtype=np.uint8)

        segment_width = width / num_chars

        for i in range(num_chars):
            center_x = int((i + 0.5) * segment_width)
            # 세로: 인물이 화면 중앙에 위치 (머리 ~ 무릎)
            head_y = int(height * 0.12)
            shoulder_y = int(height * 0.22)
            hip_y = int(height * 0.50)
            knee_y = int(height * 0.65)
            foot_y = int(height * 0.80)

            shoulder_w = int(segment_width * 0.25)
            hip_w = int(segment_width * 0.15)

            # OpenPose 색상 (BGR for cv2 convention, but we use RGB)
            colors = [
                (255, 128, 0),   # 주황 (인물 1)
                (0, 255, 128),   # 초록 (인물 2)
                (128, 0, 255),   # 보라 (인물 3)
            ]
            color = colors[i % len(colors)]

            # 머리 (원)
            self._draw_circle(img, center_x, head_y, int(segment_width * 0.12), color)

            # 목 → 어깨
            self._draw_line(img, center_x, head_y + int(segment_width * 0.12),
                          center_x, shoulder_y, color, 3)
            # 어깨
            self._draw_line(img, center_x - shoulder_w, shoulder_y,
                          center_x + shoulder_w, shoulder_y, color, 3)
            # 어깨 → 왼팔
            self._draw_line(img, center_x - shoulder_w, shoulder_y,
                          center_x - shoulder_w - int(segment_width * 0.1), hip_y - int(height * 0.05), color, 2)
            # 어깨 → 오른팔
            self._draw_line(img, center_x + shoulder_w, shoulder_y,
                          center_x + shoulder_w + int(segment_width * 0.1), hip_y - int(height * 0.05), color, 2)
            # 몸통
            self._draw_line(img, center_x, shoulder_y, center_x, hip_y, color, 3)
            # 골반
            self._draw_line(img, center_x - hip_w, hip_y,
                          center_x + hip_w, hip_y, color, 3)
            # 왼다리
            self._draw_line(img, center_x - hip_w, hip_y,
                          center_x - hip_w, knee_y, color, 2)
            self._draw_line(img, center_x - hip_w, knee_y,
                          center_x - hip_w - int(segment_width * 0.05), foot_y, color, 2)
            # 오른다리
            self._draw_line(img, center_x + hip_w, hip_y,
                          center_x + hip_w, knee_y, color, 2)
            self._draw_line(img, center_x + hip_w, knee_y,
                          center_x + hip_w + int(segment_width * 0.05), foot_y, color, 2)

        return Image.fromarray(img)

    @staticmethod
    def _draw_circle(img, cx, cy, r, color, thickness=-1):
        """간단한 원 그리기 (numpy)"""
        y, x = np.ogrid[:img.shape[0], :img.shape[1]]
        mask = (x - cx) ** 2 + (y - cy) ** 2 <= r ** 2
        if thickness > 0:
            inner = (x - cx) ** 2 + (y - cy) ** 2 <= (r - thickness) ** 2
            mask = mask & ~inner
        img[mask] = color

    @staticmethod
    def _draw_line(img, x0, y0, x1, y1, color, thickness=2):
        """간단한 선 그리기 (Bresenham)"""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            # 두께 적용
            for ty in range(-thickness // 2, thickness // 2 + 1):
                for tx in range(-thickness // 2, thickness // 2 + 1):
                    ny, nx = y0 + ty, x0 + tx
                    if 0 <= ny < img.shape[0] and 0 <= nx < img.shape[1]:
                        img[ny, nx] = color
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    # ================================================================== #
    #  IP-Adapter 처리
    # ================================================================== #

    def _prepare_ip_adapter_embeds(
        self, pipe, device, character_ref_images: dict = None,
        scene_char_ids: list = None,
    ):
        """IP-Adapter 임베딩 준비

        character_ref_images가 제공되면 씬의 첫 번째 캐릭터 참조를 사용.
        없으면 기존 embeds 또는 dummy 사용.
        """
        if not self.gen._ip_adapter_loaded:
            return None

        # 기존 embeds가 있으면 우선 사용
        if self.gen._ip_adapter_embeds is not None:
            return self.gen._ip_adapter_embeds

        # 캐릭터 참조 이미지가 있으면 standard 파이프라인으로 embeds 계산
        # (ControlNet 파이프라인에는 IP-Adapter가 로드되지 않을 수 있음)
        if character_ref_images and scene_char_ids:
            for char_id in scene_char_ids:
                ref_path = character_ref_images.get(char_id)
                if ref_path and Path(ref_path).exists():
                    try:
                        from PIL import Image
                        ref_image = Image.open(ref_path).convert("RGB")
                        embeds = self.gen.pipeline.prepare_ip_adapter_image_embeds(
                            ip_adapter_image=ref_image,
                            ip_adapter_image_embeds=None,
                            device="cpu",
                            num_images_per_prompt=1,
                            do_classifier_free_guidance=True,
                        )
                        logger.info(
                            f"[Regional] IP-Adapter embeds: {char_id} 참조 사용"
                        )
                        return embeds
                    except Exception as e:
                        logger.warning(
                            f"[Regional] IP-Adapter embeds 계산 실패 ({char_id}): {e}"
                        )

        # 더미 임베딩
        dummy = self.gen._create_dummy_ip_adapter_embeds()
        if dummy is not None:
            pipe.set_ip_adapter_scale(0.0)
        return dummy

    # ================================================================== #
    #  유틸리티
    # ================================================================== #

    @staticmethod
    def _mood_to_prompt(mood: str) -> str:
        mood_map = {
            "tense": "tense atmosphere", "dark": "dark moody lighting",
            "bright": "bright cheerful lighting", "romantic": "warm romantic glow",
            "mysterious": "mysterious foggy atmosphere",
            "peaceful": "peaceful serene ambiance", "epic": "epic grand scale",
            "joyful": "vibrant joyful energy", "sad": "melancholic muted tones",
            "neutral": "", "dramatic": "dramatic high contrast lighting",
            "suspenseful": "suspenseful shadowy lighting",
            "cheerful": "bright warm cheerful tone",
            "gloomy": "gloomy desaturated atmosphere",
        }
        return mood_map.get(mood, f"{mood} atmosphere" if mood else "")

    @staticmethod
    def _camera_to_prompt(camera: str) -> str:
        camera_map = {
            "close-up": "close-up shot", "medium_shot": "medium shot",
            "wide_shot": "wide establishing shot", "extreme_closeup": "extreme close-up",
            "low_angle": "low angle shot", "high_angle": "high angle shot",
            "over_shoulder": "over the shoulder shot", "dutch_angle": "dutch angle",
            "medium": "medium shot", "wide": "wide shot",
        }
        return camera_map.get(camera, "")

    def debug_region_masks(
        self,
        num_chars: int = 2,
        output_dir: str = "output/regional_debug",
        width: int = 576,
        height: int = 1024,
    ) -> List[str]:
        """영역 마스크 시각화"""
        import numpy as np

        lat_h, lat_w = height // 8, width // 8
        masks = self._create_region_masks(num_chars, lat_h, lat_w)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        saved = []
        colors = [(255, 100, 100), (100, 255, 100), (100, 100, 255)]

        for idx, mask in enumerate(masks):
            mask_np = mask[0, 0].numpy()
            mask_img = Image.fromarray(
                (mask_np * 255).astype(np.uint8)
            ).resize((width, height), Image.BILINEAR)
            path = str(output_path / f"regional_mask_{idx}.png")
            mask_img.save(path)
            saved.append(path)

        # 오버레이
        overlay = np.zeros((height, width, 3), dtype=np.uint8)
        for idx, mask in enumerate(masks):
            mask_np = mask[0, 0].numpy()
            mask_resized = np.array(
                Image.fromarray((mask_np * 255).astype(np.uint8)).resize(
                    (width, height), Image.BILINEAR
                )
            ) / 255.0
            color = np.array(colors[idx % len(colors)])
            for c in range(3):
                overlay[:, :, c] = np.clip(
                    overlay[:, :, c].astype(float) + mask_resized * color[c],
                    0, 255,
                ).astype(np.uint8)

        path = str(output_path / "regional_overlay.png")
        Image.fromarray(overlay).save(path)
        saved.append(path)

        return saved
