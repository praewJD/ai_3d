# -*- coding: utf-8 -*-
"""
StoryToImagePipeline - StorySpec -> 이미지 시퀀스 생성 E2E 파이프라인

Face Authority 아키텍처:
- 얼굴 = IP-Adapter 단일 소스 (scale 0.8)
- LoRA = 스타일만 (scale 0.5)
- 프롬프트 = 얼굴 묘사 없음 (ScenePromptBuilder가 자동 필터링)

RTX 3060 6GB VRAM 환경에서 CPU offload 기반으로 동작합니다.
"""
import asyncio
import gc
import json
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from infrastructure.story.story_spec import StorySpec, SceneSpec, CharacterSpec
from infrastructure.image.sdxl_generator import SDXLGenerator
from infrastructure.image.multi_char_regional import MultiCharRegionalGenerator
from infrastructure.pipeline.scene_prompt_builder import ScenePromptBuilder
from core.domain.entities.preset import StylePreset

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """파이프라인 설정"""

    base_model: str = "stabilityai/stable-diffusion-xl-base-1.0"
    lora_path: str = "D:/AI-Video/autonomous-creator/data/lora/3dModel_sdxl_v2.safetensors"
    lora_scale: float = 0.5  # Face Authority: 스타일만
    ip_adapter_scale: float = 0.8  # Face Authority: 얼굴 결정권
    seed: int = 12345
    steps: int = 25
    cfg_scale: float = 7.5
    width: int = 576  # 9:16 Shorts
    height: int = 1024
    style: str = "disney_3d"
    output_dir: str = "output/story_images"
    # Face Anchor: 캐릭터별 참조 이미지
    character_ref_images: Dict[str, str] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """파이프라인 실행 결과"""

    success: bool
    image_paths: List[str] = field(default_factory=list)
    scene_count: int = 0
    failed_scenes: List[str] = field(default_factory=list)
    total_time: float = 0.0
    error: str = ""


class StoryToImagePipeline:
    """
    StorySpec -> 이미지 시퀀스 생성 파이프라인

    Face Authority 아키텍처:
    - 얼굴 = IP-Adapter 단일 소스
    - LoRA = 스타일만 (scale 0.5)
    - 프롬프트 = 얼굴 묘사 없음

    사용법:
        pipeline = StoryToImagePipeline(config)
        result = await pipeline.run(story_spec)
    """

    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()
        self.generator = SDXLGenerator()
        self.prompt_builder = ScenePromptBuilder()
        self.regional_gen: Optional[MultiCharRegionalGenerator] = None
        self._is_loaded = False

    async def load(self) -> None:
        """모델 로드 (SDXL + LoRA + IP-Adapter)

        SDXL 베이스 모델을 CPU offload 모드로 로드하고,
        LoRA 가중치를 적용합니다.
        IP-Adapter는 SDXLGenerator.load_model()에서 자동 로드됩니다.
        """
        if self._is_loaded:
            logger.info("[StoryToImagePipeline] 이미 로드됨, 스킵")
            return

        try:
            # 1. SDXL 모델 로드 (CPU offload)
            logger.info("[StoryToImagePipeline] SDXL 모델 로드 시작...")
            await self.generator.load_model()
            logger.info("[StoryToImagePipeline] SDXL 모델 로드 완료")

            # 2. LoRA 로드 (scale 0.5 - Face Authority: 스타일만)
            if self.config.lora_path:
                lora_path = self.config.lora_path
                if Path(lora_path).exists():
                    lora_loaded = self.generator.load_lora(
                        lora_path, scale=self.config.lora_scale
                    )
                    if lora_loaded:
                        logger.info(
                            f"[StoryToImagePipeline] LoRA 로드 완료: "
                            f"{lora_path} (scale={self.config.lora_scale})"
                        )
                    else:
                        logger.warning(
                            f"[StoryToImagePipeline] LoRA 로드 실패: {lora_path}, "
                            "LoRA 없이 진행"
                        )
                else:
                    logger.warning(
                        f"[StoryToImagePipeline] LoRA 파일 없음: {lora_path}, "
                        "LoRA 없이 진행"
                    )

            # 3. IP-Adapter는 SDXLGenerator에서 자동 로드됨
            logger.info(
                f"[StoryToImagePipeline] IP-Adapter 상태: "
                f"loaded={self.generator.is_ip_adapter_loaded()}"
            )

            # 4. MultiCharRegionalGenerator 초기화
            self.regional_gen = MultiCharRegionalGenerator(self.generator)
            logger.info("[StoryToImagePipeline] RegionalGenerator 초기화 완료")

            self._is_loaded = True

        except Exception as e:
            logger.error(f"[StoryToImagePipeline] 모델 로드 실패: {e}")
            self._is_loaded = False
            raise

    async def run(self, story_spec: StorySpec) -> PipelineResult:
        """
        StorySpec -> 이미지 시퀀스 생성

        Args:
            story_spec: 컴파일된 스토리 명세

        Returns:
            PipelineResult: 생성 결과 (성공 여부, 이미지 경로 목록 등)
        """
        start_time = time.time()

        # 스토리 검증
        if not story_spec.scenes:
            return PipelineResult(
                success=False,
                error="StorySpec에 scenes가 없습니다",
                total_time=time.time() - start_time,
            )

        try:
            # 1. 모델 로드 (필요시)
            if not self._is_loaded:
                await self.load()

            # 2. 출력 디렉토리 생성
            output_dir = Path(self.config.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            total_scenes = len(story_spec.scenes)
            logger.info(
                f"[StoryToImagePipeline] 시작: "
                f"title='{story_spec.title}', "
                f"scenes={total_scenes}, "
                f"characters={len(story_spec.characters)}"
            )

            # 3. 캐릭터 참조 이미지 자동 생성
            await self._generate_character_references(story_spec, output_dir)

            # 4. 각 씬별 이미지 생성
            image_paths: List[str] = []
            failed_scenes: List[str] = []

            for i, scene in enumerate(story_spec.scenes):
                scene_label = f"[{i + 1}/{total_scenes}] scene={scene.id}"
                logger.info(f"{scene_label} 생성 시작...")

                try:
                    # 출력 파일 경로: {output_dir}/scene_{index:03d}_{scene_id}.png
                    output_path = str(
                        output_dir / f"scene_{i:03d}_{scene.id}.png"
                    )

                    path = await self._generate_scene_image(
                        scene=scene,
                        characters=story_spec.characters,
                        output_path=output_path,
                        scene_number=i,
                    )

                    image_paths.append(path)
                    logger.info(f"{scene_label} 생성 완료: {path}")

                except Exception as e:
                    failed_scenes.append(scene.id)
                    logger.error(
                        f"{scene_label} 생성 실패: {e}", exc_info=True
                    )
                    # 한 씬 실패해도 나머지 계속 진행

                # VRAM 정리 (Regional/CtrlNet 사용 후 누적 방지)
                gc.collect()
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass

            # 5. 결과 반환
            total_time = time.time() - start_time
            success = len(image_paths) > 0

            # 6. 전체 결과 리포트 (manifest_summary.json) 저장
            self._save_manifest_summary(
                story_spec=story_spec,
                image_paths=image_paths,
                failed_scenes=failed_scenes,
                total_time=total_time,
                output_dir=output_dir,
            )

            result = PipelineResult(
                success=success,
                image_paths=image_paths,
                scene_count=total_scenes,
                failed_scenes=failed_scenes,
                total_time=total_time,
                error="" if success else "모든 씬 생성에 실패했습니다",
            )

            logger.info(
                f"[StoryToImagePipeline] 완료: "
                f"success={success}, "
                f"images={len(image_paths)}/{total_scenes}, "
                f"failed={len(failed_scenes)}, "
                f"time={total_time:.1f}s"
            )

            return result

        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"[StoryToImagePipeline] 실행 실패: {e}", exc_info=True)
            return PipelineResult(
                success=False,
                image_paths=[],
                scene_count=len(story_spec.scenes),
                failed_scenes=[s.id for s in story_spec.scenes],
                total_time=total_time,
                error=str(e),
            )

    async def _generate_character_references(
        self,
        story_spec: StorySpec,
        output_dir: Path,
    ) -> None:
        """캐릭터별 참조 이미지 자동 생성

        각 캐릭터의 appearance 기반으로 portrait 프롬프트를 만들어
        close-up 참조 이미지를 생성합니다. 생성된 이미지는
        IP-Adapter face anchor로 사용되어 모든 씬에서 얼굴 일관성을 유지합니다.

        Args:
            story_spec: 스토리 명세 (characters 포함)
            output_dir: 출력 디렉토리
        """
        characters = story_spec.characters
        if not characters:
            return

        # 이미 참조 이미지가 있는 캐릭터는 스킵
        chars_to_generate = [
            c for c in characters
            if c.id not in self.config.character_ref_images
            or not Path(self.config.character_ref_images[c.id]).exists()
        ]

        if not chars_to_generate:
            logger.info("[StoryToImagePipeline] 모든 캐릭터 참조 이미지 존재, 스킵")
            return

        ref_dir = output_dir / "character_refs"
        ref_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"[StoryToImagePipeline] 캐릭터 참조 이미지 생성: "
            f"{len(chars_to_generate)}명"
        )

        preset = self._create_preset(seed=self.config.seed)

        for char in chars_to_generate:
            ref_path = str(ref_dir / f"{char.id}_ref.png")

            # 이미 존재하면 스킵
            if Path(ref_path).exists():
                self.config.character_ref_images[char.id] = ref_path
                logger.info(f"  {char.name} ({char.id}): 기존 참조 사용")
                continue

            # portrait 프롬프트 생성
            ref_prompt = (
                f"MG_ip, {char.appearance}, portrait photo, front facing, "
                f"neutral expression, clean white background, studio lighting, "
                f"Disney 3D style, Pixar quality, detailed face, "
                f"ultra detailed, 4k, masterpiece"
            )

            logger.info(f"  {char.name} ({char.id}) 참조 이미지 생성 중...")

            try:
                await self.generator.generate(
                    prompt=ref_prompt,
                    preset=preset,
                    output_path=ref_path,
                    width=512,
                    height=512,
                    use_ip_adapter=False,  # 참조 생성 시 IP-Adapter 없이
                )
                self.config.character_ref_images[char.id] = ref_path
                logger.info(f"  {char.name} 참조 이미지 생성 완료: {ref_path}")
            except Exception as e:
                logger.warning(
                    f"  {char.name} 참조 이미지 생성 실패: {e}, 참조 없이 진행"
                )

            # VRAM 정리
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

        # 첫 번째 캐릭터 참조를 기본 IP-Adapter embeds로 설정
        first_ref = None
        for char in characters:
            ref = self.config.character_ref_images.get(char.id)
            if ref and Path(ref).exists():
                first_ref = ref
                break

        if first_ref and self.generator.is_ip_adapter_loaded():
            self.generator.set_character_reference(first_ref)
            logger.info(
                f"[StoryToImagePipeline] 기본 IP-Adapter 참조 설정: {first_ref}"
            )

        logger.info(
            f"[StoryToImagePipeline] 캐릭터 참조 완료: "
            f"{len(self.config.character_ref_images)}명"
        )

    async def _generate_scene_image(
        self,
        scene: SceneSpec,
        characters: List[CharacterSpec],
        output_path: str,
        scene_number: int = 0,
    ) -> str:
        """단일 씬 이미지 생성 + 매니페스트 저장

        1인물 씬: SDXLGenerator.generate() 사용
        2인물 이상 씬: MultiCharRegionalGenerator 사용 (Regional Cross-Attention)

        Args:
            scene: 장면 명세
            characters: 전체 캐릭터 목록
            output_path: 출력 이미지 경로
            scene_number: 씬 인덱스 (0-based, 매니페스트 파일명에 사용)

        Returns:
            생성된 이미지 파일 경로
        """
        num_chars = len(scene.characters)

        if num_chars >= 2 and self.regional_gen is not None:
            return await self._generate_multi_char_scene(
                scene, characters, output_path, scene_number
            )

        # --- 1인물 씬: 기존 로직 ---
        # 1. ScenePromptBuilder로 프롬프트 생성
        prompt = self.prompt_builder.build_prompt(
            scene=scene,
            characters=characters,
            style=self.config.style,
        )

        # 2. Face Anchor 이미지 결정
        face_anchor = self._get_face_anchor(scene.characters)

        if face_anchor:
            logger.debug(
                f"[StoryToImagePipeline] Face Anchor: {face_anchor} "
                f"(scene={scene.id}, chars={scene.characters})"
            )
        else:
            logger.debug(
                f"[StoryToImagePipeline] Face Anchor 없음 "
                f"(scene={scene.id}, chars={scene.characters})"
            )

        # 3. StylePreset 생성 (Face Authority 파라미터)
        preset = self._create_preset(seed=self.config.seed)

        # 4. SDXLGenerator.generate() 호출 (생성 시간 측정)
        gen_start_time = time.time()
        image_path = await self.generator.generate(
            prompt=prompt,
            preset=preset,
            output_path=output_path,
            width=self.config.width,
            height=self.config.height,
            use_ip_adapter=True,
            face_anchor_image=face_anchor,
        )
        gen_elapsed = time.time() - gen_start_time

        # 5. 매니페스트 저장
        self._save_scene_manifest(
            scene=scene,
            characters=characters,
            prompt_used=prompt,
            preset=preset,
            image_path=image_path,
            scene_number=scene_number,
            generation_time_seconds=gen_elapsed,
        )

        return image_path

    async def _generate_multi_char_scene(
        self,
        scene: SceneSpec,
        characters: List[CharacterSpec],
        output_path: str,
        scene_number: int,
    ) -> str:
        """2인물 이상 씬: Regional Cross-Attention으로 생성

        MultiCharRegionalGenerator를 사용하여 각 캐릭터를
        별도 영역에 분리하여 생성합니다.

        Args:
            scene: 장면 명세
            characters: 전체 캐릭터 목록
            output_path: 출력 이미지 경로
            scene_number: 씬 인덱스

        Returns:
            생성된 이미지 파일 경로
        """
        num_chars = len(scene.characters)
        logger.info(
            f"[StoryToImagePipeline] Regional Cross-Attention 모드: "
            f"scene={scene.id}, chars={num_chars}"
        )

        gen_start_time = time.time()
        image_path = await self.regional_gen.generate_multi_char(
            scene=scene,
            characters=characters,
            output_path=output_path,
            seed=self.config.seed,
            steps=self.config.steps,
            cfg_scale=self.config.cfg_scale,
            width=self.config.width,
            height=self.config.height,
            controlnet_scale=0.4,
            use_controlnet=True,
            character_ref_images=self.config.character_ref_images,
        )
        gen_elapsed = time.time() - gen_start_time

        # 매니페스트 저장 (Regional 모드 표시)
        preset = self._create_preset(seed=self.config.seed)
        self._save_scene_manifest(
            scene=scene,
            characters=characters,
            prompt_used=f"[Regional Cross-Attention] {num_chars} chars: {scene.action}",
            preset=preset,
            image_path=image_path,
            scene_number=scene_number,
            generation_time_seconds=gen_elapsed,
        )

        return image_path

    def _save_scene_manifest(
        self,
        scene: SceneSpec,
        characters: List[CharacterSpec],
        prompt_used: str,
        preset: StylePreset,
        image_path: str,
        scene_number: int,
        generation_time_seconds: float,
    ) -> None:
        """씬 매니페스트 JSON 파일 저장

        이미지와 동일한 디렉토리에 scene_{number:03d}_manifest.json으로 저장합니다.
        매니페스트 저장 실패해도 이미지 생성 결과에는 영향을 주지 않습니다.

        Args:
            scene: 장면 명세
            characters: 전체 캐릭터 목록
            prompt_used: 실제 사용된 프롬프트
            preset: StylePreset (negative_prompt, seed, cfg_scale, steps 포함)
            image_path: 생성된 이미지 경로
            scene_number: 씬 인덱스 (0-based)
            generation_time_seconds: 이미지 생성 소요 시간
        """
        try:
            image_dir = Path(image_path).parent
            manifest_filename = f"scene_{scene_number:03d}_manifest.json"
            manifest_path = image_dir / manifest_filename

            # 씬에 등장하는 캐릭터의 ID 목록
            scene_char_ids = scene.characters

            manifest_data = {
                "scene_id": scene.id,
                "scene_number": scene_number,
                "purpose": scene.purpose.value if hasattr(scene.purpose, "value") else str(scene.purpose),
                "action": scene.action,
                "characters": scene_char_ids,
                "location": scene.location,
                "camera": scene.camera,
                "mood": scene.mood,
                "emotion": scene.emotion,
                "duration": scene.duration,
                "dialogue": scene.dialogue,
                "narration": scene.narration,
                "prompt_used": prompt_used,
                "negative_prompt": preset.negative_prompt,
                "image_path": Path(image_path).name,
                "seed": preset.seed,
                "steps": preset.steps,
                "cfg_scale": preset.cfg_scale,
                "generation_time_seconds": round(generation_time_seconds, 1),
            }

            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, ensure_ascii=False, indent=4)

            logger.info(
                f"[StoryToImagePipeline] 매니페스트 저장: {manifest_path}"
            )

        except Exception as e:
            # 매니페스트 저장 실패해도 이미지 생성은 성공으로 처리
            logger.warning(
                f"[StoryToImagePipeline] 매니페스트 저장 실패 "
                f"(scene={scene.id}): {e}"
            )

    def _save_manifest_summary(
        self,
        story_spec: StorySpec,
        image_paths: List[str],
        failed_scenes: List[str],
        total_time: float,
        output_dir: Path,
    ) -> None:
        """전체 결과 리포트 manifest_summary.json 저장

        모든 이미지 생성 완료 후 출력 디렉토리에 저장합니다.
        저장 실패해도 파이프라인 결과에는 영향을 주지 않습니다.

        Args:
            story_spec: 스토리 명세
            image_paths: 생성된 이미지 경로 목록
            failed_scenes: 실패한 씬 ID 목록
            total_time: 전체 파이프라인 소요 시간
            output_dir: 출력 디렉토리
        """
        try:
            summary_path = output_dir / "manifest_summary.json"

            # 씬별 요약 정보 구성
            scenes_summary = []
            for i, scene in enumerate(story_spec.scenes):
                # 해당 씬의 이미지 파일명 찾기
                expected_image = f"scene_{i:03d}_{scene.id}.png"
                manifest_file = f"scene_{i:03d}_manifest.json"

                # 실제 생성된 이미지인지 확인
                actual_image = expected_image
                for path_str in image_paths:
                    path_obj = Path(path_str)
                    if path_obj.name == expected_image:
                        actual_image = path_obj.name
                        break

                scenes_summary.append({
                    "scene_id": scene.id,
                    "image": actual_image,
                    "manifest": manifest_file,
                    "status": "success" if scene.id not in failed_scenes else "failed",
                })

            # 캐릭터 요약 정보
            characters_summary = [
                {
                    "id": char.id,
                    "name": char.name,
                    "appearance": char.appearance,
                }
                for char in story_spec.characters
            ]

            summary_data = {
                "title": story_spec.title,
                "total_scenes": len(story_spec.scenes),
                "total_images": len(image_paths),
                "total_time_seconds": round(total_time, 1),
                "characters": characters_summary,
                "scenes": scenes_summary,
            }

            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(summary_data, f, ensure_ascii=False, indent=4)

            logger.info(
                f"[StoryToImagePipeline] 전체 리포트 저장: {summary_path}"
            )

        except Exception as e:
            # 리포트 저장 실패해도 파이프라인 결과에는 영향 없음
            logger.warning(
                f"[StoryToImagePipeline] manifest_summary 저장 실패: {e}"
            )

    def _create_preset(self, seed: int = 12345) -> StylePreset:
        """Face Authority 기반 StylePreset 생성

        Returns:
            StylePreset: Face Authority 파라미터가 적용된 프리셋
        """
        return StylePreset(
            name="disney_3d_face_authority",
            base_prompt="high quality, 3d animation",
            negative_prompt=(
                "butterflies, insects, birds, flying objects, extra objects, "
                "background clutter, ugly, blurry, low quality, distorted, watermark"
            ),
            seed=seed,
            cfg_scale=self.config.cfg_scale,
            steps=self.config.steps,
            sampler="dpmpp_2m",
            ip_adapter_scale=self.config.ip_adapter_scale,  # Face Authority: 얼굴 결정권
            lora_weights=self.config.lora_path if self.config.lora_path else None,
            lora_scale=self.config.lora_scale,  # Face Authority: 스타일만
        )

    def _get_face_anchor(self, character_ids: List[str]) -> Optional[str]:
        """씬에 등장하는 캐릭터의 Face Anchor 이미지 경로 반환

        character_ref_images에서 첫 번째로 발견된 캐릭터의
        참조 이미지를 Face Anchor로 사용합니다.
        참조 이미지가 없으면 None을 반환합니다 (IP-Adapter 참조 없이 생성).

        Args:
            character_ids: 씬에 등장하는 캐릭터 ID 목록

        Returns:
            Face Anchor 이미지 경로 또는 None
        """
        for char_id in character_ids:
            ref_path = self.config.character_ref_images.get(char_id)
            if ref_path and Path(ref_path).exists():
                return ref_path

        return None

    async def unload(self) -> None:
        """모델 언로드 (VRAM 해제)"""
        if self._is_loaded:
            logger.info("[StoryToImagePipeline] 모델 언로드 시작...")
            await self.generator.unload_model()
            self._is_loaded = False
            logger.info("[StoryToImagePipeline] 모델 언로드 완료")
