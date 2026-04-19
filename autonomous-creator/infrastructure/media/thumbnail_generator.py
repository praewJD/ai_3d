"""
Thumbnail Generator

Extracts and generates thumbnails from video with face detection
and multiple platform size exports.
"""
import os
import json
import logging
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import random
import math

# Video processing
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# Image processing
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Numpy for array operations
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


logger = logging.getLogger(__name__)


class ThumbnailSize(str, Enum):
    """Standard thumbnail sizes for different platforms"""
    # YouTube
    YOUTUBE = "youtube"  # 1280x720
    YOUTUBE_MOBILE = "youtube_mobile"  # 480x270

    # TikTok
    TIKTOK = "tiktok"  # 1080x1920 (9:16 vertical)

    # Instagram
    INSTAGRAM_SQUARE = "instagram_square"  # 1080x1080 (1:1)
    INSTAGRAM_PORTRAIT = "instagram_portrait"  # 1080x1350 (4:5)
    INSTAGRAM_STORY = "instagram_story"  # 1080x1920 (9:16)

    # Twitter/X
    TWITTER = "twitter"  # 1200x675

    # Facebook
    FACEBOOK = "facebook"  # 1200x630

    # Thumbnail/Preview
    PREVIEW_SMALL = "preview_small"  # 320x180
    PREVIEW_MEDIUM = "preview_medium"  # 640x360
    PREVIEW_LARGE = "preview_large"  # 1280x720


# Size specifications
SIZE_SPECS = {
    ThumbnailSize.YOUTUBE: (1280, 720),
    ThumbnailSize.YOUTUBE_MOBILE: (480, 270),
    ThumbnailSize.TIKTOK: (1080, 1920),
    ThumbnailSize.INSTAGRAM_SQUARE: (1080, 1080),
    ThumbnailSize.INSTAGRAM_PORTRAIT: (1080, 1350),
    ThumbnailSize.INSTAGRAM_STORY: (1080, 1920),
    ThumbnailSize.TWITTER: (1200, 675),
    ThumbnailSize.FACEBOOK: (1200, 630),
    ThumbnailSize.PREVIEW_SMALL: (320, 180),
    ThumbnailSize.PREVIEW_MEDIUM: (640, 360),
    ThumbnailSize.PREVIEW_LARGE: (1280, 720),
}


class TextPosition(str, Enum):
    """Text overlay position"""
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    CENTER = "center"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"


@dataclass
class TextOverlay:
    """Text overlay configuration"""
    text: str
    position: TextPosition = TextPosition.BOTTOM_CENTER
    font_family: str = "Arial"
    font_size: int = 48
    font_color: str = "#FFFFFF"
    outline_color: str = "#000000"
    outline_width: int = 3
    shadow: bool = True
    shadow_color: str = "#000000"
    shadow_offset: Tuple[int, int] = (3, 3)
    background: bool = True
    background_color: str = "rgba(0,0,0,0.6)"
    padding: int = 20
    margin: int = 30


@dataclass
class ThumbnailSettings:
    """Settings for thumbnail generation"""
    sizes: List[ThumbnailSize] = field(default_factory=lambda: [ThumbnailSize.YOUTUBE])
    text_overlay: Optional[TextOverlay] = None
    extract_best_frame: bool = True
    face_detection: bool = True
    brightness_enhance: float = 1.1  # 1.0 = no change
    contrast_enhance: float = 1.1
    saturation_enhance: float = 1.0
    sharpness_enhance: float = 1.0
    add_border: bool = False
    border_color: str = "#FFFFFF"
    border_width: int = 4
    add_logo: bool = False
    logo_path: Optional[str] = None
    logo_position: TextPosition = TextPosition.BOTTOM_RIGHT
    logo_scale: float = 0.15
    output_format: str = "jpg"
    quality: int = 95


@dataclass
class ThumbnailResult:
    """Result of thumbnail generation"""
    file_paths: Dict[str, str]  # size -> path mapping
    source_frame_time: float  # Time in video of source frame
    face_detected: bool
    confidence_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class ThumbnailGenerator:
    """
    Thumbnail Generator

    Features:
    - Extract best frame from video
    - Face detection for optimal frame selection
    - Multiple size exports (YouTube, TikTok, Instagram, etc.)
    - Text overlay with customization
    - Image enhancement
    - Logo watermark
    """

    def __init__(
        self,
        output_dir: str = "outputs/thumbnails",
        cascade_path: Optional[str] = None,
    ):
        """
        Initialize Thumbnail Generator

        Args:
            output_dir: Directory for output files
            cascade_path: Path to Haar cascade for face detection
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Face detection cascade
        self.cascade_path = cascade_path
        self.face_cascade = None

        if CV2_AVAILABLE:
            if cascade_path and os.path.exists(cascade_path):
                self.face_cascade = cv2.CascadeClassifier(cascade_path)
            else:
                # Try default OpenCV cascades
                cascade_paths = [
                    cv2.data.haarcascades + "haarcascade_frontalface_default.xml",
                    cv2.data.haarcascades + "haarcascade_frontalface_alt.xml",
                ]
                for path in cascade_paths:
                    if os.path.exists(path):
                        self.face_cascade = cv2.CascadeClassifier(path)
                        logger.info(f"Loaded face cascade from: {path}")
                        break

        logger.info("ThumbnailGenerator initialized")

    async def generate(
        self,
        video_path: str,
        settings: Optional[ThumbnailSettings] = None,
        output_filename: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> ThumbnailResult:
        """
        Generate thumbnails from video

        Args:
            video_path: Path to video file
            settings: Thumbnail generation settings
            output_filename: Base output filename (without extension)
            timestamp: Specific timestamp to extract (optional)

        Returns:
            ThumbnailResult with paths and metadata
        """
        if not CV2_AVAILABLE:
            raise RuntimeError("OpenCV (cv2) is required for thumbnail generation")

        settings = settings or ThumbnailSettings()

        # Generate output filename
        output_filename = output_filename or Path(video_path).stem

        # Extract frame
        if timestamp is not None:
            frame, actual_time = await self._extract_frame_at_time(video_path, timestamp)
        elif settings.extract_best_frame:
            frame, actual_time, face_detected, confidence = await self._extract_best_frame(
                video_path, settings.face_detection
            )
        else:
            frame, actual_time = await self._extract_frame_at_time(video_path, 0)
            face_detected = False
            confidence = 0.0

        # Run face detection if not done
        if settings.face_detection and not face_detected:
            face_detected, confidence = self._detect_face(frame)

        # Enhance frame
        enhanced_frame = await self._enhance_frame(frame, settings)

        # Convert to PIL for processing
        pil_image = self._cv2_to_pil(enhanced_frame)

        # Add text overlay
        if settings.text_overlay:
            pil_image = await self._add_text_overlay(pil_image, settings.text_overlay)

        # Add logo
        if settings.add_logo and settings.logo_path:
            pil_image = await self._add_logo(pil_image, settings)

        # Export in all sizes
        output_paths = {}
        for size in settings.sizes:
            width, height = SIZE_SPECS[size]
            resized = await self._resize_and_crop(pil_image, width, height)

            # Add border if requested
            if settings.add_border:
                resized = await self._add_border(resized, settings)

            # Save
            output_path = self.output_dir / f"{output_filename}_{size.value}.{settings.output_format}"
            await self._save_image(resized, str(output_path), settings.quality, settings.output_format)
            output_paths[size.value] = str(output_path)

        logger.info(f"Generated {len(output_paths)} thumbnail(s) from {video_path}")

        return ThumbnailResult(
            file_paths=output_paths,
            source_frame_time=actual_time,
            face_detected=face_detected,
            confidence_score=confidence,
            metadata={
                "video_path": video_path,
                "settings": {
                    "sizes": [s.value for s in settings.sizes],
                    "brightness_enhance": settings.brightness_enhance,
                    "contrast_enhance": settings.contrast_enhance,
                }
            }
        )

    async def generate_multiple(
        self,
        video_path: str,
        num_thumbnails: int = 5,
        settings: Optional[ThumbnailSettings] = None,
        output_filename: Optional[str] = None,
        spread_mode: str = "evenly",  # "evenly", "random", "best_frames"
    ) -> List[ThumbnailResult]:
        """
        Generate multiple thumbnails from video

        Args:
            video_path: Path to video file
            num_thumbnails: Number of thumbnails to generate
            settings: Thumbnail settings
            output_filename: Base output filename
            spread_mode: How to select timestamps

        Returns:
            List of ThumbnailResult
        """
        settings = settings or ThumbnailSettings()
        output_filename = output_filename or Path(video_path).stem

        # Get video duration
        duration = await self._get_video_duration(video_path)

        # Determine timestamps
        if spread_mode == "evenly":
            timestamps = [duration * (i + 1) / (num_thumbnails + 1) for i in range(num_thumbnails)]
        elif spread_mode == "random":
            timestamps = [random.uniform(0.1 * duration, 0.9 * duration) for _ in range(num_thumbnails)]
        elif spread_mode == "best_frames":
            # Find best frames based on face detection and quality
            timestamps = await self._find_best_frames(video_path, num_thumbnails, settings.face_detection)
        else:
            timestamps = [duration * (i + 1) / (num_thumbnails + 1) for i in range(num_thumbnails)]

        results = []
        for i, ts in enumerate(timestamps):
            result = await self.generate(
                video_path=video_path,
                settings=settings,
                output_filename=f"{output_filename}_{i+1:02d}",
                timestamp=ts,
            )
            results.append(result)

        return results

    async def _get_video_duration(self, video_path: str) -> float:
        """Get video duration in seconds"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0

        cap.release()
        return duration

    async def _extract_frame_at_time(
        self,
        video_path: str,
        timestamp: float
    ) -> Tuple[np.ndarray, float]:
        """Extract frame at specific timestamp"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_number = int(timestamp * fps)

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()

        cap.release()

        if not ret:
            raise RuntimeError(f"Failed to extract frame at {timestamp}s")

        return frame, timestamp

    async def _extract_best_frame(
        self,
        video_path: str,
        use_face_detection: bool
    ) -> Tuple[np.ndarray, float, bool, float]:
        """Extract the best frame from video"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        # Sample frames at regular intervals
        sample_interval = max(1, total_frames // 30)  # Sample ~30 frames

        best_frame = None
        best_score = -1
        best_time = 0
        face_detected = False

        frame_idx = 0
        while frame_idx < total_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()

            if not ret:
                frame_idx += sample_interval
                continue

            # Calculate frame score
            score = 0.0
            detected = False

            # Face detection score
            if use_face_detection and self.face_cascade is not None:
                detected, face_score = self._detect_face(frame)
                if detected:
                    score += face_score * 100

            # Image quality score (sharpness/laplacian variance)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
            score += sharpness

            # Brightness score (prefer well-lit frames)
            brightness = np.mean(gray)
            # Optimal brightness around 127
            brightness_score = 100 - abs(brightness - 127) / 1.27
            score += brightness_score

            # Prefer frames from the middle portion of the video
            time_position = frame_idx / total_frames
            if 0.2 <= time_position <= 0.8:
                score += 20

            if score > best_score:
                best_score = score
                best_frame = frame.copy()
                best_time = frame_idx / fps
                face_detected = detected

            frame_idx += sample_interval

        cap.release()

        if best_frame is None:
            # Fallback to middle frame
            return await self._extract_frame_at_time(video_path, duration / 2)

        return best_frame, best_time, face_detected, best_score

    async def _find_best_frames(
        self,
        video_path: str,
        num_frames: int,
        use_face_detection: bool
    ) -> List[float]:
        """Find the best frames in the video"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        # Sample frames
        sample_interval = max(1, total_frames // 100)  # Sample up to 100 frames

        frame_scores = []

        frame_idx = 0
        while frame_idx < total_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()

            if not ret:
                frame_idx += sample_interval
                continue

            score = 0.0

            # Face detection
            if use_face_detection and self.face_cascade is not None:
                detected, face_score = self._detect_face(frame)
                if detected:
                    score += face_score * 100

            # Sharpness
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
            score += sharpness

            frame_scores.append((frame_idx / fps, score))
            frame_idx += sample_interval

        cap.release()

        # Sort by score and get top N
        frame_scores.sort(key=lambda x: x[1], reverse=True)

        # Ensure minimum spacing between frames
        min_spacing = duration / (num_frames * 2)
        selected_times = []

        for time, score in frame_scores:
            if len(selected_times) >= num_frames:
                break

            # Check spacing
            too_close = any(abs(time - t) < min_spacing for t in selected_times)
            if not too_close:
                selected_times.append(time)

        # Fill remaining with evenly spaced frames if needed
        while len(selected_times) < num_frames:
            remaining = num_frames - len(selected_times)
            for i in range(remaining):
                t = duration * (i + 1) / (remaining + 1)
                if t not in selected_times:
                    selected_times.append(t)
                if len(selected_times) >= num_frames:
                    break

        return sorted(selected_times[:num_frames])

    def _detect_face(self, frame: np.ndarray) -> Tuple[bool, float]:
        """Detect face in frame and return confidence"""
        if self.face_cascade is None:
            return False, 0.0

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Detect faces
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )

        if len(faces) == 0:
            return False, 0.0

        # Calculate confidence based on face size and position
        frame_h, frame_w = frame.shape[:2]
        frame_area = frame_w * frame_h

        best_confidence = 0.0
        for (x, y, w, h) in faces:
            face_area = w * h
            area_ratio = face_area / frame_area

            # Prefer faces in center
            center_x = (x + w/2) / frame_w
            center_y = (y + h/2) / frame_h
            center_distance = math.sqrt((center_x - 0.5)**2 + (center_y - 0.5)**2)

            # Score: larger face + closer to center = higher confidence
            confidence = area_ratio * (1 - center_distance)

            if confidence > best_confidence:
                best_confidence = confidence

        return True, min(best_confidence * 10, 1.0)  # Normalize to 0-1

    async def _enhance_frame(
        self,
        frame: np.ndarray,
        settings: ThumbnailSettings
    ) -> np.ndarray:
        """Apply image enhancements"""
        if not PIL_AVAILABLE:
            return frame

        # Convert to PIL
        pil_image = self._cv2_to_pil(frame)

        # Apply enhancements
        if settings.brightness_enhance != 1.0:
            enhancer = ImageEnhance.Brightness(pil_image)
            pil_image = enhancer.enhance(settings.brightness_enhance)

        if settings.contrast_enhance != 1.0:
            enhancer = ImageEnhance.Contrast(pil_image)
            pil_image = enhancer.enhance(settings.contrast_enhance)

        if settings.saturation_enhance != 1.0:
            enhancer = ImageEnhance.Color(pil_image)
            pil_image = enhancer.enhance(settings.saturation_enhance)

        if settings.sharpness_enhance != 1.0:
            enhancer = ImageEnhance.Sharpness(pil_image)
            pil_image = enhancer.enhance(settings.sharpness_enhance)

        # Convert back to OpenCV
        return self._pil_to_cv2(pil_image)

    def _cv2_to_pil(self, frame: np.ndarray) -> Image.Image:
        """Convert OpenCV frame to PIL Image"""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    def _pil_to_cv2(self, pil_image: Image.Image) -> np.ndarray:
        """Convert PIL Image to OpenCV frame"""
        np_array = np.array(pil_image)
        return cv2.cvtColor(np_array, cv2.COLOR_RGB2BGR)

    async def _resize_and_crop(
        self,
        image: Image.Image,
        target_width: int,
        target_height: int
    ) -> Image.Image:
        """Resize and crop image to target dimensions"""
        src_width, src_height = image.size
        target_ratio = target_width / target_height
        src_ratio = src_width / src_height

        if src_ratio > target_ratio:
            # Source is wider - crop sides
            new_height = src_height
            new_width = int(src_height * target_ratio)
            left = (src_width - new_width) // 2
            top = 0
            right = left + new_width
            bottom = src_height
        else:
            # Source is taller - crop top/bottom
            new_width = src_width
            new_height = int(src_width / target_ratio)
            left = 0
            top = (src_height - new_height) // 2
            right = src_width
            bottom = top + new_height

        # Crop and resize
        cropped = image.crop((left, top, right, bottom))
        resized = cropped.resize((target_width, target_height), Image.LANCZOS)

        return resized

    async def _add_text_overlay(
        self,
        image: Image.Image,
        overlay: TextOverlay
    ) -> Image.Image:
        """Add text overlay to image"""
        if not PIL_AVAILABLE:
            return image

        draw = ImageDraw.Draw(image)

        # Try to load font
        try:
            font = ImageFont.truetype(overlay.font_family, overlay.font_size)
        except (OSError, IOError):
            try:
                # Try system fonts
                font_paths = [
                    "arial.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "/System/Library/Fonts/Helvetica.ttc",
                    "C:\\Windows\\Fonts\\arial.ttf",
                ]
                font = None
                for path in font_paths:
                    try:
                        font = ImageFont.truetype(path, overlay.font_size)
                        break
                    except (OSError, IOError):
                        continue
                if font is None:
                    font = ImageFont.load_default()
            except Exception:
                font = ImageFont.load_default()

        # Get text bounding box
        bbox = draw.textbbox((0, 0), overlay.text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Calculate position
        img_width, img_height = image.size
        margin = overlay.margin
        padding = overlay.padding

        positions = {
            TextPosition.TOP_LEFT: (margin + padding, margin + padding),
            TextPosition.TOP_CENTER: ((img_width - text_width) // 2, margin + padding),
            TextPosition.TOP_RIGHT: (img_width - text_width - margin - padding, margin + padding),
            TextPosition.CENTER: ((img_width - text_width) // 2, (img_height - text_height) // 2),
            TextPosition.BOTTOM_LEFT: (margin + padding, img_height - text_height - margin - padding),
            TextPosition.BOTTOM_CENTER: ((img_width - text_width) // 2, img_height - text_height - margin - padding),
            TextPosition.BOTTOM_RIGHT: (img_width - text_width - margin - padding, img_height - text_height - margin - padding),
        }

        x, y = positions[overlay.position]

        # Draw background
        if overlay.background:
            bg_padding = padding
            bg_bbox = [
                x - bg_padding,
                y - bg_padding,
                x + text_width + bg_padding,
                y + text_height + bg_padding,
            ]

            # Parse background color
            bg_color = overlay.background_color
            if bg_color.startswith("rgba"):
                # Parse rgba
                match = re.match(r"rgba\((\d+),(\d+),(\d+),([\d.]+)\)", bg_color)
                if match:
                    r, g, b, a = match.groups()
                    bg_color = (int(r), int(g), int(b), int(float(a) * 255))
                    # Create overlay for transparency
                    overlay_img = Image.new("RGBA", image.size, (0, 0, 0, 0))
                    overlay_draw = ImageDraw.Draw(overlay_img)
                    overlay_draw.rounded_rectangle(bg_bbox, radius=10, fill=bg_color)
                    image = Image.alpha_composite(image.convert("RGBA"), overlay_img).convert("RGB")
                    draw = ImageDraw.Draw(image)

        # Parse font color
        font_color = self._parse_color(overlay.font_color)
        outline_color = self._parse_color(overlay.outline_color)

        # Draw shadow
        if overlay.shadow:
            shadow_offset = overlay.shadow_offset
            shadow_color = self._parse_color(overlay.shadow_color)
            draw.text(
                (x + shadow_offset[0], y + shadow_offset[1]),
                overlay.text,
                font=font,
                fill=shadow_color
            )

        # Draw outline
        if overlay.outline_width > 0:
            for adj_x in range(-overlay.outline_width, overlay.outline_width + 1):
                for adj_y in range(-overlay.outline_width, overlay.outline_width + 1):
                    if adj_x != 0 or adj_y != 0:
                        draw.text((x + adj_x, y + adj_y), overlay.text, font=font, fill=outline_color)

        # Draw text
        draw.text((x, y), overlay.text, font=font, fill=font_color)

        return image

    def _parse_color(self, color_str: str) -> Tuple[int, int, int]:
        """Parse color string to RGB tuple"""
        if color_str.startswith("#"):
            hex_color = color_str.lstrip("#")
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        elif color_str.startswith("rgb"):
            match = re.match(r"rgb\((\d+),(\d+),(\d+)\)", color_str)
            if match:
                return tuple(int(g) for g in match.groups())

        # Default to white
        return (255, 255, 255)

    async def _add_logo(
        self,
        image: Image.Image,
        settings: ThumbnailSettings
    ) -> Image.Image:
        """Add logo watermark to image"""
        if not settings.logo_path or not os.path.exists(settings.logo_path):
            return image

        try:
            logo = Image.open(settings.logo_path)

            # Convert to RGBA if needed
            if logo.mode != "RGBA":
                logo = logo.convert("RGBA")

            # Scale logo
            img_width, img_height = image.size
            logo_width = int(img_width * settings.logo_scale)
            logo_height = int(logo.size[1] * (logo_width / logo.size[0]))
            logo = logo.resize((logo_width, logo_height), Image.LANCZOS)

            # Calculate position
            margin = 20
            positions = {
                TextPosition.TOP_LEFT: (margin, margin),
                TextPosition.TOP_RIGHT: (img_width - logo_width - margin, margin),
                TextPosition.BOTTOM_LEFT: (margin, img_height - logo_height - margin),
                TextPosition.BOTTOM_RIGHT: (img_width - logo_width - margin, img_height - logo_height - margin),
            }

            pos = positions.get(settings.logo_position, positions[TextPosition.BOTTOM_RIGHT])

            # Paste logo
            image = image.convert("RGBA")
            image.paste(logo, pos, logo)
            return image.convert("RGB")

        except Exception as e:
            logger.warning(f"Failed to add logo: {e}")
            return image

    async def _add_border(
        self,
        image: Image.Image,
        settings: ThumbnailSettings
    ) -> Image.Image:
        """Add border to image"""
        border_color = self._parse_color(settings.border_color)
        return ImageOps.expand(image, border=settings.border_width, fill=border_color)

    async def _save_image(
        self,
        image: Image.Image,
        output_path: str,
        quality: int,
        format: str
    ) -> None:
        """Save image to file"""
        format = format.lower()

        if format in ["jpg", "jpeg"]:
            # Convert to RGB for JPEG
            if image.mode == "RGBA":
                image = image.convert("RGB")
            image.save(output_path, "JPEG", quality=quality, optimize=True)
        elif format == "png":
            image.save(output_path, "PNG", optimize=True)
        elif format == "webp":
            image.save(output_path, "WEBP", quality=quality)
        else:
            image.save(output_path, format)

    async def create_custom_thumbnail(
        self,
        background_path: Optional[str] = None,
        background_color: str = "#1a1a2e",
        text_overlay: Optional[TextOverlay] = None,
        size: ThumbnailSize = ThumbnailSize.YOUTUBE,
        output_filename: Optional[str] = None,
    ) -> str:
        """
        Create a custom thumbnail with text (no video required)

        Args:
            background_path: Path to background image
            background_color: Solid color if no image
            text_overlay: Text configuration
            size: Output size
            output_filename: Output filename

        Returns:
            Path to generated thumbnail
        """
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL is required for thumbnail creation")

        width, height = SIZE_SPECS[size]

        # Create or load background
        if background_path and os.path.exists(background_path):
            image = Image.open(background_path)
            image = await self._resize_and_crop(image, width, height)
        else:
            bg_color = self._parse_color(background_color)
            image = Image.new("RGB", (width, height), bg_color)

        # Add gradient overlay for better text visibility
        gradient = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        gradient_draw = ImageDraw.Draw(gradient)

        for i in range(height // 3):
            alpha = int(180 * (1 - i / (height // 3)))
            gradient_draw.line([(0, height - i), (width, height - i)], fill=(0, 0, 0, alpha))

        image = Image.alpha_composite(image.convert("RGBA"), gradient).convert("RGB")

        # Add text
        if text_overlay:
            image = await self._add_text_overlay(image, text_overlay)

        # Save
        output_filename = output_filename or "custom_thumbnail"
        output_path = self.output_dir / f"{output_filename}_{size.value}.jpg"

        image.save(str(output_path), "JPEG", quality=95, optimize=True)

        logger.info(f"Created custom thumbnail: {output_path}")
        return str(output_path)

    async def get_frame_at_timestamp(
        self,
        video_path: str,
        timestamp: float,
        output_path: Optional[str] = None
    ) -> str:
        """
        Extract a single frame at specific timestamp

        Args:
            video_path: Path to video
            timestamp: Time in seconds
            output_path: Output path (optional)

        Returns:
            Path to extracted frame
        """
        frame, _ = await self._extract_frame_at_time(video_path, timestamp)

        output_path = output_path or str(self.output_dir / f"frame_{timestamp:.2f}.jpg")

        if PIL_AVAILABLE:
            pil_image = self._cv2_to_pil(frame)
            pil_image.save(output_path, "JPEG", quality=95)
        else:
            cv2.imwrite(output_path, frame)

        return output_path

    async def analyze_video_for_thumbnails(
        self,
        video_path: str
    ) -> Dict[str, Any]:
        """
        Analyze video to find optimal thumbnail timestamps

        Args:
            video_path: Path to video

        Returns:
            Analysis results with recommended timestamps
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Sample frames for analysis
        sample_interval = max(1, total_frames // 50)

        frame_analysis = []
        face_count = 0

        frame_idx = 0
        while frame_idx < total_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()

            if not ret:
                frame_idx += sample_interval
                continue

            timestamp = frame_idx / fps

            # Analyze frame
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Sharpness
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()

            # Brightness
            brightness = np.mean(gray)

            # Face detection
            has_face = False
            face_confidence = 0
            if self.face_cascade is not None:
                has_face, face_confidence = self._detect_face(frame)
                if has_face:
                    face_count += 1

            frame_analysis.append({
                "timestamp": timestamp,
                "frame_idx": frame_idx,
                "sharpness": float(sharpness),
                "brightness": float(brightness),
                "has_face": has_face,
                "face_confidence": face_confidence,
            })

            frame_idx += sample_interval

        cap.release()

        # Calculate recommendations
        if frame_analysis:
            # Sort by combined score
            for fa in frame_analysis:
                fa["score"] = fa["sharpness"] * 0.5 + fa["face_confidence"] * 100

            sorted_analysis = sorted(frame_analysis, key=lambda x: x["score"], reverse=True)
            recommended_timestamps = [fa["timestamp"] for fa in sorted_analysis[:5]]
        else:
            recommended_timestamps = [duration * 0.25, duration * 0.5, duration * 0.75]

        return {
            "video_path": video_path,
            "duration": duration,
            "resolution": f"{width}x{height}",
            "fps": fps,
            "total_frames": total_frames,
            "frames_analyzed": len(frame_analysis),
            "frames_with_faces": face_count,
            "recommended_timestamps": recommended_timestamps,
            "frame_analysis": frame_analysis[:10],  # Top 10 for reference
        }


# Import for border
try:
    from PIL import ImageOps
except ImportError:
    pass

import re
