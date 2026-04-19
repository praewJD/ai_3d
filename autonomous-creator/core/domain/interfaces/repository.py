"""
Repository Interfaces

데이터 저장소 추상화
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from ..entities.story import Story
from ..entities.preset import StylePreset
from ..entities.task import GenerationTask


class IStoryRepository(ABC):
    """
    스토리 저장소 인터페이스
    """

    @abstractmethod
    async def save(self, story: Story) -> Story:
        """
        스토리 저장

        Args:
            story: 저장할 스토리

        Returns:
            저장된 스토리 (ID 포함)
        """
        pass

    @abstractmethod
    async def find_by_id(self, id: str) -> Optional[Story]:
        """
        ID로 스토리 조회

        Args:
            id: 스토리 ID

        Returns:
            스토리 또는 None
        """
        pass

    @abstractmethod
    async def find_all(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Story]:
        """
        모든 스토리 조회

        Args:
            limit: 최대 개수
            offset: 건너뛸 개수

        Returns:
            스토리 목록
        """
        pass

    @abstractmethod
    async def find_by_language(self, language: str) -> List[Story]:
        """
        언어별 스토리 조회

        Args:
            language: 언어 코드

        Returns:
            해당 언어의 스토리 목록
        """
        pass

    @abstractmethod
    async def delete(self, id: str) -> bool:
        """
        스토리 삭제

        Args:
            id: 스토리 ID

        Returns:
            삭제 성공 여부
        """
        pass


class IPresetRepository(ABC):
    """
    스타일 프리셋 저장소 인터페이스
    """

    @abstractmethod
    async def save(self, preset: StylePreset) -> StylePreset:
        """프리셋 저장"""
        pass

    @abstractmethod
    async def find_by_id(self, id: str) -> Optional[StylePreset]:
        """ID로 프리셋 조회"""
        pass

    @abstractmethod
    async def find_by_name(self, name: str) -> Optional[StylePreset]:
        """이름으로 프리셋 조회"""
        pass

    @abstractmethod
    async def find_all(self) -> List[StylePreset]:
        """모든 프리셋 조회"""
        pass

    @abstractmethod
    async def find_defaults(self) -> List[StylePreset]:
        """기본 프리셋 목록 조회"""
        pass

    @abstractmethod
    async def delete(self, id: str) -> bool:
        """프리셋 삭제"""
        pass


class ITaskRepository(ABC):
    """
    작업 저장소 인터페이스
    """

    @abstractmethod
    async def save(self, task: GenerationTask) -> GenerationTask:
        """작업 저장"""
        pass

    @abstractmethod
    async def find_by_id(self, id: str) -> Optional[GenerationTask]:
        """ID로 작업 조회"""
        pass

    @abstractmethod
    async def find_by_story_id(self, story_id: str) -> Optional[GenerationTask]:
        """스토리 ID로 작업 조회"""
        pass

    @abstractmethod
    async def find_pending(self) -> List[GenerationTask]:
        """대기 중인 작업 목록"""
        pass

    @abstractmethod
    async def find_running(self) -> List[GenerationTask]:
        """실행 중인 작업 목록"""
        pass

    @abstractmethod
    async def find_recent(self, limit: int = 50) -> List[GenerationTask]:
        """최근 작업 목록"""
        pass

    @abstractmethod
    async def delete(self, id: str) -> bool:
        """작업 삭제"""
        pass
