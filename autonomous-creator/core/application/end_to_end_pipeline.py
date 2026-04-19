"""
End-to-End Pipeline - 데이터 중심 생성 엔진 v2

전체 파이프라인 통합:
Story Text → SceneGraph → Prompts -> Images
"""
import asyncio
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import logging

from core.domain.entities.scene.scene_graph import (
    SceneGraph, SceneNode, SceneStyle, CharacterIdentity
)
from infrastructure.scene.scene_compiler import SceneCompiler
from infrastructure.validation.rule_engine import RuleEngine, ValidationResult
from infrastructure.prompt.prompt_orchestrator import PromptOrchestrator
from infrastructure.style.style_manager import StyleManager
from infrastructure.storage.execution_log import (
    FileProjectRepository, RunResult, SceneOutput
)

# 기존 구현 사용 (로컬 모델)
from infrastructure.image.sd35_generator import SD35Generator
from infrastructure.tts.factory import TTSFactory
from core.domain.entities.audio import VoiceSettings
from core.domain.entities.preset import StylePreset

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """파이프라인 설정"""
    output_dir: str = "outputs"
    language: str = "th"  # 태국어 기본
    style_strategy: str = "hybrid"
    max_concurrent_images: int = 3
    enable_cache: bool = True
    enable_validation: bool = True


@dataclass
class PipelineResult:
    """파이프라인 실행 결과"""
    success: bool
    story_id: str
    scene_graph: Optional[SceneGraph] = None
    image_paths: List[Path] = field(default_factory=list)
    audio_paths: List[Path] = field(default_factory=list)
    total_time_seconds: float = 0.0
    error_message: str = ""
    validation_errors: List[str] = field(default_factory=list)


class EndToEndPipeline:
    """
    End-to-End 영상 생성 파이프라인

    데이터 중심 아키텍처:
    1. Story Text → SceneGraph (SceneCompiler)
    2. SceneGraph → Prompts (PromptOrchestrator)
    3. Prompts → Images (SD35Generator)

    특징:
    - 모든 단계가 데이터(SceneGraph)를 기반으로 동작
    - LLM은 컴파일 단계에서만 사용
    - 이후는 deterministic 변환
    """

    def __init__(
        self,
        llm_provider=None,
        config: PipelineConfig = None
    ):
        self.llm_provider = llm_provider
        self.config = config or PipelineConfig()

        # 컴포넌트 초기화
        self.compiler = SceneCompiler(llm_provider=llm_provider)
        self.rule_engine = RuleEngine()
        self.prompt_orchestrator = PromptOrchestrator()
        self.style_manager = StyleManager(strategy=self.config.style_strategy)
        self.repository = FileProjectRepository(base_path=self.config.output_dir)

        # 기존 구현 사용 (지연 초기화)
        self._image_generator = None
        self._tts_engine = None

        # 진행 콜백
        self._progress_callback: Optional[Callable] = None

    @property
    def image_generator(self):
        """기존 SD35Generator 사용 (로컬 모델)"""
        if self._image_generator is None:
            self._image_generator = SD35Generator()
        return self._image_generator

    @property
    def tts_engine(self):
        """기존 TTSFactory 사용 (언어 자동 선택)"""
        if self._tts_engine is None:
            self._tts_engine = TTSFactory.create(self.config.language)
        return self._tts_engine

    def set_progress_callback(self, callback: Callable) -> None:
        """진행 상황 콜백 설정"""
        self._progress_callback = callback

    async def _report_progress(self, step: str, progress: int, details: str = "") -> None:
        """진행 상황 보고"""
        logger.info(f"[{progress}%] {step}: {details}")
        if self._progress_callback:
            await self._progress_callback(step, progress, details)

    async def run(
        self,
        story_text: str,
        story_id: str = None,
        title: str = "",
        art_style: str = "disney_3d"
    ) -> PipelineResult:
        """
        전체 파이프라인 실행

        Args:
            story_text: 스토리 텍스트
            story_id: 스토리 ID (없으면 자동 생성)
            title: 제목
            art_style: 아트 스타일

        Returns:
            PipelineResult
        """
        start_time = datetime.now()
        story_id = story_id or f"story_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        result = PipelineResult(
            success=False,
            story_id=story_id
        )

        try:
            # ========================================
            # Phase 1: SceneGraph 생성 (LLM 필요)
            # ========================================
            await self._report_progress("COMPILER", 5, "장면 분석 중...")

            scene_graph = await self.compiler.compile(
                story_text=story_text,
                story_id=story_id,
                title=title,
                art_style=art_style
            )

            if not scene_graph or not scene_graph.scenes:
                raise ValueError("SceneGraph 생성 실패: 장면이 없습니다")

            result.scene_graph = scene_graph
            await self._report_progress("COMPILER", 15, f"{len(scene_graph.scenes)}개 장면 생성")

            # ========================================
            # Phase 2: 검증 및 자동 수정
            # ========================================
            if self.config.enable_validation:
                await self._report_progress("VALIDATION", 20, "규칙 검증 중...")

                validation = self.rule_engine.validate(scene_graph)

                if not validation.is_valid:
                    result.validation_errors = validation.errors
                    logger.warning(f"검증 경고: {validation.warnings}")

                    # 자동 수정 시도
                    if validation.can_auto_fix:
                        scene_graph, fixes = self.rule_engine.auto_fix(scene_graph)
                        await self._report_progress("VALIDATION", 25, f"{fixes}개 자동 수정")
                        result.scene_graph = scene_graph

            # ========================================
            # Phase 3: 스타일 적용
            # ========================================
            await self._report_progress("STYLE", 30, "스타일 적용 중...")

            self.style_manager.apply_to_scene_graph(scene_graph)
            await self._report_progress("STYLE", 35, "스타일 적용 완료")

            # ========================================
            # Phase 4: 프롬프트 생성
            # ========================================
            await self._report_progress("PROMPT", 40, "프롬프트 생성 중...")

            for scene in scene_graph.scenes:
                image_bundle = self.prompt_orchestrator.build_image_prompt(scene)
                scene._image_prompt = image_bundle.positive

            await self._report_progress("PROMPT", 45, "프롬프트 생성 완료")

            # ========================================
            # Phase 5: 이미지 생성 (기존 SD35Generator)
            # ========================================
            await self._report_progress("IMAGE", 50, "이미지 생성 중...")

            # 출력 디렉토리 준비
            image_dir = Path(self.config.output_dir) / story_id / "images"
            image_dir.mkdir(parents=True, exist_ok=True)

            # 스타일 프리셋
            preset = StylePreset.create_default()

            for i, scene in enumerate(scene_graph.scenes):
                image_path = str(image_dir / f"scene_{i:03d}.png")
                prompt = getattr(scene, '_image_prompt', scene.description)

                await self.image_generator.generate(
                    prompt=prompt,
                    preset=preset,
                    output_path=image_path
                )
                result.image_paths.append(Path(image_path))

            await self._report_progress("IMAGE", 80, f"{len(result.image_paths)}개 이미지 생성")

            # ========================================
            # Phase 6: TTS 생성 (기존 TTSFactory)
            # ========================================
            await self._report_progress("TTS", 85, "음성 생성 중...")

            audio_dir = Path(self.config.output_dir) / story_id / "audio"
            audio_dir.mkdir(parents=True, exist_ok=True)

            voice = VoiceSettings(language=self.config.language)

            for i, scene in enumerate(scene_graph.scenes):
                # 대사 + 나레이션
                text = ""
                if scene.dialogue:
                    text = " ".join([d.text for d in scene.dialogue])
                if scene.narration:
                    text = f"{text} {scene.narration}".strip()

                if text:
                    audio_path = str(audio_dir / f"scene_{i:03d}.wav")
                    await self.tts_engine.generate(text, voice, audio_path)
                    result.audio_paths.append(Path(audio_path))

            await self._report_progress("TTS", 95, f"{len(result.audio_paths)}개 음성 생성")

            # ========================================
            # 완료
            # ========================================
            result.success = True
            result.total_time_seconds = (datetime.now() - start_time).total_seconds()

            await self._report_progress("COMPLETE", 100, f"완료! {result.total_time_seconds:.1f}초")

            return result

        except Exception as e:
            logger.exception("Pipeline execution failed")
            result.error_message = str(e)
            result.total_time_seconds = (datetime.now() - start_time).total_seconds()
            return result

    async def run_from_scene_graph(
        self,
        scene_graph: SceneGraph
    ) -> PipelineResult:
        """
        기존 SceneGraph에서 실행 (컴파일 단계 건너뛰기)
        """
        result = PipelineResult(
            success=False,
            story_id=scene_graph.story_id
        )
        result.scene_graph = scene_graph
        start_time = datetime.now()

        try:
            # 검증
            if self.config.enable_validation:
                validation = self.rule_engine.validate(scene_graph)
                if not validation.is_valid and validation.can_auto_fix:
                    scene_graph, _ = self.rule_engine.auto_fix(scene_graph)
                    result.scene_graph = scene_graph

            # 스타일 적용
            self.style_manager.apply_to_scene_graph(scene_graph)

            # 프롬프트 생성
            for scene in scene_graph.scenes:
                image_bundle = self.prompt_orchestrator.build_image_prompt(scene)
                scene._image_prompt = image_bundle.positive

            # 이미지 생성
            image_dir = Path(self.config.output_dir) / scene_graph.story_id / "images"
            image_dir.mkdir(parents=True, exist_ok=True)
            preset = StylePreset.create_default()

            for i, scene in enumerate(scene_graph.scenes):
                image_path = str(image_dir / f"scene_{i:03d}.png")
                await self.image_generator.generate(
                    prompt=getattr(scene, '_image_prompt', scene.description),
                    preset=preset,
                    output_path=image_path
                )
                result.image_paths.append(Path(image_path))

            result.success = True
            result.total_time_seconds = (datetime.now() - start_time).total_seconds()
            return result

        except Exception as e:
            result.error_message = str(e)
            return result

    async def estimate_cost(self, scene_graph: SceneGraph) -> Dict[str, float]:
        """예상 비용 계산 (로컬 모델 사용으로 무료)"""
        num_scenes = len(scene_graph.scenes)
        return {
            "image_cost_usd": 0.0,  # 로컬 모델 무료
            "tts_cost_usd": 0.0,  # 로컬 무료
            "total_cost_usd": 0.0,
            "num_scenes": num_scenes
        }


# 편의 함수
async def create_video(
    story_text: str,
    language: str = "th",
    config: PipelineConfig = None
) -> PipelineResult:
    """
    스토리 텍스트로 영상 생성 (간편 함수)
    """
    config = config or PipelineConfig(language=language)
    pipeline = EndToEndPipeline(config=config)
    return await pipeline.run(story_text)
