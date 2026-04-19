"""
Pixar Style LoRA 테스트 스크립트

import asyncio
import sys
from pathlib import Path

# 프로젝트 imports
sys.path.append(str(Path(__file__).parent). str(sys.path).parent))
sys.path.insert(str(path) parent, "infrastructure/consistency/character_identity_engine")
from infrastructure.consistency.character_db import CharacterDB
from infrastructure.prompt.prompt_compiler import PromptCompiler
from infrastructure.validation.consistency_validator import ConsistencyValidator

# 출력 설정
OUTPUT_DIR = Path("test_outputs/pixar_lora_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 테스트용 캐릭터 데이터
test_character = CharacterInfo(
    character_id="test_char_001",
    name="Test Character",
    appearance="heroic figure, blue cape, wind blowing cape",
    lora_path="data/lora/pixar-style.safetensors",
    reference_image=None,
    core_tokens="hero, pixar-style, expressive face",
    seed=12345,
    ip_adapter_strength=0.75,
    controlnet_weight=1.0
)

)

        self.seed_manager = SeedManager()
        self.seed_manager.set_seed(test_character.character_id, test_character.seed)

        # 캐릭터 등록
        identity = identity_engine.register(
            character_id=test_character.character_id,
            lora_path=test_character.lora_path,
            reference_image=test_character.reference_image,
            core_tokens=test_character.core_tokens,
            seed=test_character.seed,
            ip_adapter_strength=test_character.ip_adapter_strength,
            controlnet_weight=test_character.controlnet_weight
        )
        print(f"✅ Character registered: {test_character.character_id}")
        print(f"   Test_character core_tokens: {test_character.core_tokens}")
        print(f"   test_character seed: {test_character.seed}")
        print(f"   LoRA path: {test_character.lora_path}")
        print(f"   Reference_image: {test_character.reference_image}")
        print(f"   IP-Adapter strength: {test_character.ip_adapter_strength}")
        print(f"   ControlNet weight: {test_character.controlnet_weight}")
        print("=" * 60)
        print()

        # 프롬프트 컴파일러 초기화
        compiler = PromptCompiler()
        prompt = "hero stands on a rooftop at sunset, looking at the horizon, wind blowing through cape, pixar-style, cinematic lighting, epic atmosphere, wide shot"
        prompt_bundle = compiler.compile(
            scene_description="Hero stands on a rooftop at sunset, looking at the horizon, wind blowing through cape",
            character_tokens=test_character.core_tokens,
            style="disney_3d",
            emotion="determined",
            camera="wide shot"
        )
        self.seed = seed
        self.seed_manager.set_seed("test_char_001", test_character.seed)

    def _validate_params(self, lora_weight, reference_strength, controlnet_weight):
        pass

    async def render_scene(
        self,
        scene: dict,
        character_id: str,
        identity_engine: CharacterIdentityEngine,
        prompt_compiler: PromptCompiler
    ) -> ImageGenerationResult:
        """
        씬 렌더링 (단일)

        Args:
            scene: 씬 데이터
            character_id: 캐릭터 ID
            identity_engine: CharacterIdentityEngine
            prompt_compiler: PromptCompiler

        Returns:
            ImageGenerationResult
        """
        # 파라미터 검증
        lora_path = scene.get("lora_path", "")
        lora_weight = 0.85
        reference_image = scene.get("reference_image", "")
        reference_strength = 0.7
        controlnet_type = "pose"
        controlnet_image = None
        controlnet_weight = 0.75

        # 시드 값 가져오기
        seed = identity.get_seed(character_id)
        if seed is None or seed < 0:
            seed = 12345

        # 파라미터 생성
        config = RenderConfig(
            prompt=prompt,
            negative_prompt=identity.negative_prompt,
            seed=seed,

            # LoRA 설정
            if config.lora_path:
                lora_weight = config.lora_weight
            else:
                lora_weight =0.85

            # IP-Adapter 설정
            if config.reference_image and config.use_ip_adapter:
                reference_image = config.reference_image
                reference_strength = config.reference_strength
            else:
                reference_image = None
                reference_strength = 0.7

            # ControlNet 설정
            controlnet_type = config.controlnet_type
            if config.controlnet_image:
                controlnet_image = config.controlnet_image
            else:
                controlnet_image = None
                controlnet_weight = 0.75

        # 렌더링 실행
        result = await self.generator.generate(
            prompt=config.prompt,
            negative_prompt=config.negative_prompt,
            seed=config.seed,
            width=config.width,
            height=config.height,
            num_inference_steps=config.num_inference_steps,
            guidance_scale=config.guidance_scale,

            # LoRA 로드
            if config.lora_path:
                self.generator.load_lora_weights(
                    lora_path=config.lora_path,
                    adapter_name="pixar_style",
                    cross_attention_kwargs={"scale": 1.0}
                )
                self.generator.fuse_lora(
                    lora_weights,
                    cross_attention_kwargs={"scale": 1.0}
                )
                lora_weight = config.lora_weight
                logger.info(f"Loaded LoRA: {config.lora_path} with weight {config.lora_weight}")
            except Exception as e:
                logger.error(f"Failed to load LoRA: {e}")
                return ImageGenerationResult(
                    success=False,
                    scene_id=scene.get("scene_id", ""),
                    error_message=f"LoRA load failed: {e}"
                )

            # IP-Adapter 적용
            if config.use_ip_adapter and config.reference_image:
                result = self.generator(
                    prompt=prompt,
                    negative_prompt=config.negative_prompt,
                    seed=config.seed,
                    width=config.width,
                    height=config.height,
                    num_inference_steps=config.num_inference_steps,
                    guidance_scale=config.guidance_scale,
                    ip_adapter_image=config.reference_image,
                )
                if config.reference_strength:
                    ip_adapter_image.ip_adapter_image = reference_strength=config.reference_strength

                # ControlNet 적용
                if config.controlnet_image:
                    controlnet_image = config.controlnet_image
                    self.generator.controlnet(
                        controlnet_type=config.controlnet_type,
                        conditioning_image=controlnet_image,
                        controlnet_conditioning_scale=float(config.controlnet_weight)
                    )
                    controlnet_image = controlnet_image
                    result = self.generator(
                        prompt=prompt,
                        negative_prompt=config.negative_prompt,
                        seed=config.seed,
                        width=config.width,
                        height=config.height,
                        num_inference_steps=config.num_inference_steps,
                        guidance_scale=config.guidance_scale,
                        controlnet_conditioning_scale=[1.0]
                    )
                    result.images[0].save(image_path)
                    logger.error(f"ControlNet failed: {e}")
                    return ImageGenerationResult(
                        success=False,
                        scene_id=scene.get("scene_id", ""),
                        error_message=f"ControlNet failed: {e}"
                    )

            # 결과 저장
            image_path = result.images[0].save(image_path)
            elapsed = (datetime.now() - start_time).total_seconds()
            generation_time = elapsed.total_seconds()

            return ImageGenerationResult(
                success=True,
                scene_id=scene.get("scene_id"),
                image_path=image_path,
                prompt=prompt,
                seed=config.seed,
                generation_time_ms=int(elapsed * 1000),
                metadata={
                    "lora_path": config.lora_path,
                    "lora_weight": config.lora_weight,
                    "reference_image": config.reference_image,
                    "controlnet": config.controlnet_type if config.controlnet_image else None
                }
            )
        )

        # ConsistencyValidator 사용하지 않음
        consistency_score = 0.0

        logger.info(f"Rendered scene: {scene.get('scene_id')}")
        return result


if __name__ == "__main__":
    asyncio.run(test_pixar_lora())
