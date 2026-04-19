"""
Thumbnail Generator - 썸네일 자동 생성

이미지에서 썸네일 생성
"""
import asyncio
import logging
from typing import Optional, Tuple
from pathlib import Path
from PIL import Image


logger = logging.getLogger(__name__)


class ThumbnailGenerator:
    """
    썸네일 생성기

    다양한 크기의 썸네일 자동 생성
    """

    # 기본 썸네일 크기
    DEFAULT_SIZES = {
        "small": (128, 128),
        "medium": (256, 256),
        "large": (512, 512),
    }

    # 썸네일 저장 품질
    DEFAULT_QUALITY = 85

    def __init__(
        self,
        output_dir: str = "data/assets/thumbnails",
        default_size: Tuple[int, int] = (256, 256)
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.default_size = default_size

    async def generate(
        self,
        source_path: str,
        output_filename: str = None,
        size: Tuple[int, int] = None,
        maintain_aspect: bool = True,
        crop_to_square: bool = True
    ) -> Optional[str]:
        """
        썸네일 생성

        Args:
            source_path: 원본 이미지 경로
            output_filename: 출력 파일명 (확장자 제외)
            size: 썸네일 크기 (width, height)
            maintain_aspect: 가로세로 비율 유지
            crop_to_square: 정사각형으로 크롭

        Returns:
            생성된 썸네일 경로 또는 None
        """
        source = Path(source_path)
        if not source.exists():
            logger.error(f"Source image not found: {source_path}")
            return None

        size = size or self.default_size

        # 출력 파일명 결정
        if not output_filename:
            output_filename = source.stem

        # 비동기로 이미지 처리 실행
        loop = asyncio.get_event_loop()
        try:
            thumbnail_path = await loop.run_in_executor(
                None,
                self._generate_sync,
                source,
                output_filename,
                size,
                maintain_aspect,
                crop_to_square
            )
            return thumbnail_path
        except Exception as e:
            logger.error(f"Failed to generate thumbnail: {e}")
            return None

    def _generate_sync(
        self,
        source_path: Path,
        output_filename: str,
        size: Tuple[int, int],
        maintain_aspect: bool,
        crop_to_square: bool
    ) -> str:
        """동기식 썸네일 생성"""
        with Image.open(source_path) as img:
            # RGB로 변환 (투명도 제거)
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # 정사각형 크롭
            if crop_to_square:
                img = self._crop_to_square(img)

            # 리사이즈
            if maintain_aspect:
                img.thumbnail(size, Image.Resampling.LANCZOS)
            else:
                img = img.resize(size, Image.Resampling.LANCZOS)

            # 저장
            output_path = self.output_dir / f"{output_filename}.jpg"
            img.save(output_path, "JPEG", quality=self.DEFAULT_QUALITY, optimize=True)

            logger.info(f"Thumbnail generated: {output_path}")
            return str(output_path)

    def _crop_to_square(self, img: Image.Image) -> Image.Image:
        """이미지를 정사각형으로 크롭 (중앙 기준)"""
        width, height = img.size
        min_dim = min(width, height)

        # 중앙 좌표 계산
        left = (width - min_dim) // 2
        top = (height - min_dim) // 2
        right = left + min_dim
        bottom = top + min_dim

        return img.crop((left, top, right, bottom))

    async def generate_multiple_sizes(
        self,
        source_path: str,
        output_prefix: str = None,
        sizes: dict = None
    ) -> dict:
        """
        여러 크기의 썸네일 생성

        Args:
            source_path: 원본 이미지 경로
            output_prefix: 출력 파일명 접두사
            sizes: 크기 딕셔너리 {"small": (128, 128), ...}

        Returns:
            크기별 생성된 썸네일 경로
        """
        sizes = sizes or self.DEFAULT_SIZES
        source = Path(source_path)

        if not source.exists():
            logger.error(f"Source image not found: {source_path}")
            return {}

        if not output_prefix:
            output_prefix = source.stem

        results = {}
        for size_name, size in sizes.items():
            output_filename = f"{output_prefix}_{size_name}"
            thumbnail_path = await self.generate(
                source_path,
                output_filename,
                size,
                maintain_aspect=True,
                crop_to_square=True
            )
            if thumbnail_path:
                results[size_name] = thumbnail_path

        return results

    async def generate_for_character(
        self,
        source_path: str,
        character_id: str
    ) -> Optional[str]:
        """캐릭터용 썸네일 생성"""
        return await self.generate(
            source_path,
            output_filename=f"char_{character_id}",
            size=(256, 256),
            crop_to_square=True
        )

    async def generate_for_location(
        self,
        source_path: str,
        location_id: str
    ) -> Optional[str]:
        """장소용 썸네일 생성 (가로 형태)"""
        source = Path(source_path)
        if not source.exists():
            return None

        output_filename = f"loc_{location_id}"
        output_path = self.output_dir / f"{output_filename}.jpg"

        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(
                None,
                self._generate_location_thumbnail,
                source_path,
                output_path
            )
        except Exception as e:
            logger.error(f"Failed to generate location thumbnail: {e}")
            return None

    def _generate_location_thumbnail(
        self,
        source_path: str,
        output_path: Path
    ) -> str:
        """장소용 썸네일 생성 (16:9 비율)"""
        with Image.open(source_path) as img:
            # RGB 변환
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # 16:9 비율로 크롭
            width, height = img.size
            target_ratio = 16 / 9

            current_ratio = width / height
            if current_ratio > target_ratio:
                # 가로가 더 김 - 양쪽 자르기
                new_width = int(height * target_ratio)
                left = (width - new_width) // 2
                img = img.crop((left, 0, left + new_width, height))
            else:
                # 세로가 더 김 - 위아래 자르기
                new_height = int(width / target_ratio)
                top = (height - new_height) // 2
                img = img.crop((0, top, width, top + new_height))

            # 리사이즈
            img.thumbnail((512, 288), Image.Resampling.LANCZOS)

            # 저장
            img.save(output_path, "JPEG", quality=self.DEFAULT_QUALITY, optimize=True)

            logger.info(f"Location thumbnail generated: {output_path}")
            return str(output_path)

    async def generate_for_style(
        self,
        source_path: str,
        preset_id: str
    ) -> Optional[str]:
        """스타일 프리셋용 썸네일 생성"""
        return await self.generate(
            source_path,
            output_filename=f"style_{preset_id}",
            size=(256, 256),
            crop_to_square=True
        )

    def get_thumbnail_path(self, asset_id: str, asset_type: str = "char") -> Path:
        """썸네일 경로 조회"""
        prefix_map = {
            "char": "char_",
            "character": "char_",
            "loc": "loc_",
            "location": "loc_",
            "style": "style_",
            "preset": "style_",
        }
        prefix = prefix_map.get(asset_type, "")
        return self.output_dir / f"{prefix}{asset_id}.jpg"

    def thumbnail_exists(self, asset_id: str, asset_type: str = "char") -> bool:
        """썸네일 존재 여부"""
        path = self.get_thumbnail_path(asset_id, asset_type)
        return path.exists()

    async def delete_thumbnail(self, asset_id: str, asset_type: str = "char") -> bool:
        """썸네일 삭제"""
        path = self.get_thumbnail_path(asset_id, asset_type)
        if path.exists():
            path.unlink()
            logger.info(f"Thumbnail deleted: {path}")
            return True
        return False

    async def batch_generate(
        self,
        sources: list,
        asset_type: str = "char"
    ) -> dict:
        """
        여러 이미지 일괄 썸네일 생성

        Args:
            sources: [{"path": "...", "id": "..."}, ...]
            asset_type: 에셋 타입

        Returns:
            {"id": "thumbnail_path", ...}
        """
        results = {}

        for source in sources:
            path = source.get("path")
            asset_id = source.get("id")

            if not path or not asset_id:
                continue

            if asset_type in ("char", "character"):
                thumbnail_path = await self.generate_for_character(path, asset_id)
            elif asset_type in ("loc", "location"):
                thumbnail_path = await self.generate_for_location(path, asset_id)
            elif asset_type in ("style", "preset"):
                thumbnail_path = await self.generate_for_style(path, asset_id)
            else:
                thumbnail_path = await self.generate(path, asset_id)

            if thumbnail_path:
                results[asset_id] = thumbnail_path

        return results


# ============================================================
# 싱글톤
# ============================================================

_thumbnail_generator: Optional[ThumbnailGenerator] = None


def get_thumbnail_generator() -> ThumbnailGenerator:
    """썸네일 생성기 싱글톤"""
    global _thumbnail_generator
    if _thumbnail_generator is None:
        _thumbnail_generator = ThumbnailGenerator()
    return _thumbnail_generator
