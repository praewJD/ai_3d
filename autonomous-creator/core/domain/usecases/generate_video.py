"""
Generate Video Use Case

영상 생성 비즈니스 로직을 캡슐화
"""
from typing import Optional
from dataclasses import dataclass
from enum import Enum

from ..entities.story import Story
from ..entities.video import Video, VideoQuality
from ..entities.task import GenerationTask, TaskStatus
from ..interfaces.repository import IStoryRepository, ITaskRepository
from ..interfaces.video_composer import IVideoComposer


class GenerationMode(str, Enum):
    """영상 생성 모드"""
    FULL = "full"           # 전체 파이프라인
    IMAGES_ONLY = "images"  # 이미지만 생성
    VIDEO_ONLY = "video"    # 영상만 생성 (기존 이미지 사용)


@dataclass
class GenerateVideoRequest:
    """영상 생성 요청"""
    story_id: str
    quality: VideoQuality = VideoQuality.FHD
    mode: GenerationMode = GenerationMode.FULL
    use_svd: bool = True
    style_preset_id: Optional[str] = None


@dataclass
class GenerateVideoResponse:
    """영상 생성 응답"""
    task_id: str
    success: bool
    message: str = ""
    video: Optional[Video] = None


class GenerateVideoUseCase:
    """
    영상 생성 유스케이스

    Responsibility:
    - 스토리 조회 및 검증
    - 생성 태스크 생성
    - 파이프라인 실행 트리거
    """

    def __init__(
        self,
        story_repository: IStoryRepository,
        task_repository: ITaskRepository,
        video_composer: IVideoComposer
    ):
        self._story_repository = story_repository
        self._task_repository = task_repository
        self._video_composer = video_composer

    async def execute(self, request: GenerateVideoRequest) -> GenerateVideoResponse:
        """
        영상 생성 실행

        Args:
            request: 영상 생성 요청 데이터

        Returns:
            GenerateVideoResponse: 생성 결과
        """
        # 1. 스토리 조회
        story = await self._story_repository.find_by_id(request.story_id)
        if not story:
            return GenerateVideoResponse(
                task_id="",
                success=False,
                message=f"스토리를 찾을 수 없습니다: {request.story_id}"
            )

        # 2. 스토리 검증
        if not story.scenes:
            return GenerateVideoResponse(
                task_id="",
                success=False,
                message="스토리에 장면이 없습니다."
            )

        # 3. 태스크 생성
        task = GenerationTask(
            story_id=request.story_id,
            quality=request.quality,
            use_svd=request.use_svd,
            style_preset_id=request.style_preset_id
        )
        task = await self._task_repository.save(task)

        # 4. 파이프라인 실행 (비동기)
        try:
            video = await self._run_pipeline(task, story)
            task.status = TaskStatus.COMPLETED
            task.video_path = video.file_path
            await self._task_repository.save(task)

            return GenerateVideoResponse(
                task_id=task.id,
                success=True,
                message="영상 생성 완료",
                video=video
            )
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            await self._task_repository.save(task)

            return GenerateVideoResponse(
                task_id=task.id,
                success=False,
                message=f"영상 생성 실패: {str(e)}"
            )

    async def _run_pipeline(self, task: GenerationTask, story: Story) -> Video:
        """
        영상 생성 파이프라인 실행

        Args:
            task: 생성 태스크
            story: 스토리 엔티티

        Returns:
            Video: 생성된 영상
        """
        # 1. 이미지 생성
        # 2. 내레이션 생성
        # 3. 영상 합성
        # 4. 결과 반환

        video = await self._video_composer.compose_video(
            story=story,
            quality=task.quality,
            use_svd=task.use_svd
        )

        return video
