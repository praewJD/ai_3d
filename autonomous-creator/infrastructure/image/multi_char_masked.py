# -*- coding: utf-8 -*-
"""
MultiCharMaskedGenerator - Method 4: Mask-Based Prompt Conditioning

다중 인물 이미지 생성기. 노이즈 제거 과정에서 각 캐릭터의 영역 마스크에 따라
개별 프롬프트 조건을 적용하여 한 번의 패스로 모든 캐릭터를 생성합니다.

접근 방식: Latent Region Blending (Denoising-time compositing)
- 각 캐릭터의 프롬프트를 별도로 인코딩합니다.
- 각 노이즈 제거 단계에서:
  1. 각 캐릭터의 임베딩으로 노이즈를 예측합니다.
  2. 영역 마스크를 사용하여 예측된 노이즈를 혼합합니다.
- 모든 캐릭터가 하나의 일관된 이미지로 함께 생성됩니다.

RTX 3060 6GB VRAM 최적화 (CPU offload 필수)
"""
import torch
import logging
import time
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from PIL import Image

logger = logging.getLogger(__name__)


class MultiCharMaskedGenerator:
    """
    Method 4: Mask-Based Prompt Conditioning

    각 캐릭터의 프롬프트를 개별적으로 인코딩하고,
    커스텀 디노이징 루프에서 영역별로 노이즈 예측을 혼합합니다.
    """

    def __init__(self, sdxl_generator):
        """
        Args:
            sdxl_generator: SDXLGenerator 인스턴스 (파이프라인이 이미 로드되어 있어야 함)
        """
        self.gen = sdxl_generator

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
        feather_strength: float = 0.15,
    ) -> str:
        """
        다중 인물 씬 이미지 생성 (Method 4: Mask-Based Prompt Conditioning)

        Args:
            scene: SceneSpec 인스턴스 (action, camera, mood, location 포함)
            characters: CharacterSpec 인스턴스 목록
            output_path: 출력 이미지 경로
            seed: 랜덤 시드
            steps: 디노이징 스텝 수
            cfg_scale: CFG 스케일
            width: 이미지 너비
            height: 이미지 높이
            feather_strength: 영역 마스크 경계 페이더 강도 (0.0~1.0)
                              높을수록 부드러운 경계 (캐릭터 간 자연스러운 전환)

        Returns:
            생성된 이미지 파일 경로
        """
        start_time = time.time()
        pipe = self.gen.pipeline

        if pipe is None:
            raise RuntimeError("SDXL 파이프라인이 로드되지 않았습니다. load_model()을 먼저 호출하세요.")

        device = self.gen.device
        dtype = self.gen.dtype
        num_chars = len(scene.characters)

        if num_chars < 2:
            raise ValueError(
                f"MultiCharMaskedGenerator는 2인물 이상 씬에서만 사용합니다. "
                f"현재 인물 수: {num_chars}"
            )

        logger.info(
            f"[Method4] 시작: scene={scene.id}, chars={num_chars}, "
            f"size={width}x{height}, steps={steps}, seed={seed}"
        )

        # ------------------------------------------------------------------
        # 1. 캐릭터별 프롬프트 구성
        # ------------------------------------------------------------------
        char_prompts = self._build_character_prompts(scene, characters)
        logger.info(f"[Method4] 캐릭터 프롬프트 수: {len(char_prompts)}")
        for cp in char_prompts:
            logger.info(f"[Method4]   {cp['id']}: {cp['prompt'][:80]}...")

        # ------------------------------------------------------------------
        # 2. 네거티브 프롬프트 구성
        # ------------------------------------------------------------------
        negative_prompt = self._build_negative_prompt()

        # ------------------------------------------------------------------
        # 3. 영역 마스크 생성 (latent 공간)
        # ------------------------------------------------------------------
        lat_h, lat_w = height // 8, width // 8
        region_masks = self._create_region_masks(
            num_chars=len(char_prompts),
            lat_h=lat_h,
            lat_w=lat_w,
            feather=feather_strength,
        )
        # 마스크를 디바이스로 이동
        region_masks = [m.to(device=device, dtype=dtype) for m in region_masks]

        logger.info(
            f"[Method4] 영역 마스크 생성: {len(region_masks)}개, "
            f"latent 크기: {lat_h}x{lat_w}"
        )

        # ------------------------------------------------------------------
        # 4. 각 캐릭터 프롬프트 개별 인코딩 (청킹 사용)
        # ------------------------------------------------------------------
        all_embeds = []
        for cp in char_prompts:
            prompt_embeds, neg_embeds, pooled_embeds, neg_pooled_embeds = (
                self.gen._encode_prompt_with_chunking(
                    prompt=cp["prompt"],
                    negative_prompt=negative_prompt,
                    device=device,
                )
            )
            all_embeds.append({
                "prompt_embeds": prompt_embeds,
                "negative_prompt_embeds": neg_embeds,
                "pooled_prompt_embeds": pooled_embeds,
                "negative_pooled_prompt_embeds": neg_pooled_embeds,
            })
            logger.info(
                f"[Method4]   {cp['id']} 인코딩 완료: "
                f"prompt_embeds shape={prompt_embeds.shape}"
            )

        # ------------------------------------------------------------------
        # 5. 커스텀 디노이징 루프 (영역별 노이즈 예측 혼합)
        # ------------------------------------------------------------------
        image = self._denoise_with_region_blending(
            pipe=pipe,
            all_embeds=all_embeds,
            region_masks=region_masks,
            seed=seed,
            steps=steps,
            cfg_scale=cfg_scale,
            width=width,
            height=height,
            device=device,
            dtype=dtype,
        )

        # ------------------------------------------------------------------
        # 6. 저장
        # ------------------------------------------------------------------
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, quality=95)

        elapsed = time.time() - start_time
        logger.info(
            f"[Method4] 완료: {output_path} ({elapsed:.1f}s)"
        )

        return output_path

    # ================================================================== #
    #  프롬프트 구성
    # ================================================================== #

    def _build_character_prompts(
        self, scene, characters: list
    ) -> List[Dict[str, str]]:
        """
        캐릭터별 개별 프롬프트 구성

        각 캐릭터의 appearance를 포함한 독립적인 프롬프트를 생성합니다.
        공통 요소(배경, 무드, 카메라)는 모든 프롬프트에 포함됩니다.

        Returns:
            [{"id": "char_1", "prompt": "...", "region": "left"}, ...]
        """
        # 캐릭터 ID → CharacterSpec 매핑
        char_map = {c.id: c for c in characters}

        # 공통 요소 추출
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

        # 스타일 + 품질 접미사
        style_suffix = (
            "Disney 3D style, Pixar quality, soft lighting, "
            "cinematic, ultra detailed, 4k, masterpiece, "
            "no text, no letters, no watermark"
        )

        # IP-Adapter LoRA 트리거 워드
        trigger = "MG_ip, pixar"

        # 캐릭터별 프롬프트
        char_prompts = []
        scene_char_ids = scene.characters

        for idx, char_id in enumerate(scene_char_ids):
            char_spec = char_map.get(char_id)
            if char_spec is None:
                logger.warning(
                    f"[Method4] 캐릭터 '{char_id}'를 찾을 수 없음, 스킵"
                )
                continue

            # 이 캐릭터의 appearance를 사용한 프롬프트 구성
            # action에서 이 캐릭터의 의상/외모 묘사를 강화
            appearance = char_spec.appearance if char_spec.appearance else ""

            # 프롬프트 구조:
            # [trigger] + [action] + [이 캐릭터 appearance] + [공통 요소] + [스타일]
            parts = [trigger]

            # action은 모든 캐릭터에 동일하게 포함 (씬의 전체 구도)
            if scene.action:
                parts.append(scene.action)

            # 이 캐릭터의 appearance 추가 (Method 4의 핵심: 각 프롬프트에 개별 appearance)
            if appearance:
                parts.append(appearance)

            if common_suffix:
                parts.append(common_suffix)
            parts.append(style_suffix)

            prompt = ", ".join(p for p in parts if p)

            # 영역 할당 (왼쪽→오른쪽 순서)
            region_labels = ["left", "center-left", "center", "center-right", "right"]
            region = region_labels[idx] if idx < len(region_labels) else f"region_{idx}"

            char_prompts.append({
                "id": char_id,
                "name": char_spec.name if char_spec else char_id,
                "prompt": prompt,
                "region": region,
            })

        return char_prompts

    def _build_negative_prompt(self) -> str:
        """네거티브 프롬프트 구성"""
        parts = [
            # 기본 품질
            "blurry, deformed, bad anatomy, different person",
            "extra limbs, low quality, distorted face, watermark",
            # 텍스트 렌더링 방지
            "text, letters, words, signature, logo, font",
            "typography, writing, caption, subtitle",
            # 배경 노이즈
            "butterflies, insects, birds, flying objects",
            "extra objects, background clutter",
            # 눈 일그러짐 방지
            "asymmetric eyes, cross-eyed, deformed eyes",
            "misaligned eyes, uneven eyes",
            # 품질
            "cropped, worst quality, normal quality, jpeg artifacts",
        ]
        # 주의: "multiple characters", "crowd", "creatures", "animals" 제외
        # 다중 인물 씬에서 인물 생성이 억제되기 때문
        return ", ".join(parts)

    # ================================================================== #
    #  영역 마스크
    # ================================================================== #

    def _create_region_masks(
        self,
        num_chars: int,
        lat_h: int,
        lat_w: int,
        feather: float = 0.15,
    ) -> List[torch.Tensor]:
        """
        latent 공간에서 영역 마스크 생성

        각 캐릭터에게 수평으로 균등하게 분할된 영역을 할당합니다.
        경계 부분은 feather 비율만큼 부드럽게 블렌딩합니다.

        Args:
            num_chars: 캐릭터 수
            lat_h: latent 높이
            lat_w: latent 너비
            feather: 경계 페이더 비율 (0.0~1.0)
                     각 영역 경계에서 인접 영역과 오버랩되는 비율

        Returns:
            마스크 리스트: [mask_0, mask_1, ...]
            각 마스크 shape: [1, 1, lat_h, lat_w], 값: 0.0~1.0
            모든 마스크의 합 = 1.0 (모든 위치에서)
        """
        masks = []

        if num_chars == 2:
            # 2인물: 좌우 분할 (50/50)
            # 왼쪽 반과 오른쪽 반, 경계에서 페이더 블렌딩
            mask_left = torch.zeros(1, 1, lat_h, lat_w)
            mask_right = torch.zeros(1, 1, lat_h, lat_w)

            # feather 영역 계산
            feather_pixels = max(1, int(lat_w * feather))

            for x in range(lat_w):
                if x < lat_w // 2 - feather_pixels:
                    # 왼쪽 영역 (완전)
                    mask_left[0, 0, :, x] = 1.0
                    mask_right[0, 0, :, x] = 0.0
                elif x < lat_w // 2 + feather_pixels:
                    # 경계 영역 (페이더 블렌딩)
                    # 왼쪽에서 오른쪽으로 갈수록 mask_left 감소, mask_right 증가
                    progress = (x - (lat_w // 2 - feather_pixels)) / (2 * feather_pixels)
                    progress = max(0.0, min(1.0, progress))
                    # 부드러운 보간 (cosine easing)
                    smooth = 0.5 * (1.0 - torch.cos(torch.tensor(progress * 3.14159)))
                    mask_left[0, 0, :, x] = 1.0 - smooth.item()
                    mask_right[0, 0, :, x] = smooth.item()
                else:
                    # 오른쪽 영역 (완전)
                    mask_left[0, 0, :, x] = 0.0
                    mask_right[0, 0, :, x] = 1.0

            masks = [mask_left, mask_right]

        elif num_chars == 3:
            # 3인물: 좌/중/우 분할 (33/34/33)
            mask_left = torch.zeros(1, 1, lat_h, lat_w)
            mask_center = torch.zeros(1, 1, lat_h, lat_w)
            mask_right = torch.zeros(1, 1, lat_h, lat_w)

            third = lat_w // 3
            feather_pixels = max(1, int(lat_w * feather * 0.5))

            for x in range(lat_w):
                if x < third - feather_pixels:
                    mask_left[0, 0, :, x] = 1.0
                elif x < third + feather_pixels:
                    progress = (x - (third - feather_pixels)) / (2 * feather_pixels)
                    progress = max(0.0, min(1.0, progress))
                    smooth = 0.5 * (1.0 - torch.cos(torch.tensor(progress * 3.14159)))
                    mask_left[0, 0, :, x] = 1.0 - smooth.item()
                    mask_center[0, 0, :, x] = smooth.item()
                elif x < 2 * third - feather_pixels:
                    mask_center[0, 0, :, x] = 1.0
                elif x < 2 * third + feather_pixels:
                    progress = (x - (2 * third - feather_pixels)) / (2 * feather_pixels)
                    progress = max(0.0, min(1.0, progress))
                    smooth = 0.5 * (1.0 - torch.cos(torch.tensor(progress * 3.14159)))
                    mask_center[0, 0, :, x] = 1.0 - smooth.item()
                    mask_right[0, 0, :, x] = smooth.item()
                else:
                    mask_right[0, 0, :, x] = 1.0

            masks = [mask_left, mask_center, mask_right]

        else:
            # 4인물 이상: 균등 분할 (벡터화된 방식)
            # 각 x 위치에 대해 소프트 할당 가중치 계산
            x_coords = torch.arange(lat_w, dtype=torch.float32)
            segment_width = lat_w / num_chars
            feather_pixels = max(1, int(segment_width * feather * 0.5))

            for i in range(num_chars):
                center = (i + 0.5) * segment_width
                # 각 x 위치와 이 영역 중심 사이의 거리
                dist = torch.abs(x_coords - center)
                # 시그모이드 기반 소프트 마스크
                half_width = segment_width / 2.0
                # 페이더가 적용된 마스크: 거리가 half_width 미만이면 1.0, 멀면 0.0
                sharpness = 1.0 / max(1.0, feather_pixels * 0.5)
                soft_mask = torch.sigmoid(sharpness * (half_width - dist))
                # [lat_w] → [1, 1, lat_h, lat_w]
                mask = soft_mask.unsqueeze(0).unsqueeze(0).expand(1, 1, lat_h, lat_w).clone()
                masks.append(mask)

            # 정규화: 모든 마스크의 합 = 1.0
            total = sum(masks)
            # 0으로 나누기 방지
            total = torch.where(total > 0, total, torch.ones_like(total))
            masks = [m / total for m in masks]

        return masks

    # ================================================================== #
    #  커스텀 디노이징 루프 (핵심)
    # ================================================================== #

    def _denoise_with_region_blending(
        self,
        pipe,
        all_embeds: List[Dict[str, torch.Tensor]],
        region_masks: List[torch.Tensor],
        seed: int,
        steps: int,
        cfg_scale: float,
        width: int,
        height: int,
        device: str,
        dtype: torch.dtype,
    ) -> Image.Image:
        """
        영역별 노이즈 예측 혼합을 사용한 커스텀 디노이징 루프

        각 디노이징 스텝에서:
        1. 각 캐릭터의 임베딩으로 노이즈를 예측합니다.
        2. CFG(Classifier-Free Guidance)를 적용합니다.
        3. 영역 마스크로 노이즈 예측을 혼합합니다.
        4. 스케줄러 스텝을 적용합니다.

        Args:
            pipe: StableDiffusionXLPipeline 인스턴스
            all_embeds: 각 캐릭터의 임베딩 dict 리스트
            region_masks: 영역 마스크 텐서 리스트
            seed: 랜덤 시드
            steps: 디노이징 스텝 수
            cfg_scale: CFG 스케일
            width: 이미지 너비
            height: 이미지 높이
            device: 장치
            dtype: 데이터 타입

        Returns:
            PIL Image
        """
        lat_h, lat_w = height // 8, width // 8
        num_chars = len(all_embeds)

        # ----------------------------------------------------------------
        # 5a. 초기 노이즈 생성
        # ----------------------------------------------------------------
        generator = torch.Generator(device="cpu").manual_seed(seed)
        latents = torch.randn(
            (1, 4, lat_h, lat_w),
            generator=generator,
            device="cpu",
            dtype=torch.float32,
        ).to(device=device, dtype=dtype)

        # 스케줄러 설정
        pipe.scheduler.set_timesteps(steps, device=device)
        timesteps = pipe.scheduler.timesteps

        # 초기 노이즈 스케일링
        latents = latents * pipe.scheduler.init_noise_sigma

        # ----------------------------------------------------------------
        # 5b. SDXL time_ids 준비
        # SDXL UNet은 added_cond_kwargs에 time_ids와 text_embeds를 필요로 함
        # time_ids: [original_h, original_w, crop_top, crop_left, target_h, target_w]
        # ----------------------------------------------------------------
        def _make_time_ids():
            return torch.tensor(
                [height, width, 0, 0, height, width],
                device=device,
                dtype=dtype,
            ).unsqueeze(0)  # [1, 6]

        # ----------------------------------------------------------------
        # 5c. IP-Adapter 임베딩 처리
        # IP-Adapter가 로드된 경우, 더미 또는 실제 임베딩을 UNet에 전달
        # ----------------------------------------------------------------
        ip_adapter_embeds = None
        ip_adapter_active = (
            self.gen._ip_adapter_loaded
            and self.gen._ip_adapter_embeds is not None
        )

        if ip_adapter_active:
            ip_adapter_embeds = self.gen._ip_adapter_embeds
            logger.info("[Method4] IP-Adapter 임베딩 사용")
        elif self.gen._ip_adapter_loaded:
            # IP-Adapter가 로드되었지만 참조 없음 → 더미로 충족
            ip_adapter_embeds = self.gen._create_dummy_ip_adapter_embeds()
            if ip_adapter_embeds is not None:
                # IP-Adapter 영향 최소화
                pipe.set_ip_adapter_scale(0.0)
                logger.info("[Method4] IP-Adapter 더미 임베딩 (scale=0.0)")

        # ----------------------------------------------------------------
        # 5d. 디노이징 루프
        # ----------------------------------------------------------------
        num_warmup_steps = len(timesteps) - steps
        logger.info(
            f"[Method4] 디노이징 시작: {len(timesteps)} 스텝, "
            f"{num_chars} 캐릭터, CFG={cfg_scale}"
        )

        with torch.no_grad():
            for i, t in enumerate(timesteps):
                step_label = f"[{i + 1}/{len(timesteps)}]"

                # 각 캐릭터 영역별로 노이즈 예측
                noise_preds_regions = []

                for char_idx, char_emb in enumerate(all_embeds):
                    # CFG: unconditional + conditional를 위해 latents 복제
                    latent_model_input = torch.cat([latents, latents])
                    latent_model_input = pipe.scheduler.scale_model_input(
                        latent_model_input, t
                    )

                    # UNet에 전달할 임베딩 준비
                    # prompt_embeds: [1, seq, 2048] → CFG를 위해 [2, seq, 2048] (neg+pos)
                    unet_prompt_embeds = torch.cat([
                        char_emb["negative_prompt_embeds"],
                        char_emb["prompt_embeds"],
                    ], dim=0)

                    # pooled: [1, 1280] → [2, 1280] (neg+pos)
                    unet_pooled = torch.cat([
                        char_emb["negative_pooled_prompt_embeds"],
                        char_emb["pooled_prompt_embeds"],
                    ], dim=0)

                    # time_ids: [1, 6] → [2, 6]
                    unet_time_ids = _make_time_ids().repeat(2, 1)

                    # added_cond_kwargs 구성
                    added_cond = {
                        "text_embeds": unet_pooled,
                        "time_ids": unet_time_ids,
                    }

                    # IP-Adapter: UNet config에 encoder_hid_dim_type='ip_image_proj'가 있으면
                    # added_cond_kwargs에 image_embeds 필수 (shape: [batch, 1, 1280])
                    if ip_adapter_embeds is not None:
                        if isinstance(ip_adapter_embeds, list) and len(ip_adapter_embeds) > 0:
                            added_cond["image_embeds"] = [ip_adapter_embeds[0]]
                        elif isinstance(ip_adapter_embeds, torch.Tensor):
                            added_cond["image_embeds"] = [ip_adapter_embeds]

                    # UNet 호출
                    unet_kwargs = {
                        "sample": latent_model_input,
                        "timestep": t,
                        "encoder_hidden_states": unet_prompt_embeds,
                        "added_cond_kwargs": added_cond,
                    }

                    try:
                        noise_pred = pipe.unet(**unet_kwargs).sample
                    except Exception as e:
                        logger.error(
                            f"{step_label} UNet 호출 실패 (char_idx={char_idx}): {e}"
                        )
                        raise

                    # CFG 적용: noise_pred = uncond + guidance * (cond - uncond)
                    noise_pred_uncond, noise_pred_cond = noise_pred.chunk(2)
                    noise_pred_cfg = noise_pred_uncond + cfg_scale * (
                        noise_pred_cond - noise_pred_uncond
                    )

                    noise_preds_regions.append(noise_pred_cfg)

                # 영역 마스크로 노이즈 예측 혼합
                blended_noise = torch.zeros_like(latents)
                for mask, pred in zip(region_masks, noise_preds_regions):
                    blended_noise = blended_noise + mask * pred

                # 스케줄러 스텝
                latents = pipe.scheduler.step(
                    blended_noise, t, latents
                ).prev_sample

                # 진행 로깅 (5스텝마다)
                if (i + 1) % 5 == 0 or i == 0 or i == len(timesteps) - 1:
                    logger.info(
                        f"{step_label} timestep={t.item():.1f}, "
                        f"latents stats: mean={latents.mean().item():.4f}, "
                        f"std={latents.std().item():.4f}"
                    )

        # ----------------------------------------------------------------
        # 5e. VAE 디코딩
        # ----------------------------------------------------------------
        logger.info("[Method4] VAE 디코딩...")

        # CPU offload 환경에서 VAE 디코딩 처리
        # fp16 VAE는 큰 latent 값에서 NaN을 발생시킬 수 있으므로
        # float32로 변환하여 안정적으로 디코딩
        vae = pipe.vae
        vae_device = next(vae.parameters()).device
        vae_dtype = next(vae.parameters()).dtype
        logger.info(
            f"[Method4] VAE 디코딩 준비: VAE={vae_device}/{vae_dtype}, "
            f"latents={latents.device}/{latents.dtype}"
        )

        # latent 스케일링
        latents_scaled = latents / vae.config.scaling_factor

        # NaN/Inf 체크
        if torch.isnan(latents_scaled).any() or torch.isinf(latents_scaled).any():
            nan_pct = torch.isnan(latents_scaled).float().mean().item() * 100
            logger.warning(
                f"[Method4] latents에 NaN/Inf 감지: NaN={nan_pct:.1f}%, 대체"
            )
            latents_scaled = torch.nan_to_num(
                latents_scaled, nan=0.0, posinf=1.0, neginf=-1.0
            )

        # VAE를 float32로 GPU에 로드 (fp16 NaN 방지)
        gpu_device = torch.device(device)
        vae_fp32 = vae.to(device=gpu_device, dtype=torch.float32)
        latents_fp32 = latents_scaled.to(device=gpu_device, dtype=torch.float32)

        # VAE 디코딩 (float32)
        with torch.no_grad():
            image_tensor = vae_fp32.decode(latents_fp32).sample

        # VAE를 다시 원래 상태로 복원 (CPU, 원래 dtype)
        pipe.vae = vae.to(device="cpu", dtype=vae_dtype)
        del vae_fp32
        torch.cuda.empty_cache()

        logger.info(
            f"[Method4] VAE 출력: mean={image_tensor.mean().item():.4f}, "
            f"std={image_tensor.std().item():.4f}, "
            f"has_nan={torch.isnan(image_tensor).any().item()}"
        )

        # 후처리: [-1, 1] → [0, 255] PIL Image
        image_tensor = image_tensor.detach().float()

        # NaN 체크 후 클리핑
        if torch.isnan(image_tensor).any():
            logger.warning("[Method4] VAE 출력에 NaN 감지, 0으로 대체")
            image_tensor = torch.nan_to_num(image_tensor, nan=0.0)

        image_tensor = image_tensor.clamp(-1.0, 1.0)
        image = pipe.image_processor.postprocess(image_tensor)[0]

        # IP-Adapter scale 복원
        if self.gen._ip_adapter_loaded and not ip_adapter_active:
            pipe.set_ip_adapter_scale(self.gen._ip_adapter_scale)

        logger.info("[Method4] VAE 디코딩 완료")

        return image

    # ================================================================== #
    #  유틸리티
    # ================================================================== #

    @staticmethod
    def _mood_to_prompt(mood: str) -> str:
        """무드 → 프롬프트 용어 변환"""
        mood_map = {
            "tense": "tense atmosphere",
            "dark": "dark moody lighting",
            "bright": "bright cheerful lighting",
            "mysterious": "mysterious foggy atmosphere",
            "peaceful": "peaceful serene ambiance",
            "epic": "epic grand scale",
            "romantic": "warm romantic glow",
            "horror": "creepy unsettling atmosphere",
            "joyful": "vibrant joyful energy",
            "sad": "melancholic muted tones",
            "neutral": "balanced natural lighting",
            "dramatic": "dramatic high contrast lighting",
            "suspenseful": "suspenseful shadowy lighting",
            "cheerful": "bright warm cheerful tone",
            "gloomy": "gloomy desaturated atmosphere",
        }
        return mood_map.get(mood, f"{mood} atmosphere" if mood and mood != "neutral" else "")

    @staticmethod
    def _camera_to_prompt(camera: str) -> str:
        """카메라 앵글 → 프롬프트 용어 변환"""
        camera_map = {
            "close-up": "close-up shot",
            "medium_shot": "medium shot",
            "wide_shot": "wide establishing shot",
            "extreme_closeup": "extreme close-up",
            "low_angle": "low angle shot",
            "high_angle": "high angle shot",
            "bird_eye": "bird's eye view",
            "over_shoulder": "over the shoulder shot",
            "dutch_angle": "dutch angle",
            "medium": "medium shot",
            "wide": "wide shot",
        }
        return camera_map.get(camera, "")

    def debug_region_masks(
        self,
        num_chars: int = 2,
        width: int = 576,
        height: int = 1024,
        output_dir: str = "output/method4_debug",
        feather: float = 0.15,
    ) -> List[str]:
        """
        영역 마스크를 시각화하여 디버그 이미지로 저장

        Args:
            num_chars: 캐릭터 수
            width: 이미지 너비
            height: 이미지 높이
            output_dir: 출력 디렉토리
            feather: 페이더 강도

        Returns:
            저장된 이미지 경로 리스트
        """
        import numpy as np

        lat_h, lat_w = height // 8, width // 8
        masks = self._create_region_masks(num_chars, lat_h, lat_w, feather)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        saved_paths = []

        # 개별 마스크 저장
        colors = [
            (255, 100, 100),  # 빨강
            (100, 255, 100),  # 초록
            (100, 100, 255),  # 파랑
            (255, 255, 100),  # 노랑
            (255, 100, 255),  # 보라
        ]

        for idx, mask in enumerate(masks):
            # 마스크를 PIL 이미지로 변환
            mask_np = mask[0, 0].numpy()  # [lat_h, lat_w]
            # latent 크기 → 이미지 크기로 업스케일
            mask_img = Image.fromarray(
                (mask_np * 255).astype(np.uint8)
            ).resize((width, height), Image.BILINEAR)

            color = colors[idx % len(colors)]
            mask_colored = Image.new("RGB", (width, height), color)
            mask_colored = Image.blend(
                Image.new("RGB", (width, height), (0, 0, 0)),
                mask_colored,
                mask_np.mean(),
            )

            path = str(output_path / f"mask_{idx}_char{idx}.png")
            mask_img.save(path)
            saved_paths.append(path)
            logger.info(f"[Method4 Debug] 마스크 저장: {path}")

        # 합성 오버레이 이미지 저장
        overlay = Image.new("RGB", (width, height), (0, 0, 0))
        for idx, mask in enumerate(masks):
            mask_np = mask[0, 0].numpy()
            mask_resized = np.array(
                Image.fromarray((mask_np * 255).astype(np.uint8)).resize(
                    (width, height), Image.BILINEAR
                )
            ) / 255.0

            color = np.array(colors[idx % len(colors)])
            overlay_array = np.array(overlay).astype(np.float32)
            for c in range(3):
                overlay_array[:, :, c] += mask_resized * color[c]
            overlay = Image.fromarray(
                np.clip(overlay_array, 0, 255).astype(np.uint8)
            )

        path = str(output_path / "mask_overlay.png")
        overlay.save(path)
        saved_paths.append(path)
        logger.info(f"[Method4 Debug] 오버레이 저장: {path}")

        return saved_paths
