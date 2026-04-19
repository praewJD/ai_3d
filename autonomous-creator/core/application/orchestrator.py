"""
Pipeline Orchestrator

전체 영상 생성 파이프라인 조율

v2.1: 체크포인트 + 프롬프트 생성기 통합
"""
import asyncio
from typing import Optional, Callable, List
from datetime import datetime
from pathlib import Path

from core.domain.entities.story import Story, Scene, Script
from core.domain.entities.video import Video, VideoSegment
from core.domain.entities.task import GenerationTask, TaskStatus, TaskStep
from core.domain.entities.audio import VoiceSettings
from core.domain.entities.preset import StylePreset
from core.domain.entities.character import Character
from core.domain.services.video_validator import VideoValidator
from infrastructure.tts.factory import TTSFactory
from infrastructure.image.style_consistency import StyleConsistencyManager
from infrastructure.video.hybrid_manager import HybridVideoManager
from infrastructure.persistence.repositories.story_repo import StoryRepository
from infrastructure.persistence.repositories.task_repo import TaskRepository

# [신규] 캐릭터 추출 모듈
from infrastructure.script_parser import CharacterExtractor, SceneParser, LLMExtractor
from infrastructure.prompt import PromptBuilder, CharacterTemplate, LocationDB
from infrastructure.prompt.prompt_generator import PromptGenerator, GeneratedPrompts
from infrastructure.image.ip_adapter_client import IPAdapterClient, IPAdapterConfig
from infrastructure.image.character_cache import CharacterCache

# [v2.1] 체크포인트 매니저
from core.application.checkpoint_manager import CheckpointManager, CheckpointState, PipelineStep

# [v2.2] RuleEngine 검증 (선택적)
try:
    from infrastructure.validation.rule_engine import RuleEngine
    _RULE_ENGINE_AVAILABLE = True
except ImportError:
    _RULE_ENGINE_AVAILABLE = False
    RuleEngine = None

from config.settings import get_settings

# 타입 힌트용 import
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from infrastructure.video.luma_provider import LumaProvider


class PipelineOrchestrator:
    """
    영상 생성 파이프라인 오케스트레이터

    파이프라인 v2.1:
    0. 캐릭터 추출
    1. 스크립트 생성 (AI)
    2. 프롬프트 생성 (AI) ← NEW
    3. 오디오 생성 (TTS)
    4. 이미지 생성 (SD 3.5 + IP-Adapter)
    5. 비디오 생성 (Luma API / SVD + MoviePy)
    6. 최종 합성

    v2.1 새 기능:
    - 체크포인트 저장/복구
    - AI 기반 프롬프트 생성
    """

    def __init__(
        self,
        story_repo: StoryRepository,
        task_repo: TaskRepository,
        ai_provider=None,
        enable_checkpoint: bool = True
    ):
        self.story_repo = story_repo
        self.task_repo = task_repo
        self.ai_provider = ai_provider
        self.enable_checkpoint = enable_checkpoint

        # 컴포넌트 초기화
        self.style_manager = StyleConsistencyManager()
        self.video_manager = HybridVideoManager()

        # [신규] 캐릭터 관련 컴포넌트
        self.character_extractor = CharacterExtractor()
        self.scene_parser = SceneParser()
        self.prompt_builder = PromptBuilder(
            CharacterTemplate(),
            LocationDB()
        )
        self.character_cache = CharacterCache()

        # [v2.1] AI 프롬프트 생성기
        self._prompt_generator: Optional[PromptGenerator] = None

        # [v2.1] 체크포인트 매니저
        self.checkpoint_manager = CheckpointManager() if enable_checkpoint else None

        # [v2.2] RuleEngine (지연 초기화)
        self._rule_engine: Optional["RuleEngine"] = None

        # [신규] IP-Adapter (지연 초기화)
        self._ip_adapter: Optional[IPAdapterClient] = None
        self._characters: list[Character] = []

        # 설정
        self.settings = get_settings()

        # 진행 콜백
        self._progress_callback: Optional[Callable] = None

    @property
    def prompt_generator(self) -> PromptGenerator:
        """프롬프트 생성기 (지연 초기화)"""
        if self._prompt_generator is None and self.ai_provider:
            self._prompt_generator = PromptGenerator(
                llm_provider=self.ai_provider,
                style_preset=StylePreset.create_default()
            )
        return self._prompt_generator

    @property
    def rule_engine(self) -> Optional["RuleEngine"]:
        """RuleEngine (지연 초기화, 선택적)"""
        if self._rule_engine is None and _RULE_ENGINE_AVAILABLE:
            self._rule_engine = RuleEngine()
        return self._rule_engine

    def set_progress_callback(self, callback: Callable) -> None:
        """진행 상황 콜백 설정"""
        self._progress_callback = callback

    async def _report_progress(
        self,
        task: GenerationTask,
        progress: int,
        step: TaskStep
    ) -> None:
        """진행 상황 보고"""
        task.update_progress(progress, step)

        if self._progress_callback:
            await self._progress_callback(task)

        await self.task_repo.save(task)

    async def generate_video(
        self,
        story: Story,
        preset: Optional[StylePreset] = None,
        output_dir: str = "outputs"
    ) -> GenerationTask:
        """
        스토리 → 영상 전체 파이프라인 실행

        Args:
            story: 스토리 엔티티
            preset: 스타일 프리셋
            output_dir: 출력 디렉토리

        Returns:
            완료된 작업
        """
        # 작업 생성
        task = GenerationTask(
            story_id=story.id,
            status=TaskStatus.PENDING,
            created_at=datetime.now()
        )
        await self.task_repo.save(task)

        try:
            # 작업 시작
            task.start()
            await self._report_progress(task, 0, TaskStep.INIT)

            # 출력 디렉토리 준비
            output_path = Path(output_dir) / story.id
            output_path.mkdir(parents=True, exist_ok=True)

            # [신규] Step 0: 캐릭터 추출 (5%)
            await self._report_progress(task, 3, TaskStep.INIT)
            self._characters = await self._extract_characters(story)
            await self._report_progress(task, 5, TaskStep.INIT)

            # [신규] IP-Adapter 준비 (캐릭터 있을 때)
            if self._characters:
                await self._prepare_character_references(
                    self._characters,
                    str(output_path / "character_refs")
                )

            # Step 1: 스크립트 생성 (10%)
            await self._report_progress(task, 10, TaskStep.SCRIPT_GENERATION)
            script = await self._generate_script(story)
            story.script = script
            await self.story_repo.save(story)

            # [v2.2] SceneGraph 검증 (선택적)
            if self.rule_engine and hasattr(script, 'to_scene_graph'):
                try:
                    scene_graph = script.to_scene_graph()
                    scene_graph, validation = self.rule_engine.validate_and_fix(scene_graph)
                    if validation.fixed_count > 0:
                        print(f"[RuleEngine] {validation.fixed_count}개 자동 수정 완료")
                    if validation.warnings:
                        for warning in validation.warnings[:5]:  # 최대 5개만 표시
                            print(f"[RuleEngine] Warning: {warning}")
                    # 수정된 SceneGraph를 스크립트에 반영
                    if validation.fixed_count > 0:
                        script = self._apply_scene_graph_to_script(script, scene_graph)
                except Exception as e:
                    print(f"[RuleEngine] 검증 스킵: {e}")

            # Step 2: 오디오 생성 (30%)
            await self._report_progress(task, 20, TaskStep.AUDIO_GENERATION)
            audio_paths = await self._generate_audio(
                script,
                story.language,
                str(output_path / "audio")
            )
            await self._report_progress(task, 30, TaskStep.AUDIO_GENERATION)

            # Step 3: 이미지 생성 (60%)
            await self._report_progress(task, 40, TaskStep.IMAGE_GENERATION)
            image_paths = await self._generate_images(
                script,
                preset or StylePreset.create_default(),
                str(output_path / "images")
            )
            await self._report_progress(task, 60, TaskStep.IMAGE_GENERATION)

            # Step 4: 비디오 생성 (90%)
            await self._report_progress(task, 70, TaskStep.VIDEO_GENERATION)
            segments = await self._generate_video_segments(
                script.scenes,
                image_paths,
                audio_paths,
                str(output_path / "segments")
            )
            await self._report_progress(task, 80, TaskStep.VIDEO_GENERATION)

            # Step 5: 최종 합성 (95%)
            await self._report_progress(task, 85, TaskStep.COMPOSITION)
            final_video = await self._compose_final(
                segments,
                str(output_path / "videos" / "final.mp4")
            )
            await self._report_progress(task, 95, TaskStep.FINALIZING)

            # Step 6: 영상 검증 (98%)
            validator = VideoValidator()
            validation = await validator.validate(final_video.output_path)
            if not validation.is_valid:
                task.fail(f"영상 검증 실패: {validation.errors}")
                await self.task_repo.save(task)
                raise ValueError(f"Video validation failed: {validation.errors}")
            if validation.warnings:
                for warning in validation.warnings:
                    print(f"Warning: {warning}")

            # 완료
            task.output_paths = [final_video.output_path]
            task.complete()
            await self.task_repo.save(task)

            return task

        except Exception as e:
            task.fail(str(e))
            await self.task_repo.save(task)
            raise

    # [신규] 캐릭터 추출 메서드
    async def _extract_characters(self, story: Story) -> list[Character]:
        """
        스크립트에서 캐릭터 추출

        로컬 규칙 → LLM 백업
        """
        content = story.content or ""
        language = story.language or "th"

        # 1. 로컬 규칙으로 추출 시도
        characters = self.character_extractor.extract(content, language)

        # 2. 캐릭터 섹션에서도 추출
        section_chars = self.character_extractor.extract_from_character_section(
            content, language
        )

        # 중복 제거하여 합치기
        char_names = {c.name for c in characters}
        for char in section_chars:
            if char.name not in char_names:
                characters.append(char)
                char_names.add(char.name)

        # 3. 복잡한 스크립트면 LLM 사용
        if not characters and len(content) > 500:
            try:
                # LLM 추출기는 필요시에만 import
                from infrastructure.script_parser.llm_extractor import LLMExtractor
                llm_extractor = LLMExtractor(self.settings.claude_api_key)
                characters = await llm_extractor.extract_characters_only(content, language)
            except Exception as e:
                print(f"LLM 캐릭터 추출 실패: {e}")

        print(f"추출된 캐릭터: {len(characters)}명")
        for char in characters:
            print(f"  - {char.name} ({char.type.value})")

        return characters

    async def _prepare_character_references(
        self,
        characters: list[Character],
        output_dir: str
    ) -> None:
        """
        캐릭터 기준 이미지 준비

        캐시 확인 → 없으면 생성
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        for char in characters:
            # 캐시 확인
            cached_path = self.character_cache.get(char.id)
            if cached_path:
                char.reference_image_path = cached_path
                print(f"  [캐시] {char.name}: {cached_path}")
                continue

            # 기준 이미지 생성 필요
            # (실제 생성은 _generate_images에서 수행)
            print(f"  [신규] {char.name}: 기준 이미지 필요")

    async def _generate_script(self, story: Story) -> Script:
        """AI로 스크립트 생성"""
        if self.ai_provider:
            # AI Provider 사용
            return await self.ai_provider.generate_script(story)
        else:
            # 기본: 스토리를 단일 장면으로
            return Script(
                scenes=[
                    Scene(
                        description=story.title,
                        narration=story.content,
                        image_prompt=story.content,
                        duration=5.0,
                        order=0
                    )
                ],
                total_duration=5.0,
                language=story.language
            )

    def _apply_scene_graph_to_script(self, script: Script, scene_graph) -> Script:
        """SceneGraph 수정사항을 Script에 반영"""
        try:
            scenes = scene_graph.get_ordered_scenes()
            for i, scene_node in enumerate(scenes):
                if i < len(script.scenes):
                    # duration 수정 반영
                    script.scenes[i].duration = scene_node.duration_seconds
        except Exception as e:
            print(f"[RuleEngine] Script 반영 실패: {e}")
        return script

    async def _generate_audio(
        self,
        script: Script,
        language: str,
        output_dir: str
    ) -> list[str]:
        """장면별 오디오 생성"""
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        tts = TTSFactory.create(language)
        audio_paths = []

        voice = VoiceSettings(language=language)

        for i, scene in enumerate(script.scenes):
            output_path = f"{output_dir}/scene_{i:03d}.wav"
            await tts.generate(scene.narration, voice, output_path)
            audio_paths.append(output_path)

        return audio_paths

    async def _generate_images(
        self,
        script: Script,
        preset: StylePreset,
        output_dir: str
    ) -> list[str]:
        """장면별 이미지 생성 (일관성 유지)"""
        await self.style_manager.initialize()
        return await self.style_manager.generate_consistent_images(
            scenes=script.scenes,
            preset=preset,
            output_dir=output_dir
        )

    async def _generate_video_segments(
        self,
        scenes: list[Scene],
        image_paths: list[str],
        audio_paths: list[str],
        output_dir: str
    ) -> list[VideoSegment]:
        """비디오 세그먼트 생성 (SVD + Ken Burns)"""
        return await self.video_manager.generate_all_segments(
            scenes=scenes,
            image_paths=image_paths,
            audio_paths=audio_paths,
            output_dir=output_dir
        )

    async def _compose_final(
        self,
        segments: list[VideoSegment],
        output_path: str
    ) -> Video:
        """최종 영상 합성"""
        return await self.video_manager.create_final_video(
            segments=segments,
            output_path=output_path
        )

    # ============================================================
    # [v2.1] 체크포인트 지원 메서드
    # ============================================================

    async def generate_video_with_resume(
        self,
        story: Story,
        preset: Optional[StylePreset] = None,
        output_dir: str = "outputs",
        force_restart: bool = False
    ) -> GenerationTask:
        """
        체크포인트 기반 영상 생성 (재개 가능)

        Args:
            story: 스토리 엔티티
            preset: 스타일 프리셋
            output_dir: 출력 디렉토리
            force_restart: 처음부터 다시 시작

        Returns:
            완료된 작업
        """
        if not self.checkpoint_manager:
            # 체크포인트 비활성화면 일반 실행
            return await self.generate_video(story, preset, output_dir)

        # 기존 체크포인트 확인
        state = None if force_restart else await self.checkpoint_manager.load(story.id)

        if state and state.current_step != PipelineStep.COMPLETED:
            print(f"[Resume] 이전 작업 발견: {state.current_step}")
            return await self._resume_from_checkpoint(story, state, preset, output_dir)

        # 새로 시작
        state = self.checkpoint_manager.create_initial_state(story.id)
        await self.checkpoint_manager.save(state)

        return await self._run_pipeline_with_checkpoint(story, state, preset, output_dir)

    async def _resume_from_checkpoint(
        self,
        story: Story,
        state: CheckpointState,
        preset: Optional[StylePreset],
        output_dir: str
    ) -> GenerationTask:
        """체크포인트에서 재개"""
        print(f"[Resume] {state.error_step or state.current_step} 단계부터 재개")

        # 재시도 횟수 확인
        if state.retry_count >= CheckpointManager.MAX_RETRY_COUNT:
            raise RuntimeError(f"최대 재시도 횟수 초과 ({state.retry_count})")

        return await self._run_pipeline_with_checkpoint(story, state, preset, output_dir)

    async def _run_pipeline_with_checkpoint(
        self,
        story: Story,
        state: CheckpointState,
        preset: Optional[StylePreset],
        output_dir: str
    ) -> GenerationTask:
        """체크포인트 저장하며 파이프라인 실행"""

        # 작업 생성
        task = GenerationTask(
            story_id=story.id,
            status=TaskStatus.PENDING,
            created_at=datetime.now()
        )
        await self.task_repo.save(task)

        output_path = Path(output_dir) / story.id
        output_path.mkdir(parents=True, exist_ok=True)

        try:
            task.start()

            # Step 0: 캐릭터 추출
            if not state.characters:
                await self._report_progress(task, 3, TaskStep.INIT)
                self._characters = await self._extract_characters(story)
                state = await self.checkpoint_manager.record_success(
                    state, PipelineStep.CHARACTER_EXTRACTION, self._characters
                )
            else:
                # 캐릭터 복원
                from core.domain.entities.character import Character
                self._characters = [Character(**c) for c in state.characters]
                print(f"[Checkpoint] 캐릭터 {len(self._characters)}명 복원")

            # Step 1: 스크립트 생성
            if not state.script:
                await self._report_progress(task, 10, TaskStep.SCRIPT_GENERATION)
                script = await self._generate_script(story)
                state = await self.checkpoint_manager.record_success(
                    state, PipelineStep.SCRIPT_GENERATION, script
                )
            else:
                script = Script(**state.script)
                print(f"[Checkpoint] 스크립트 복원 ({len(script.scenes)}장면)")

            # Step 2: [NEW] AI 프롬프트 생성
            if not state.prompts and self.prompt_generator:
                await self._report_progress(task, 15, TaskStep.INIT)
                generated = await self.prompt_generator.generate_all_prompts(story)
                state = await self.checkpoint_manager.record_success(
                    state, PipelineStep.PROMPT_GENERATION,
                    [p.__dict__ for p in generated]
                )
                # 스크립트에 프롬프트 적용
                for i, prompt in enumerate(generated):
                    if i < len(script.scenes):
                        script.scenes[i].image_prompt = prompt.image_prompt
                print(f"[Checkpoint] AI 프롬프트 {len(generated)}개 생성")
            elif state.prompts:
                print(f"[Checkpoint] 프롬프트 {len(state.prompts)}개 복원")

            # Step 3: 오디오 생성
            if not state.audio_paths:
                await self._report_progress(task, 20, TaskStep.AUDIO_GENERATION)
                audio_paths = await self._generate_audio(
                    script, story.language, str(output_path / "audio")
                )
                state = await self.checkpoint_manager.record_success(
                    state, PipelineStep.AUDIO_GENERATION, audio_paths
                )
            else:
                audio_paths = state.audio_paths
                print(f"[Checkpoint] 오디오 {len(audio_paths)}개 복원")

            # Step 4: 이미지 생성
            if not state.image_paths:
                await self._report_progress(task, 40, TaskStep.IMAGE_GENERATION)
                image_paths = await self._generate_images(
                    script,
                    preset or StylePreset.create_default(),
                    str(output_path / "images")
                )
                state = await self.checkpoint_manager.record_success(
                    state, PipelineStep.IMAGE_GENERATION, image_paths
                )
            else:
                image_paths = state.image_paths
                print(f"[Checkpoint] 이미지 {len(image_paths)}개 복원")

            # Step 5: 비디오 생성
            if not state.video_paths:
                await self._report_progress(task, 70, TaskStep.VIDEO_GENERATION)
                segments = await self._generate_video_segments(
                    script.scenes, image_paths, audio_paths,
                    str(output_path / "segments")
                )
                video_paths = [s.video_path for s in segments if s.video_path]
                state = await self.checkpoint_manager.record_success(
                    state, PipelineStep.VIDEO_GENERATION, video_paths
                )
            else:
                video_paths = state.video_paths
                print(f"[Checkpoint] 비디오 {len(video_paths)}개 복원")

            # Step 6: 최종 합성
            if not state.final_video:
                await self._report_progress(task, 85, TaskStep.COMPOSITION)
                final_video = await self._compose_final(
                    [VideoSegment(video_path=p) for p in video_paths if p],
                    str(output_path / "videos" / "final.mp4")
                )
                state = await self.checkpoint_manager.record_success(
                    state, PipelineStep.COMPOSITION, final_video.output_path
                )
            else:
                final_video = Video(output_path=state.final_video)
                print(f"[Checkpoint] 최종 영상 복원")

            # 완료
            state.current_step = PipelineStep.COMPLETED
            state.progress = 100
            await self.checkpoint_manager.save(state)

            task.output_paths = [final_video.output_path]
            task.complete()
            await self.task_repo.save(task)

            return task

        except Exception as e:
            state = await self.checkpoint_manager.record_failure(state, e)
            task.fail(str(e))
            await self.task_repo.save(task)
            raise
