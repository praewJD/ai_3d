"""
Subtitle Generator

Generates subtitles from narration text with word-level timing.
Supports SRT and VTT formats with style customization.
"""
import os
import re
import json
import logging
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import timedelta

# Audio processing for word timing
try:
    import librosa
    import numpy as np
    AUDIO_LIBS_AVAILABLE = True
except ImportError:
    AUDIO_LIBS_AVAILABLE = False


logger = logging.getLogger(__name__)


class SubtitleFormat(str, Enum):
    """Subtitle format types"""
    SRT = "srt"
    VTT = "vtt"
    ASS = "ass"  # Advanced SubStation Alpha
    JSON = "json"


class SubtitlePosition(str, Enum):
    """Subtitle position"""
    BOTTOM = "bottom"
    TOP = "top"
    CENTER = "center"


@dataclass
class SubtitleStyle:
    """Subtitle styling options"""
    font_family: str = "Arial"
    font_size: int = 24
    font_color: str = "#FFFFFF"
    outline_color: str = "#000000"
    outline_width: int = 2
    shadow: bool = True
    shadow_color: str = "#000000"
    shadow_blur: int = 4
    background: bool = True
    background_color: str = "rgba(0,0,0,0.5)"
    background_padding: int = 8
    position: SubtitlePosition = SubtitlePosition.BOTTOM
    margin_vertical: int = 50
    margin_horizontal: int = 50
    line_spacing: float = 1.2
    max_lines: int = 2
    max_chars_per_line: int = 42

    # Animation
    fade_in: float = 0.1  # seconds
    fade_out: float = 0.1  # seconds

    def to_ass_style(self) -> str:
        """Convert to ASS style format"""
        # Map common fonts
        font_map = {
            "Arial": "Arial",
            "Helvetica": "Arial",
            "Times New Roman": "Times New Roman",
            "Courier": "Courier New",
            "Verdana": "Verdana",
            "Georgia": "Georgia",
        }

        font = font_map.get(self.font_family, self.font_family)

        # Convert hex to ASS color (BGR format)
        def hex_to_ass(hex_color: str) -> str:
            hex_color = hex_color.lstrip('#')
            r, g, b = hex_color[:2], hex_color[2:4], hex_color[4:6]
            return f"&H{b}{g}{r}&".upper()

        primary_color = hex_to_ass(self.font_color)
        outline_color = hex_to_ass(self.outline_color)
        shadow_color = hex_to_ass(self.shadow_color)

        # Position alignment
        alignment = 2  # Bottom center by default
        if self.position == SubtitlePosition.TOP:
            alignment = 8
        elif self.position == SubtitlePosition.CENTER:
            alignment = 5

        return (
            f"Style: Default,{font},{self.font_size},"
            f"{primary_color},{primary_color},{outline_color},{shadow_color},"
            f"0,0,0,{alignment},{self.margin_horizontal},{self.margin_vertical},"
            f"0,0,0,1,{self.outline_width},0,{self.shadow_blur},0,0"
        )

    def to_vtt_style(self) -> str:
        """Convert to VTT CSS style"""
        position_css = {
            SubtitlePosition.BOTTOM: f"bottom: {self.margin_vertical}px;",
            SubtitlePosition.TOP: f"top: {self.margin_vertical}px;",
            SubtitlePosition.CENTER: "top: 50%; transform: translateY(-50%);",
        }

        bg_style = ""
        if self.background:
            bg_style = f"background-color: {self.background_color}; padding: {self.background_padding}px;"

        return f"""
::cue {{
    font-family: {self.font_family};
    font-size: {self.font_size}px;
    color: {self.font_color};
    text-shadow: {self.outline_width}px {self.outline_width}px {self.shadow_blur}px {self.shadow_color};
    {bg_style}
    {position_css[self.position]}
}}
"""


@dataclass
class SubtitleWord:
    """Single subtitle word with timing"""
    text: str
    start_time: float  # seconds
    end_time: float  # seconds
    confidence: float = 1.0


@dataclass
class SubtitleSegment:
    """Subtitle segment (one or more words displayed together)"""
    index: int
    words: List[SubtitleWord]
    start_time: float
    end_time: float
    text: str

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class SubtitleResult:
    """Complete subtitle result"""
    segments: List[SubtitleSegment]
    language: str
    format: SubtitleFormat
    total_duration: float
    style: Optional[SubtitleStyle] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class SubtitleGenerator:
    """
    Subtitle Generator

    Features:
    - Generate SRT/VTT/ASS/JSON formats
    - Word-level timing estimation
    - Multi-language support
    - Style customization
    - Integration with TTS timing data
    """

    # Language-specific character rates (characters per second)
    CHAR_RATES = {
        "en": 15.0,  # English
        "ko": 8.0,   # Korean (more complex characters)
        "ja": 8.0,   # Japanese
        "zh": 8.0,   # Chinese
        "th": 12.0,  # Thai
        "es": 14.0,  # Spanish
        "fr": 14.0,  # French
        "de": 13.0,  # German
        "default": 12.0,
    }

    # Punctuation pause durations (seconds)
    PUNCTUATION_PAUSES = {
        ".": 0.4,
        "!": 0.4,
        "?": 0.4,
        ",": 0.2,
        ";": 0.3,
        ":": 0.3,
        "-": 0.1,
        "—": 0.2,
        "...": 0.5,
    }

    def __init__(
        self,
        output_dir: str = "outputs/subtitles",
        default_language: str = "ko",
        default_style: Optional[SubtitleStyle] = None,
    ):
        """
        Initialize Subtitle Generator

        Args:
            output_dir: Directory for output files
            default_language: Default language code
            default_style: Default subtitle style
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.default_language = default_language
        self.default_style = default_style or SubtitleStyle()

        logger.info("SubtitleGenerator initialized")

    async def generate_from_text(
        self,
        text: str,
        audio_duration: float,
        language: Optional[str] = None,
        style: Optional[SubtitleStyle] = None,
        output_format: SubtitleFormat = SubtitleFormat.SRT,
        output_filename: Optional[str] = None,
    ) -> Tuple[str, SubtitleResult]:
        """
        Generate subtitles from text with estimated timing

        Args:
            text: Narration text
            audio_duration: Total audio duration in seconds
            language: Language code
            style: Subtitle style
            output_format: Output format
            output_filename: Output filename (without extension)

        Returns:
            Tuple of (file_path, SubtitleResult)
        """
        language = language or self.default_language
        style = style or self.default_style

        # Clean text
        clean_text = self._clean_text(text)

        # Estimate word timings
        words = await self._estimate_word_timings(clean_text, audio_duration, language)

        # Create segments
        segments = self._create_segments(words, style)

        # Create result
        result = SubtitleResult(
            segments=segments,
            language=language,
            format=output_format,
            total_duration=audio_duration,
            style=style,
        )

        # Generate output
        output_filename = output_filename or f"subtitle_{language}"
        output_path = self.output_dir / f"{output_filename}.{output_format.value}"

        content = self._format_output(result, output_format)
        output_path.write_text(content, encoding="utf-8")

        logger.info(f"Generated subtitles: {output_path}")
        return str(output_path), result

    async def generate_from_word_timings(
        self,
        word_timings: List[Dict[str, Any]],
        language: Optional[str] = None,
        style: Optional[SubtitleStyle] = None,
        output_format: SubtitleFormat = SubtitleFormat.SRT,
        output_filename: Optional[str] = None,
    ) -> Tuple[str, SubtitleResult]:
        """
        Generate subtitles from pre-computed word timings

        Args:
            word_timings: List of {"word": str, "start": float, "end": float}
            language: Language code
            style: Subtitle style
            output_format: Output format
            output_filename: Output filename (without extension)

        Returns:
            Tuple of (file_path, SubtitleResult)
        """
        language = language or self.default_language
        style = style or self.default_style

        # Convert to SubtitleWord objects
        words = [
            SubtitleWord(
                text=wt["word"],
                start_time=wt["start"],
                end_time=wt["end"],
                confidence=wt.get("confidence", 1.0),
            )
            for wt in word_timings
        ]

        # Create segments
        segments = self._create_segments(words, style)

        # Calculate total duration
        total_duration = max(w.end_time for w in words) if words else 0

        # Create result
        result = SubtitleResult(
            segments=segments,
            language=language,
            format=output_format,
            total_duration=total_duration,
            style=style,
        )

        # Generate output
        output_filename = output_filename or f"subtitle_{language}"
        output_path = self.output_dir / f"{output_filename}.{output_format.value}"

        content = self._format_output(result, output_format)
        output_path.write_text(content, encoding="utf-8")

        logger.info(f"Generated subtitles from timings: {output_path}")
        return str(output_path), result

    async def generate_from_audio(
        self,
        audio_path: str,
        text: str,
        language: Optional[str] = None,
        style: Optional[SubtitleStyle] = None,
        output_format: SubtitleFormat = SubtitleFormat.SRT,
        output_filename: Optional[str] = None,
    ) -> Tuple[str, SubtitleResult]:
        """
        Generate subtitles with timing derived from audio analysis

        Args:
            audio_path: Path to audio file
            text: Narration text
            language: Language code
            style: Subtitle style
            output_format: Output format
            output_filename: Output filename (without extension)

        Returns:
            Tuple of (file_path, SubtitleResult)
        """
        language = language or self.default_language
        style = style or self.default_style

        # Get audio duration
        if AUDIO_LIBS_AVAILABLE:
            audio_duration = librosa.get_duration(path=audio_path)
        else:
            # Fallback estimation
            audio_duration = await self._estimate_audio_duration(audio_path)

        return await self.generate_from_text(
            text=text,
            audio_duration=audio_duration,
            language=language,
            style=style,
            output_format=output_format,
            output_filename=output_filename,
        )

    async def _estimate_audio_duration(self, audio_path: str) -> float:
        """Estimate audio duration without librosa"""
        try:
            # Use ffprobe if available
            import subprocess
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return float(result.stdout.strip())
        except Exception:
            pass

        # Fallback: estimate from file size (rough)
        file_size = os.path.getsize(audio_path)
        return file_size / 24000  # ~192kbps

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Remove extra whitespace
        text = " ".join(text.split())
        # Normalize unicode
        text = text.strip()
        return text

    async def _estimate_word_timings(
        self,
        text: str,
        total_duration: float,
        language: str
    ) -> List[SubtitleWord]:
        """Estimate word-level timings based on text and duration"""
        # Tokenize text
        words = self._tokenize(text, language)
        if not words:
            return []

        # Get character rate for language
        char_rate = self.CHAR_RATES.get(language, self.CHAR_RATES["default"])

        # Calculate total character count
        total_chars = sum(len(w) for w in words)

        # Calculate timing scale factor
        estimated_duration = total_chars / char_rate
        scale_factor = total_duration / estimated_duration if estimated_duration > 0 else 1.0

        # Calculate timing for each word
        words_with_timing = []
        current_time = 0.0

        for i, word in enumerate(words):
            # Word duration based on character count
            word_duration = (len(word) / char_rate) * scale_factor

            # Add punctuation pause
            if i > 0:
                for punct, pause in self.PUNCTUATION_PAUSES.items():
                    if words[i-1].endswith(punct):
                        current_time += pause * scale_factor
                        break

            # Ensure minimum duration for short words
            word_duration = max(word_duration, 0.2)

            words_with_timing.append(SubtitleWord(
                text=word,
                start_time=current_time,
                end_time=current_time + word_duration,
            ))

            current_time += word_duration

            # Add inter-word gap
            current_time += 0.05

        # Normalize to fit within total duration
        if words_with_timing:
            max_end = max(w.end_time for w in words_with_timing)
            if max_end > total_duration:
                scale = total_duration / max_end
                for w in words_with_timing:
                    w.start_time *= scale
                    w.end_time *= scale

        return words_with_timing

    def _tokenize(self, text: str, language: str) -> List[str]:
        """Tokenize text into words based on language"""
        if language in ["ko", "ja", "zh", "th"]:
            # For CJK and Thai, split by spaces and punctuation
            # These languages don't use spaces between words
            tokens = re.findall(r'[\w\uAC00-\uD7AF\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\u0E00-\u0E7F]+|[.,!?;:\-—]+', text)
            return [t for t in tokens if t.strip() and not t in ".,!?;:—-"]
        else:
            # For languages with spaces (English, etc.)
            tokens = re.findall(r'\b\w+\b|[.,!?;:\-—]+', text)
            return [t for t in tokens if t.strip() and not t in ".,!?;:—-"]

    def _create_segments(
        self,
        words: List[SubtitleWord],
        style: SubtitleStyle
    ) -> List[SubtitleSegment]:
        """Create subtitle segments from words"""
        if not words:
            return []

        segments = []
        current_words = []
        current_text = []
        current_chars = 0

        for word in words:
            word_len = len(word.text)

            # Check if adding this word exceeds limits
            would_exceed_chars = current_chars + word_len + 1 > style.max_chars_per_line
            would_exceed_lines = len(current_text) >= style.max_lines * style.max_chars_per_line
            is_sentence_end = word.text.endswith(('.', '!', '?'))

            if (would_exceed_chars or would_exceed_lines) and current_words:
                # Create segment
                segments.append(SubtitleSegment(
                    index=len(segments) + 1,
                    words=current_words,
                    start_time=current_words[0].start_time,
                    end_time=current_words[-1].end_time,
                    text=" ".join(w.text for w in current_words),
                ))

                current_words = [word]
                current_text = [word.text]
                current_chars = word_len
            else:
                current_words.append(word)
                current_text.append(word.text)
                current_chars += word_len + 1  # +1 for space

            # Force break at sentence end
            if is_sentence_end and current_words:
                segments.append(SubtitleSegment(
                    index=len(segments) + 1,
                    words=current_words,
                    start_time=current_words[0].start_time,
                    end_time=current_words[-1].end_time,
                    text=" ".join(w.text for w in current_words),
                ))
                current_words = []
                current_text = []
                current_chars = 0

        # Don't forget remaining words
        if current_words:
            segments.append(SubtitleSegment(
                index=len(segments) + 1,
                words=current_words,
                start_time=current_words[0].start_time,
                end_time=current_words[-1].end_time,
                text=" ".join(w.text for w in current_words),
            ))

        return segments

    def _format_output(self, result: SubtitleResult, format: SubtitleFormat) -> str:
        """Format subtitle result to specific format"""
        if format == SubtitleFormat.SRT:
            return self._format_srt(result)
        elif format == SubtitleFormat.VTT:
            return self._format_vtt(result)
        elif format == SubtitleFormat.ASS:
            return self._format_ass(result)
        elif format == SubtitleFormat.JSON:
            return self._format_json(result)
        else:
            return self._format_srt(result)

    def _format_timestamp_srt(self, seconds: float) -> str:
        """Format timestamp for SRT format (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _format_timestamp_vtt(self, seconds: float) -> str:
        """Format timestamp for VTT format (HH:MM:SS.mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

    def _format_srt(self, result: SubtitleResult) -> str:
        """Format as SRT"""
        lines = []
        for segment in result.segments:
            lines.append(str(segment.index))
            lines.append(
                f"{self._format_timestamp_srt(segment.start_time)} --> "
                f"{self._format_timestamp_srt(segment.end_time)}"
            )
            lines.append(segment.text)
            lines.append("")  # Empty line between entries

        return "\n".join(lines)

    def _format_vtt(self, result: SubtitleResult) -> str:
        """Format as WebVTT"""
        lines = ["WEBVTT"]

        # Add style if provided
        if result.style:
            lines.append("STYLE")
            lines.append(result.style.to_vtt_style())
            lines.append("")

        for segment in result.segments:
            lines.append(
                f"{self._format_timestamp_vtt(segment.start_time)} --> "
                f"{self._format_timestamp_vtt(segment.end_time)}"
            )
            lines.append(segment.text)
            lines.append("")

        return "\n".join(lines)

    def _format_ass(self, result: SubtitleResult) -> str:
        """Format as ASS/SSA"""
        lines = ["[Script Info]"]
        lines.append("Title: Generated Subtitles")
        lines.append(f"ScriptType: v4.00+")
        lines.append(f"PlayResX: 1920")
        lines.append(f"PlayResY: 1080")
        lines.append("WrapStyle: 0")
        lines.append("")

        lines.append("[V4+ Styles]")
        if result.style:
            lines.append(result.style.to_ass_style())
        else:
            # Default style
            default_style = SubtitleStyle()
            lines.append(default_style.to_ass_style())
        lines.append("")

        lines.append("[Events]")
        lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")

        for segment in result.segments:
            start = self._format_timestamp_ass(segment.start_time)
            end = self._format_timestamp_ass(segment.end_time)
            # Escape line breaks
            text = segment.text.replace("\n", "\\N")
            lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

        return "\n".join(lines)

    def _format_timestamp_ass(self, seconds: float) -> str:
        """Format timestamp for ASS format (H:MM:SS.cc)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int((seconds % 1) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"

    def _format_json(self, result: SubtitleResult) -> str:
        """Format as JSON"""
        data = {
            "language": result.language,
            "total_duration": result.total_duration,
            "segments": [
                {
                    "index": s.index,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "duration": s.duration,
                    "text": s.text,
                    "words": [
                        {
                            "text": w.text,
                            "start": w.start_time,
                            "end": w.end_time,
                            "confidence": w.confidence,
                        }
                        for w in s.words
                    ]
                }
                for s in result.segments
            ],
            "style": {
                "font_family": result.style.font_family,
                "font_size": result.style.font_size,
                "font_color": result.style.font_color,
                "position": result.style.position.value,
            } if result.style else None,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    async def translate_subtitles(
        self,
        source_path: str,
        target_language: str,
        translation_func: callable,
        output_filename: Optional[str] = None,
    ) -> Tuple[str, SubtitleResult]:
        """
        Translate existing subtitles to another language

        Args:
            source_path: Path to source subtitle file
            target_language: Target language code
            translation_func: Async function to translate text
            output_filename: Output filename (without extension)

        Returns:
            Tuple of (file_path, SubtitleResult)
        """
        # Parse source file
        source_result = await self._parse_subtitle_file(source_path)

        # Translate each segment
        translated_segments = []
        for segment in source_result.segments:
            translated_text = await translation_func(segment.text, target_language)

            translated_segments.append(SubtitleSegment(
                index=segment.index,
                words=[],  # Clear words for translated version
                start_time=segment.start_time,
                end_time=segment.end_time,
                text=translated_text,
            ))

        # Create result
        result = SubtitleResult(
            segments=translated_segments,
            language=target_language,
            format=source_result.format,
            total_duration=source_result.total_duration,
            style=source_result.style,
        )

        # Generate output
        output_filename = output_filename or f"subtitle_{target_language}"
        output_path = self.output_dir / f"{output_filename}.{source_result.format.value}"

        content = self._format_output(result, source_result.format)
        output_path.write_text(content, encoding="utf-8")

        logger.info(f"Translated subtitles: {output_path}")
        return str(output_path), result

    async def _parse_subtitle_file(self, file_path: str) -> SubtitleResult:
        """Parse existing subtitle file"""
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")

        if file_path.endswith(".srt"):
            return self._parse_srt(content)
        elif file_path.endswith(".vtt"):
            return self._parse_vtt(content)
        elif file_path.endswith(".json"):
            return self._parse_json(content)
        else:
            raise ValueError(f"Unsupported subtitle format: {file_path}")

    def _parse_srt(self, content: str) -> SubtitleResult:
        """Parse SRT format"""
        segments = []
        blocks = content.strip().split("\n\n")

        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) >= 3:
                index = int(lines[0])
                times = lines[1].split(" --> ")
                start = self._parse_timestamp_srt(times[0])
                end = self._parse_timestamp_srt(times[1])
                text = "\n".join(lines[2:])

                segments.append(SubtitleSegment(
                    index=index,
                    words=[],
                    start_time=start,
                    end_time=end,
                    text=text,
                ))

        return SubtitleResult(
            segments=segments,
            language="unknown",
            format=SubtitleFormat.SRT,
            total_duration=max(s.end_time for s in segments) if segments else 0,
        )

    def _parse_timestamp_srt(self, timestamp: str) -> float:
        """Parse SRT timestamp"""
        parts = timestamp.replace(",", ".").split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds

    def _parse_vtt(self, content: str) -> SubtitleResult:
        """Parse WebVTT format"""
        segments = []
        lines = content.split("\n")
        i = 0

        # Skip header
        while i < len(lines) and not "-->" in lines[i]:
            i += 1

        while i < len(lines):
            if "-->" in lines[i]:
                times = lines[i].split(" --> ")
                start = self._parse_timestamp_vtt(times[0])
                end = self._parse_timestamp_vtt(times[1])
                i += 1

                text_lines = []
                while i < len(lines) and lines[i].strip():
                    text_lines.append(lines[i])
                    i += 1

                segments.append(SubtitleSegment(
                    index=len(segments) + 1,
                    words=[],
                    start_time=start,
                    end_time=end,
                    text="\n".join(text_lines),
                ))
            i += 1

        return SubtitleResult(
            segments=segments,
            language="unknown",
            format=SubtitleFormat.VTT,
            total_duration=max(s.end_time for s in segments) if segments else 0,
        )

    def _parse_timestamp_vtt(self, timestamp: str) -> float:
        """Parse VTT timestamp"""
        parts = timestamp.replace(".", ":").split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
        millis = int(parts[3]) if len(parts) > 3 else 0
        return hours * 3600 + minutes * 60 + seconds + millis / 1000

    def _parse_json(self, content: str) -> SubtitleResult:
        """Parse JSON subtitle format"""
        data = json.loads(content)

        segments = []
        for s in data.get("segments", []):
            words = [
                SubtitleWord(
                    text=w["text"],
                    start_time=w["start"],
                    end_time=w["end"],
                    confidence=w.get("confidence", 1.0),
                )
                for w in s.get("words", [])
            ]

            segments.append(SubtitleSegment(
                index=s["index"],
                words=words,
                start_time=s["start_time"],
                end_time=s["end_time"],
                text=s["text"],
            ))

        style_data = data.get("style", {})
        style = SubtitleStyle(
            font_family=style_data.get("font_family", "Arial"),
            font_size=style_data.get("font_size", 24),
            font_color=style_data.get("font_color", "#FFFFFF"),
        ) if style_data else None

        return SubtitleResult(
            segments=segments,
            language=data.get("language", "unknown"),
            format=SubtitleFormat.JSON,
            total_duration=data.get("total_duration", 0),
            style=style,
        )

    async def merge_with_video(
        self,
        video_path: str,
        subtitle_path: str,
        output_path: str,
        style: Optional[SubtitleStyle] = None,
        burn_in: bool = True,
    ) -> str:
        """
        Merge subtitles with video (burn in or embed)

        Args:
            video_path: Path to video file
            subtitle_path: Path to subtitle file
            output_path: Output video path
            style: Subtitle style for burn-in
            burn_in: If True, burn subtitles into video; if False, embed as track

        Returns:
            Path to output video
        """
        import subprocess

        style = style or self.default_style

        if burn_in:
            # Use ffmpeg with subtitles filter
            # Escape special characters for ffmpeg
            subtitle_path_escaped = subtitle_path.replace(":", "\\:").replace("'", "'\\''")

            vf_filter = f"subtitles='{subtitle_path_escaped}'"

            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vf", vf_filter,
                "-c:a", "copy",
                output_path
            ]
        else:
            # Embed subtitles as soft track
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", subtitle_path,
                "-c:v", "copy",
                "-c:a", "copy",
                "-c:s", "mov_text",
                "-map", "0:v:0",
                "-map", "0:a:0",
                "-map", "1:0",
                output_path
            ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"Merged subtitles into video: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to merge subtitles: {e.stderr}")
            raise RuntimeError(f"Failed to merge subtitles: {e.stderr}")

    async def get_supported_languages(self) -> List[Dict[str, str]]:
        """Get list of supported languages"""
        return [
            {"code": "ko", "name": "Korean"},
            {"code": "en", "name": "English"},
            {"code": "ja", "name": "Japanese"},
            {"code": "zh", "name": "Chinese"},
            {"code": "th", "name": "Thai"},
            {"code": "es", "name": "Spanish"},
            {"code": "fr", "name": "French"},
            {"code": "de", "name": "German"},
            {"code": "pt", "name": "Portuguese"},
            {"code": "ru", "name": "Russian"},
            {"code": "ar", "name": "Arabic"},
            {"code": "hi", "name": "Hindi"},
        ]
