"""
Render Engine - 캐릭터 일관성 렌더링 엔진 (SDXL 기반)

Face Authority 아키텍처:
  - 얼굴 = IP-Adapter 단일 소스 (scale 0.7~0.9)
  - LoRA = 스타일만 (scale 0.3~0.6)
  - 프롬프트 = 얼굴 묘사 금지
  - ControlNet = 포즈 고정

LoRA + IP-Adapter (embeds) + Seed + ControlNet 동시 적용
SDXL 파이프라인 호환 (StableDiffusionXLPipeline)
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import asyncio
import logging

logger = logging.getLogger(__name__)

# SDXL 기본 배경 제거 negative prompt
SDXL_BG_REMOVAL_NEGATIVE = (
    "background, landscape, scenery, environment, "
    "blurry, low quality, distorted, watermark, text, "
    "bad anatomy, ugly, deformed, extra limbs, different person"
)

# Face Authority 기본 파라미터
# 얼굴 = IP-Adapter 단일 소스, LoRA = 스타일만
FACE_AUTHORITY_DEFAULTS = {
    "lora_weight": 0.5,          # 스타일만 (0.3~0.6)
    "ip_adapter_scale": 0.8,     # 얼굴 결정권 (0.7~0.9)
    "controlnet_weight": 0.75,   # 포즈 고정
}


@dataclass
class RenderConfig:
    """렌더링 설정 (SDXL 호환, Face Authority 아키텍처)"""
    # 필수
    prompt: str
    negative_prompt: str
    seed: int

    # LoRA (스타일만 - Face Authority: weight 0.3~0.6)
    lora_path: str = ""
    lora_weight: float = 0.5

    # IP-Adapter (얼굴 결정권 - Face Authority: scale 0.7~0.9)
    reference_image: str = ""
    reference_strength: float = 0.8
    use_ip_adapter: bool = True
    ip_adapter_embeds: Optional[Any] = None  # 사전 계산된 embeds
    ip_adapter_scale: float = 0.8

    # Face Anchor (얼굴 전용 참조 이미지, 장면 참조와 분리)
    face_anchor_image: Optional[str] = None  # 얼굴 일관성을 위한 전용 앵커

    # ControlNet (SDXL conditioning)
    controlnet_type: str = "pose"  # pose, depth, canny
    controlnet_image: str = ""
    controlnet_weight: float = 0.75
    controlnet_conditioning_image: Optional[Any] = None  # 전처리된 conditioning 이미지
    controlnet_conditioning_scale: float = 0.75

    # 이미지 크기 (SDXL 권장 해상도)
    width: int = 1024
    height: int = 1024

    # 생성 파라미터 (SDXL 최적화)
    num_inference_steps: int = 28
    guidance_scale: float = 7.5


@dataclass
class RenderResult:
    """렌더링 결과"""
    image_path: str
    seed: int
    prompt: str
    generation_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class RenderEngine:
    """
    캐릭터 일관성 렌더링 엔진 (SDXL 기반)

    4요소 동시 적용:
    1. LoRA - 캐릭터 학습
    2. IP-Adapter (embeds) - 참조 이미지 임베딩
    3. Seed - 고정
    4. ControlNet - Pose 가이드 (conditioning image)
    """

    # 필수 조건 체크
    REQUIRED_FOR_CONSISTENCY = ["lora", "ip_adapter", "seed"]

    def __init__(self, generator=None):
        """
        Args:
            generator: SDXLGenerator 또는 호환 이미지 생성기
        """
        self.generator = generator

    async def render(
        self,
        config: RenderConfig,
        validate_config: bool = True
    ) -> RenderResult:
        """
        씬 렌더링

        Args:
            config: 렌더링 설정
            validate_config: 설정 검증 여부

        Returns:
            RenderResult
        """
        if validate_config:
            self._validate_config(config)

        import time
        start_time = time.time()

        # Face Authority: face_anchor_image가 있으면 IP-Adapter 참조로 사용
        # 얼굴 앵커와 장면 참조 이미지를 분리
        ip_adapter_reference = config.reference_image
        if config.face_anchor_image:
            ip_adapter_reference = config.face_anchor_image
            logger.info("[Face Authority] Using Face Anchor for character consistency")
        elif config.reference_image:
            ip_adapter_reference = config.reference_image

        # Face Authority: LoRA는 스타일만 담당
        if config.lora_path:
            logger.info(
                f"[Face Authority] LoRA style-only mode (weight: {config.lora_weight})"
            )

        # SDXL 파이프라인 파라미터 구성
        generate_kwargs = {
            "prompt": config.prompt,
            "negative_prompt": config.negative_prompt,
            "seed": config.seed,
            "width": config.width,
            "height": config.height,
            "num_inference_steps": config.num_inference_steps,
            "guidance_scale": config.guidance_scale,

            # LoRA (스타일만)
            "lora": config.lora_path if config.lora_path else None,
            "lora_weight": config.lora_weight,

            # IP-Adapter (얼굴 결정권 - embeds 방식)
            "reference_image": ip_adapter_reference if config.use_ip_adapter else None,
            "reference_strength": config.reference_strength,
            "use_ip_adapter": config.use_ip_adapter,
            "ip_adapter_embeds": config.ip_adapter_embeds,
            "ip_adapter_scale": config.ip_adapter_scale,

            # ControlNet (conditioning)
            "controlnet": self._build_controlnet_params(config),
        }

        # 생성기 호출
        result = await self.generator.generate(**generate_kwargs)

        generation_time = time.time() - start_time

        return RenderResult(
            image_path=result if isinstance(result, str) else result.image_path,
            seed=config.seed,
            prompt=config.prompt,
            generation_time=generation_time,
            metadata={
                "lora": config.lora_path,
                "lora_weight": config.lora_weight,
                "reference": config.reference_image,
                "face_anchor": config.face_anchor_image,
                "controlnet": config.controlnet_type,
                "ip_adapter_embeds": config.ip_adapter_embeds is not None,
                "ip_adapter_scale": config.ip_adapter_scale,
                "controlnet_conditioning": config.controlnet_conditioning_image is not None,
                "face_authority": config.face_anchor_image is not None,
            }
        )

    def _build_controlnet_params(self, config: RenderConfig) -> Optional[Dict[str, Any]]:
        """ControlNet 파라미터 구성 (SDXL conditioning)"""
        if not config.controlnet_image and config.controlnet_conditioning_image is None:
            return None

        controlnet_params = {
            "type": config.controlnet_type,
            "image": config.controlnet_image,
            "weight": config.controlnet_weight,
            "conditioning_scale": config.controlnet_conditioning_scale,
        }

        # 전처리된 conditioning 이미지가 있으면 사용
        if config.controlnet_conditioning_image is not None:
            controlnet_params["conditioning_image"] = config.controlnet_conditioning_image

        return controlnet_params

    async def render_scene(
        self,
        scene: Dict[str, Any],
        character_id: str,
        identity_engine,
        prompt_compiler,
        output_dir: str = "outputs/renders",
        face_anchor_image: Optional[str] = None
    ) -> RenderResult:
        """
        씬 렌더링 (통합 인터페이스, Face Authority 지원)

        Args:
            scene: 씬 데이터
            character_id: 캐릭터 ID
            identity_engine: CharacterIdentityEngine
            prompt_compiler: PromptCompiler
            output_dir: 출력 디렉토리
            face_anchor_image: 얼굴 일관성을 위한 전용 앵커 이미지 (선택)
        """
        # 1. 캐릭터 정체성 조회
        identity_config = identity_engine.get_render_config(character_id)

        # 2. 프롬프트 컴파일 (77토큰 최적화)
        prompt = prompt_compiler.compile(
            scene_description=scene.get("description", ""),
            character_tokens=identity_config["core_tokens"],
            style=scene.get("style", "disney_3d"),
            emotion=scene.get("emotion"),
            camera=scene.get("camera")
        )

        # 3. negative prompt에 배경 제거 항목 추가 (필요 시)
        negative_prompt = identity_config["negative_prompt"]
        if scene.get("remove_background", False):
            negative_prompt = f"{negative_prompt}, {SDXL_BG_REMOVAL_NEGATIVE}"

        # 4. Face Authority 파라미터 적용
        # face_anchor_image 우선순위: 인자 > scene > identity_config
        resolved_face_anchor = (
            face_anchor_image
            or scene.get("face_anchor_image")
            or identity_config.get("face_anchor_image")
        )

        if resolved_face_anchor:
            logger.info(
                f"[Face Authority] Scene '{scene.get('id')}' using face anchor: "
                f"{resolved_face_anchor}"
            )

        # 5. 렌더링 설정 생성 (SDXL 파라미터, Face Authority 적용)
        config = RenderConfig(
            prompt=prompt,
            negative_prompt=negative_prompt,
            seed=identity_config["seed"],

            # LoRA (스타일만 - Face Authority: 0.3~0.6)
            lora_path=identity_config["lora"],
            lora_weight=identity_config.get("lora_weight", FACE_AUTHORITY_DEFAULTS["lora_weight"]),

            # IP-Adapter (얼굴 결정권 - Face Authority: 0.7~0.9)
            reference_image=identity_config["reference_image"],
            reference_strength=identity_config.get("reference_strength", 0.8),
            use_ip_adapter=True,
            ip_adapter_embeds=identity_config.get("ip_adapter_embeds"),
            ip_adapter_scale=identity_config.get(
                "ip_adapter_scale", FACE_AUTHORITY_DEFAULTS["ip_adapter_scale"]
            ),

            # Face Anchor (얼굴 전용 참조)
            face_anchor_image=resolved_face_anchor,

            # ControlNet (conditioning)
            controlnet_type=scene.get("controlnet_type", "pose"),
            controlnet_image=scene.get("pose_image", ""),
            controlnet_weight=identity_config.get(
                "controlnet_weight", FACE_AUTHORITY_DEFAULTS["controlnet_weight"]
            ),
            controlnet_conditioning_image=scene.get("controlnet_conditioning_image"),
            controlnet_conditioning_scale=scene.get("controlnet_conditioning_scale", 0.75),
        )

        # 6. 렌더링
        result = await self.render(config)

        logger.info(f"Rendered scene: {scene.get('id')} with character {character_id}")

        return result

    async def render_batch(
        self,
        scenes: List[Dict[str, Any]],
        character_id: str,
        identity_engine,
        prompt_compiler,
        output_dir: str = "outputs/renders"
    ) -> List[RenderResult]:
        """
        여러 씬 일괄 렌더링
        """
        results = []

        for i, scene in enumerate(scenes):
            logger.info(f"Rendering scene {i+1}/{len(scenes)}")

            result = await self.render_scene(
                scene=scene,
                character_id=character_id,
                identity_engine=identity_engine,
                prompt_compiler=prompt_compiler,
                output_dir=output_dir
            )
            results.append(result)

        return results

    def _validate_config(self, config: RenderConfig):
        """설정 검증 (SDXL 기준, Face Authority 아키텍처)"""
        errors = []

        # 프롬프트 토큰 체크
        token_count = len(config.prompt.split()) * 1.3
        if token_count > 77:
            errors.append(f"Prompt exceeds 77 tokens: {token_count:.0f}")

        # SDXL 해상도 권장 체크
        sdxl_recommended = [(1024, 1024), (768, 1024), (1024, 768), (512, 1024), (1024, 512)]
        if (config.width, config.height) not in sdxl_recommended:
            logger.warning(
                f"Resolution {config.width}x{config.height} may not be optimal for SDXL. "
                f"Recommended: {sdxl_recommended}"
            )

        # 필수 요소 체크 (경고만)
        if not config.lora_path:
            logger.warning("No LoRA specified - character consistency may be reduced")

        if not config.reference_image and config.ip_adapter_embeds is None and not config.face_anchor_image:
            logger.warning("No reference image, embeds, or face anchor - IP-Adapter disabled")

        if config.seed < 0:
            logger.warning("Negative seed - using random")

        # Face Authority: 파라미터 범위 경고
        # LoRA는 스타일만 담당 (0.3~0.6), 0.7 이상은 얼굴에 관여하므로 경고
        if config.lora_weight > 0.6:
            logger.warning(
                f"[Face Authority] lora_weight {config.lora_weight} exceeds 0.6 - "
                f"LoRA should only control style, not face (recommended: 0.3~0.6)"
            )

        if not (0.3 <= config.lora_weight <= 0.6):
            logger.warning(
                f"lora_weight {config.lora_weight} outside Face Authority range [0.3, 0.6]"
            )

        # IP-Adapter는 얼굴 결정권 (0.7~0.9)
        if not (0.7 <= config.ip_adapter_scale <= 0.9):
            logger.warning(
                f"ip_adapter_scale {config.ip_adapter_scale} outside Face Authority range [0.7, 0.9]"
            )

        if not (0.7 <= config.reference_strength <= 0.9):
            logger.warning(
                f"reference_strength {config.reference_strength} outside recommended range [0.7, 0.9]"
            )

        # ControlNet 포즈 고정 (0.7~0.8)
        if not (0.7 <= config.controlnet_weight <= 0.8):
            logger.warning(
                f"controlnet_weight {config.controlnet_weight} outside recommended range [0.7, 0.8]"
            )

        if not (0.7 <= config.controlnet_conditioning_scale <= 0.8):
            logger.warning(
                f"controlnet_conditioning_scale {config.controlnet_conditioning_scale} "
                f"outside recommended range [0.7, 0.8]"
            )

        if errors:
            for err in errors:
                logger.error(err)
            raise ValueError(f"Render config validation failed: {errors}")
