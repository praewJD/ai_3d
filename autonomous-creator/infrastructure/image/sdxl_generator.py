"""
SDXL Image Generator

Stable Diffusion XL 기반 이미지 생성
v1.0: SDXL + IP-Adapter (diffusers 내장) + ControlNet OpenPose
- RTX 3060 6GB VRAM 최적화 (CPU offload 필수)
"""
import torch
import logging
from typing import Optional, List, Tuple
from pathlib import Path
from PIL import Image

from diffusers import (
    StableDiffusionXLPipeline,
    StableDiffusionXLControlNetPipeline,
    ControlNetModel,
)
from diffusers.utils import load_image

logger = logging.getLogger(__name__)

from core.domain.interfaces.image_generator import IImageGenerator
from core.domain.entities.preset import StylePreset
from config.settings import get_settings

# 배경 노이즈 제거용 공통 negative prompt
# 주의: "multiple characters", "crowd" 제외 - 다중 인물 씬에서 인물이 사라짐
# "creatures" 제외 - 사람 형태까지 억제할 수 있음
NEGATIVE_PROMPT_BG = (
    "butterflies, insects, birds, flying objects, "
    "extra objects, background clutter"
)

# SDXL 텍스트 렌더링 방지용 negative prompt
# SDXL은 텍스트 렌더링이 불가능하므로, 글씨/로고/워터마크 등이
# 깨진 형태로 나오는 것을 방지
NEGATIVE_PROMPT_TEXT = (
    "text, letters, watermark, words, signature, logo, font, "
    "typography, writing, caption, subtitle"
)


class SDXLGenerator(IImageGenerator):
    """
    Stable Diffusion XL 이미지 생성기

    - 6GB VRAM에서 실행 가능 (CPU offload 필수)
    - IP-Adapter: diffusers 내장 방식 (load_ip_adapter)
    - ControlNet: OpenPose SDXL (thibaud/controlnet-openpose-sdxl-1.0)
    - LoRA: PEFT 방식 (load_lora_weights)
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "auto"
    ):
        settings = get_settings()
        self.model_path = model_path or settings.sd_model
        self.device = self._determine_device(device)
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.low_vram = settings.sd_low_vram

        # 파이프라인 (기본 / ControlNet)
        self.pipeline: Optional[StableDiffusionXLPipeline] = None
        self._controlnet_pipeline: Optional[StableDiffusionXLControlNetPipeline] = None
        self._controlnet: Optional[ControlNetModel] = None
        self._is_loaded = False

        # IP-Adapter 상태 (Face Authority: 얼굴 = IP-Adapter 단일 소스)
        self._ip_adapter_enabled = settings.ip_adapter_enabled
        self._ip_adapter_loaded = False
        # Face Authority: 기본 scale 0.8 (얼굴 결정권 강화)
        # 주의: scale이 너무 높으면(0.9+) 눈동자 일그러짐/비대칭 발생 가능
        # 권장 범위: 0.7 ~ 0.85 (0.8 기본값)
        self._ip_adapter_scale: float = getattr(settings, "ip_adapter_strength", 0.8)
        if self._ip_adapter_scale < 0.8:
            self._ip_adapter_scale = 0.8  # Face Authority 최소 보장
        self._ip_adapter_embeds = None
        self._reference_image: Optional[Image.Image] = None

        # Face Anchor 상태 (얼굴 고정용 전용 참조 이미지)
        self._face_anchor_image: Optional[Image.Image] = None
        self._face_anchor_embeds = None

        # LoRA 상태
        self._lora_loaded = False
        self._current_lora_path: Optional[str] = None

        # ControlNet 상태
        self._controlnet_loaded = False

    def _determine_device(self, device: str) -> str:
        """장치 결정"""
        if device == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        return device

    # ------------------------------------------------------------------ #
    #  모델 로드 / 언로드
    # ------------------------------------------------------------------ #

    async def load_model(self) -> None:
        """SDXL 베이스 모델 로드"""
        if self._is_loaded:
            return

        print(f"Loading SDXL on {self.device}...")

        self.pipeline = StableDiffusionXLPipeline.from_pretrained(
            self.model_path,
            torch_dtype=self.dtype,
            use_safetensors=True,
            variant="fp16" if self.dtype == torch.float16 else None,
        )

        if self.device == "cuda":
            if self.low_vram:
                # 저VRAM 모드: CPU offload (6GB 필수)
                self.pipeline.enable_model_cpu_offload()
            else:
                self.pipeline = self.pipeline.to(self.device)

        self._is_loaded = True
        print("SDXL loaded successfully")

        # IP-Adapter 자동 로드
        if self._ip_adapter_enabled:
            self._load_ip_adapter()

    async def unload_model(self) -> None:
        """모델 언로드"""
        if self.pipeline:
            del self.pipeline
            self.pipeline = None
        if self._controlnet_pipeline:
            del self._controlnet_pipeline
            self._controlnet_pipeline = None
        if self._controlnet:
            del self._controlnet
            self._controlnet = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        self._is_loaded = False
        self._ip_adapter_loaded = False
        self._lora_loaded = False
        self._controlnet_loaded = False
        self._ip_adapter_embeds = None
        self._reference_image = None
        self._face_anchor_image = None
        self._face_anchor_embeds = None

    # ------------------------------------------------------------------ #
    #  IP-Adapter (diffusers 내장 방식)
    # ------------------------------------------------------------------ #

    def _load_ip_adapter(self) -> bool:
        """
        IP-Adapter 로드 (diffusers 내장)

        pipeline.load_ip_adapter() 사용
        """
        if not self.pipeline:
            return False

        try:
            settings = get_settings()
            model_path = settings.ip_adapter_model_path

            # 경로 존재 확인
            if not Path(model_path).exists():
                # huggingface hub ID 로 시도
                # 예: "h94/IP-Adapter" subfolder "sdxl_models"
                self.pipeline.load_ip_adapter(
                    "h94/IP-Adapter",
                    subfolder="sdxl_models",
                    weight_name="ip-adapter_sdxl.bin",
                )
            else:
                self.pipeline.load_ip_adapter(
                    model_path,
                    weight_name="ip-adapter_sdxl.bin",
                )

            # 기본 스케일 설정
            self.pipeline.set_ip_adapter_scale(self._ip_adapter_scale)
            self._ip_adapter_loaded = True
            print("IP-Adapter (diffusers 내장) loaded")
            return True

        except Exception as e:
            print(f"IP-Adapter 로드 실패: {e}")
            self._ip_adapter_loaded = False
            return False

    def set_character_reference(self, image_path: str) -> bool:
        """
        캐릭터 기준 이미지 설정

        IP-Adapter image embeds를 미리 계산하여 재사용

        Args:
            image_path: 기준 이미지 경로

        Returns:
            설정 성공 여부
        """
        try:
            ref_image = Image.open(image_path).convert("RGB")
            self._reference_image = ref_image

            # embeds 미리 계산 (파이프라인이 로드된 경우)
            if self._ip_adapter_loaded and self.pipeline:
                self._precompute_ip_adapter_embeds(ref_image)

            return True

        except Exception as e:
            print(f"기준 이미지 설정 실패: {e}")
            return False

    def _precompute_ip_adapter_embeds(self, image: Image.Image) -> None:
        """
        IP-Adapter 이미지 임베딩 미리 계산

        pipeline.prepare_ip_adapter_image_embeds() 사용
        """
        try:
            self._ip_adapter_embeds = self.pipeline.prepare_ip_adapter_image_embeds(
                ip_adapter_image=image,
                ip_adapter_image_embeds=None,
                device="cpu",  # VRAM 절약을 위해 CPU에서 계산
                num_images_per_prompt=1,
                do_classifier_free_guidance=True,
            )
            print("IP-Adapter embeds precomputed")
        except Exception as e:
            print(f"IP-Adapter embeds 계산 실패: {e}")
            self._ip_adapter_embeds = None

    def clear_character_reference(self):
        """캐릭터 기준 이미지 초기화"""
        self._reference_image = None
        self._ip_adapter_embeds = None
        self._face_anchor_image = None
        self._face_anchor_embeds = None

    def is_ip_adapter_loaded(self) -> bool:
        """IP-Adapter 로드 여부"""
        return self._ip_adapter_loaded

    # ------------------------------------------------------------------ #
    #  Face Anchor (얼굴 고정용 전용 참조)
    # ------------------------------------------------------------------ #

    def _set_face_anchor(self, image_path: str) -> bool:
        """
        Face Anchor 설정 (generate 호출 시 임시 사용)

        Face Authority 원칙에 따라 IP-Adapter의 참조를
        장면 참조가 아닌 얼굴 고정용으로 교체한다.
        embeds를 계산하여 _ip_adapter_embeds에 임시 할당.

        Args:
            image_path: 얼굴 고정용 이미지 경로

        Returns:
            Face Anchor 적용 성공 여부
        """
        try:
            anchor_image = Image.open(image_path).convert("RGB")
            self._face_anchor_image = anchor_image

            # Face Anchor embeds 계산
            if self.pipeline and self._ip_adapter_loaded:
                self._face_anchor_embeds = self.pipeline.prepare_ip_adapter_image_embeds(
                    ip_adapter_image=anchor_image,
                    ip_adapter_image_embeds=None,
                    device="cpu",
                    num_images_per_prompt=1,
                    do_classifier_free_guidance=True,
                )
                # 기존 embeds를 Face Anchor embeds로 교체
                self._ip_adapter_embeds = self._face_anchor_embeds

                # Face Authority: 얼굴 결정권 보장 (최소 0.8)
                if self._ip_adapter_scale < 0.8:
                    self.pipeline.set_ip_adapter_scale(0.8)

                print(f"Face Anchor 설정됨: {image_path}")
                return True

            return False

        except Exception as e:
            print(f"Face Anchor 설정 실패: {e}")
            return False

    def clear_face_anchor(self):
        """Face Anchor 초기화"""
        self._face_anchor_image = None
        self._face_anchor_embeds = None

    # ------------------------------------------------------------------ #
    #  LoRA (PEFT 방식)
    # ------------------------------------------------------------------ #

    def load_lora(self, lora_path: str, scale: float = 0.5) -> bool:
        """
        LoRA 가중치 로드 (PEFT 방식)

        Face Authority: LoRA는 스타일만 담당 (얼굴 관여 금지)
        기본값 0.5 = 스타일 영향만, 얼굴에는 관여하지 않도록 낮춤

        Args:
            lora_path: LoRA 파일 경로 또는 HuggingFace ID
            scale: LoRA 스케일 (권장: 0.3~0.6, 0.7 이상 금지)

        Returns:
            로드 성공 여부
        """
        if not self.pipeline:
            return False

        try:
            self.pipeline.load_lora_weights(lora_path)
            self._lora_loaded = True
            self._current_lora_path = lora_path
            print(f"LoRA loaded: {lora_path}")
            return True
        except Exception as e:
            print(f"LoRA 로드 실패: {e}")
            return False

    def unload_lora(self) -> None:
        """LoRA 언로드"""
        if self._lora_loaded and self.pipeline:
            try:
                self.pipeline.unload_lora_weights()
            except Exception:
                pass
        self._lora_loaded = False
        self._current_lora_path = None

    # ------------------------------------------------------------------ #
    #  ControlNet OpenPose
    # ------------------------------------------------------------------ #

    def _load_controlnet(self) -> bool:
        """
        ControlNet OpenPose SDXL 로드

        모델: thibaud/controlnet-openpose-sdxl-1.0
        """
        if self._controlnet_loaded:
            return True

        try:
            self._controlnet = ControlNetModel.from_pretrained(
                "thibaud/controlnet-openpose-sdxl-1.0",
                torch_dtype=self.dtype,
            )

            # 기존 파이프라인을 ControlNet 파이프라인으로 교체
            self._controlnet_pipeline = StableDiffusionXLControlNetPipeline.from_pretrained(
                self.model_path,
                controlnet=self._controlnet,
                torch_dtype=self.dtype,
                use_safetensors=True,
                variant="fp16" if self.dtype == torch.float16 else None,
            )

            if self.device == "cuda":
                if self.low_vram:
                    self._controlnet_pipeline.enable_model_cpu_offload()
                else:
                    self._controlnet_pipeline = self._controlnet_pipeline.to(self.device)

            self._controlnet_loaded = True
            print("ControlNet OpenPose SDXL loaded")
            return True

        except Exception as e:
            print(f"ControlNet 로드 실패: {e}")
            return False

    async def generate_with_controlnet(
        self,
        prompt: str,
        preset: StylePreset,
        pose_image_path: str,
        output_path: str,
        controlnet_scale: float = 0.7,
        width: int = 576,
        height: int = 1024,
    ) -> str:
        """
        ControlNet OpenPose 기반 이미지 생성

        Args:
            prompt: 이미지 프롬프트
            preset: 스타일 프리셋
            pose_image_path: OpenPose 포즈 이미지 경로
            output_path: 출력 경로
            controlnet_scale: ControlNet 영향도 (0.0~1.0)
            width: 너비
            height: 높이

        Returns:
            생성된 이미지 경로
        """
        if not self._is_loaded:
            await self.load_model()

        # ControlNet 로드 (필요시)
        if not self._controlnet_loaded:
            self._load_controlnet()

        if not self._controlnet_pipeline:
            # ControlNet 실패 시 기본 생성으로 폴백
            return await self.generate(prompt, preset, output_path, width, height)

        # 포즈 이미지 로드
        pose_image = load_image(pose_image_path)

        # 프롬프트 조합
        full_prompt = f"{preset.base_prompt}, {prompt}" if preset.base_prompt else prompt
        negative = self._build_negative_prompt(preset)

        # 시드 설정
        generator = None
        if preset.seed and preset.seed > 0:
            generator = torch.Generator(device="cpu").manual_seed(preset.seed)

        # 생성 파라미터
        call_kwargs = dict(
            prompt=full_prompt,
            negative_prompt=negative,
            image=pose_image,
            controlnet_conditioning_scale=controlnet_scale,
            num_inference_steps=preset.steps,
            guidance_scale=preset.cfg_scale,
            width=width,
            height=height,
            generator=generator,
        )

        # IP-Adapter embeds 추가
        if self._ip_adapter_embeds is not None:
            call_kwargs["ip_adapter_image_embeds"] = self._ip_adapter_embeds

        result = self._controlnet_pipeline(**call_kwargs)
        image = result.images[0]

        # 저장
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, quality=95)

        return output_path

    # ------------------------------------------------------------------ #
    #  기본 인터페이스 구현
    # ------------------------------------------------------------------ #

    def is_loaded(self) -> bool:
        return self._is_loaded

    def get_model_name(self) -> str:
        return "SDXL"

    def _build_negative_prompt(self, preset: StylePreset) -> str:
        """
        Negative prompt 조합

        배경 노이즈 요소 제거 + SDXL 텍스트 렌더링 방지 + 사용자 negative prompt 병합
        """
        parts = []
        if preset.negative_prompt:
            parts.append(preset.negative_prompt)
        parts.append(NEGATIVE_PROMPT_BG)
        parts.append(NEGATIVE_PROMPT_TEXT)
        return ", ".join(parts)

    async def generate(
        self,
        prompt: str,
        preset: StylePreset,
        output_path: str,
        width: int = 576,
        height: int = 1024,
        use_ip_adapter: bool = True,
        face_anchor_image: Optional[str] = None,
    ) -> str:
        """
        이미지 생성

        Face Authority: 얼굴 = IP-Adapter 단일 소스 (100% 결정권)
        LoRA는 스타일만 담당하며 얼굴에 관여하지 않음

        Args:
            prompt: 이미지 프롬프트
            preset: 스타일 프리셋
            output_path: 출력 경로
            width: 너비 (기본 576, 9:16)
            height: 높이 (기본 1024, 9:16)
            use_ip_adapter: IP-Adapter 사용 여부
            face_anchor_image: Face Anchor 이미지 경로 (optional)
                제공되면 IP-Adapter의 참조 이미지로 사용하여 얼굴을 고정.
                장면 참조(reference_image)가 아닌 얼굴 고정 전용.

        Returns:
            생성된 이미지 경로
        """
        if not self._is_loaded:
            await self.load_model()

        # Face Anchor 처리: 얼굴 고정용 이미지가 제공되면 embeds 교체
        prev_embeds = self._ip_adapter_embeds
        face_anchor_active = False

        if face_anchor_image and self._ip_adapter_loaded:
            face_anchor_active = self._set_face_anchor(face_anchor_image)

        # 프롬프트 조합
        full_prompt = f"{preset.base_prompt}, {prompt}" if preset.base_prompt else prompt
        negative = self._build_negative_prompt(preset)

        # IP-Adapter 사용 시
        if (
            use_ip_adapter
            and self._ip_adapter_loaded
            and self._ip_adapter_embeds is not None
        ):
            image = await self._generate_with_ip_adapter(
                full_prompt, negative, preset, width, height
            )
        else:
            image = await self._generate_standard(
                full_prompt, negative, preset, width, height
            )

        # Face Anchor 복구: 임시 교체한 embeds를 원래대로 복원
        if face_anchor_active:
            self._ip_adapter_embeds = prev_embeds

        # 저장
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, quality=95)

        return output_path

    # ------------------------------------------------------------------ #
    #  프롬프트 청킹 (Prompt Chunking)
    #  A1111/WebUI/ComfyUI 방식: 75토큰 단위 분할 → 임베딩 결합
    # ------------------------------------------------------------------ #

    CHUNK_SIZE = 75  # 77 - BOS - EOS

    def _encode_prompt_with_chunking(
        self,
        prompt: str,
        negative_prompt: str,
        device: str,
    ):
        """
        프롬프트 청킹: A1111 방식
        75토큰 단위로 분할 → 개별 인코딩 → 임베딩 결합

        Returns:
            (prompt_embeds, negative_prompt_embeds,
             pooled_prompt_embeds, negative_pooled_prompt_embeds)
            - prompt_embeds: 긍정 임베딩 [1, seq, 2048]
            - negative_prompt_embeds: 부정 임베딩 [1, seq, 2048]
            - pooled_prompt_embeds: 긍정 pooled [1, 1280]
            - negative_pooled_prompt_embeds: 부정 pooled [1, 1280]
        """
        pipe = self.pipeline
        dev = torch.device(device)

        def _encode_long(text, tokenizer, text_encoder):
            """긴 텍스트를 청킹하여 인코딩"""
            tokens = tokenizer.tokenize(text)
            if len(tokens) <= self.CHUNK_SIZE:
                # 77토큰 이내: 표준 인코딩
                tok_out = tokenizer(
                    text, padding="max_length", truncation=True,
                    max_length=tokenizer.model_max_length, return_tensors="pt",
                )
                with torch.no_grad():
                    out = text_encoder(tok_out.input_ids.to(dev))
                    return out.last_hidden_state

            # 75토큰 단위 청크 분할
            logger.info(f"Prompt chunking: {len(tokens)} tokens → {(len(tokens) + self.CHUNK_SIZE - 1) // self.CHUNK_SIZE} chunks")
            chunks = []
            for i in range(0, len(tokens), self.CHUNK_SIZE):
                chunk_tokens = tokens[i:i + self.CHUNK_SIZE]
                ids = [tokenizer.bos_token_id] + tokenizer.convert_tokens_to_ids(chunk_tokens) + [tokenizer.eos_token_id]
                actual_len = len(ids)
                ids += [tokenizer.pad_token_id] * (tokenizer.model_max_length - actual_len)
                chunks.append((ids, actual_len))

            embeddings = []
            for ids, actual_len in chunks:
                input_ids = torch.tensor([ids], dtype=torch.long).to(dev)
                with torch.no_grad():
                    out = text_encoder(input_ids)
                    embeddings.append(out.last_hidden_state[:, :actual_len, :])

            # 청크 결합: 이전 EOS와 다음 BOS 중복 제거
            result = embeddings[0]
            for emb in embeddings[1:]:
                result = torch.cat([result[:, :-1, :], emb[:, 1:, :]], dim=1)
            return result

        def _pad(a, b):
            """시퀀스 길이 맞추기 (zero-pad)"""
            if a.shape[1] < b.shape[1]:
                p = torch.zeros(1, b.shape[1] - a.shape[1], a.shape[2], device=a.device, dtype=a.dtype)
                a = torch.cat([a, p], dim=1)
            elif b.shape[1] < a.shape[1]:
                p = torch.zeros(1, a.shape[1] - b.shape[1], b.shape[2], device=b.device, dtype=b.dtype)
                b = torch.cat([b, p], dim=1)
            return a, b

        # 1. 양쪽 텍스트 인코더로 인코딩
        pos_1 = _encode_long(prompt, pipe.tokenizer, pipe.text_encoder)
        pos_2 = _encode_long(prompt, pipe.tokenizer_2, pipe.text_encoder_2)
        neg_1 = _encode_long(negative_prompt, pipe.tokenizer, pipe.text_encoder)
        neg_2 = _encode_long(negative_prompt, pipe.tokenizer_2, pipe.text_encoder_2)

        # 2. 인코더 간 시퀀스 길이 맞추기
        pos_1, pos_2 = _pad(pos_1, pos_2)
        neg_1, neg_2 = _pad(neg_1, neg_2)

        # 3. feature 차원 결합 (encoder_1 + encoder_2)
        prompt_embeds = torch.cat([pos_1, pos_2], dim=-1)
        negative_prompt_embeds = torch.cat([neg_1, neg_2], dim=-1)

        # 4. positive/negative 시퀀스 길이 맞추기
        prompt_embeds, negative_prompt_embeds = _pad(prompt_embeds, negative_prompt_embeds)

        # 5. Pooled: pipeline 내장 사용 (마지막 77토큰 분량으로)
        #    encode_prompt 반환값: (prompt_embeds, negative_prompt_embeds,
        #                          pooled_prompt_embeds, pooled_negative_prompt_embeds)
        _, _, pooled_prompt_embeds, pooled_negative_prompt_embeds = pipe.encode_prompt(
            prompt=prompt, prompt_2=prompt, device=dev, num_images_per_prompt=1,
            do_classifier_free_guidance=False,
        )
        _, _, neg_pooled, _ = pipe.encode_prompt(
            prompt=negative_prompt, prompt_2=negative_prompt, device=dev,
            num_images_per_prompt=1, do_classifier_free_guidance=False,
        )
        negative_pooled_prompt_embeds = neg_pooled

        return prompt_embeds, negative_prompt_embeds, pooled_prompt_embeds, negative_pooled_prompt_embeds

    # ------------------------------------------------------------------ #
    #  이미지 생성
    # ------------------------------------------------------------------ #

    async def _generate_standard(
        self,
        prompt: str,
        negative_prompt: str,
        preset: StylePreset,
        width: int,
        height: int,
    ) -> Image.Image:
        """표준 이미지 생성 (프롬프트 청킹 적용)"""
        generator = None
        if preset.seed and preset.seed > 0:
            generator = torch.Generator(device="cpu").manual_seed(preset.seed)

        # 프롬프트 청킹으로 임베딩 생성 (4개 분리 반환)
        prompt_embeds, negative_prompt_embeds, pooled_embeds, negative_pooled_embeds = (
            self._encode_prompt_with_chunking(
                prompt=prompt,
                negative_prompt=negative_prompt,
                device=self.device,
            )
        )

        call_kwargs = dict(
            prompt_embeds=prompt_embeds,
            negative_prompt_embeds=negative_prompt_embeds,
            pooled_prompt_embeds=pooled_embeds,
            negative_pooled_prompt_embeds=negative_pooled_embeds,
            num_inference_steps=preset.steps,
            guidance_scale=preset.cfg_scale,
            width=width,
            height=height,
            generator=generator,
        )

        # IP-Adapter가 파이프라인에 로드된 경우:
        if self._ip_adapter_loaded and self.pipeline:
            dummy_embeds = self._create_dummy_ip_adapter_embeds()
            if dummy_embeds is not None:
                call_kwargs["ip_adapter_image_embeds"] = dummy_embeds
            self.pipeline.set_ip_adapter_scale(0.0)

        result = self.pipeline(**call_kwargs)

        # IP-Adapter scale 복원
        if self._ip_adapter_loaded and self.pipeline:
            self.pipeline.set_ip_adapter_scale(self._ip_adapter_scale)

        return result.images[0]

    def _create_dummy_ip_adapter_embeds(self):
        """IP-Adapter 더미 embeds 생성

        IP-Adapter가 로드되었지만 참조 이미지가 없는 경우
        UNet의 ip_image_proj 요구사항을 충족하기 위해 사용
        """
        try:
            dummy_image = Image.new("RGB", (224, 224), (128, 128, 128))
            return self.pipeline.prepare_ip_adapter_image_embeds(
                ip_adapter_image=dummy_image,
                ip_adapter_image_embeds=None,
                device="cpu",
                num_images_per_prompt=1,
                do_classifier_free_guidance=True,
            )
        except Exception:
            return None

    async def _generate_with_ip_adapter(
        self,
        prompt: str,
        negative_prompt: str,
        preset: StylePreset,
        width: int,
        height: int,
    ) -> Image.Image:
        """IP-Adapter embeds를 사용한 이미지 생성 (프롬프트 청킹 적용)"""
        generator = None
        if preset.seed and preset.seed > 0:
            generator = torch.Generator(device="cpu").manual_seed(preset.seed)

        # 프롬프트 청킹으로 임베딩 생성 (4개 분리 반환)
        prompt_embeds, negative_prompt_embeds, pooled_embeds, negative_pooled_embeds = (
            self._encode_prompt_with_chunking(
                prompt=prompt,
                negative_prompt=negative_prompt,
                device=self.device,
            )
        )

        try:
            result = self.pipeline(
                prompt_embeds=prompt_embeds,
                negative_prompt_embeds=negative_prompt_embeds,
                pooled_prompt_embeds=pooled_embeds,
                negative_pooled_prompt_embeds=negative_pooled_embeds,
                ip_adapter_image_embeds=self._ip_adapter_embeds,
                num_inference_steps=preset.steps,
                guidance_scale=preset.cfg_scale,
                width=width,
                height=height,
                generator=generator,
            )
            return result.images[0]
        except Exception as e:
            print(f"IP-Adapter 생성 실패, 기본 생성으로 폴백: {e}")
            return await self._generate_standard(
                prompt, negative_prompt, preset, width, height
            )

    async def generate_with_reference(
        self,
        prompt: str,
        preset: StylePreset,
        reference_image: str,
        output_path: str,
        scale: float = 0.8,
        face_anchor_image: Optional[str] = None,
    ) -> str:
        """
        참조 이미지 기반 생성 (IP-Adapter 사용)

        Face Authority 원칙:
        - face_anchor_image가 제공되면 얼굴 고정에 사용 (IP-Adapter 단일 소스)
        - reference_image는 장면/스타일 참조용
        - LoRA는 스타일만 담당 (얼굴 관여 금지)

        Args:
            prompt: 이미지 프롬프트
            preset: 스타일 프리셋
            reference_image: 기준 이미지 경로 (장면/스타일 참조)
            output_path: 출력 경로
            scale: IP-Adapter 강도 (0.0~1.0, Face Authority 최소 0.8)
            face_anchor_image: Face Anchor 이미지 경로 (optional)
                제공되면 얼굴 고정용으로 IP-Adapter 참조를 덮어씀

        Returns:
            생성된 이미지 경로
        """
        if not self._is_loaded:
            await self.load_model()

        # 기준 이미지 설정 (장면 참조)
        self.set_character_reference(reference_image)

        # IP-Adapter 스케일 임시 변경 (Face Authority 최소 보장)
        original_scale = self._ip_adapter_scale
        effective_scale = max(scale, 0.8)  # Face Authority: 최소 0.8
        if effective_scale > 0 and self._ip_adapter_loaded and self.pipeline:
            self._ip_adapter_scale = effective_scale
            self.pipeline.set_ip_adapter_scale(effective_scale)

        try:
            return await self.generate(
                prompt=prompt,
                preset=preset,
                output_path=output_path,
                use_ip_adapter=True,
                face_anchor_image=face_anchor_image,
            )
        finally:
            # 원래 스케일로 복구
            self._ip_adapter_scale = original_scale
            if self._ip_adapter_loaded and self.pipeline:
                self.pipeline.set_ip_adapter_scale(original_scale)

    async def generate_batch(
        self,
        prompts: List[str],
        preset: StylePreset,
        output_dir: str,
    ) -> List[str]:
        """여러 이미지 일괄 생성"""
        paths = []
        for i, prompt in enumerate(prompts):
            output_path = f"{output_dir}/image_{i:03d}.png"
            path = await self.generate(prompt, preset, output_path)
            paths.append(path)
        return paths
