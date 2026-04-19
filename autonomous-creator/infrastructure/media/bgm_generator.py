"""
Background Music Generator

Generates or selects background music based on mood and duration requirements.
Supports free music APIs and local generation.
"""
import os
import json
import logging
import asyncio
import aiohttp
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import random
import hashlib

# Audio processing
try:
    import librosa
    import soundfile as sf
    AUDIO_LIBS_AVAILABLE = True
except ImportError:
    AUDIO_LIBS_AVAILABLE = False

# For local generation
try:
    from scipy import signal
    from scipy.io import wavfile
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


logger = logging.getLogger(__name__)


class BGMMood(str, Enum):
    """Background music mood types"""
    HAPPY = "happy"
    SAD = "sad"
    DRAMATIC = "dramatic"
    PEACEFUL = "peaceful"
    ENERGETIC = "energetic"
    MYSTERIOUS = "mysterious"
    ROMANTIC = "romantic"
    TENSE = "tense"
    INSPIRATIONAL = "inspirational"
    NEUTRAL = "neutral"


class BGMSource(str, Enum):
    """BGM source types"""
    LOCAL_LIBRARY = "local_library"
    FREE_MUSIC_ARCHIVE = "free_music_archive"
    PIXABAY = "pixabay"
    GENERATED = "generated"


@dataclass
class BGMSettings:
    """Settings for BGM generation/selection"""
    mood: BGMMood = BGMMood.NEUTRAL
    duration: float = 60.0  # seconds
    volume: float = 0.3  # 0.0 to 1.0
    fade_in: float = 2.0  # seconds
    fade_out: float = 3.0  # seconds
    loop: bool = True
    source: BGMSource = BGMSource.LOCAL_LIBRARY
    tempo_range: Tuple[int, int] = (60, 120)  # BPM range
    instruments: Optional[List[str]] = None
    genre: Optional[str] = None
    avoid_vocals: bool = True
    sample_rate: int = 44100


@dataclass
class BGMTrack:
    """Represents a BGM track"""
    file_path: str
    title: str
    mood: BGMMood
    duration: float
    tempo: int  # BPM
    source: BGMSource
    artist: Optional[str] = None
    license: Optional[str] = None
    preview_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BGMGenerator:
    """
    Background Music Generator/Selector

    Features:
    - Mood-based music selection
    - Duration matching with loop/stretch
    - Volume auto-adjustment
    - Free music API integration
    - Local procedural generation
    """

    # Mood to musical parameters mapping
    MOOD_PARAMS = {
        BGMMood.HAPPY: {
            "tempo_range": (100, 140),
            "scale": "major",
            "instruments": ["piano", "guitar", "strings", "brass"],
            "energy": 0.8,
            "valence": 0.9,
        },
        BGMMood.SAD: {
            "tempo_range": (40, 80),
            "scale": "minor",
            "instruments": ["piano", "strings", "cello"],
            "energy": 0.3,
            "valence": 0.2,
        },
        BGMMood.DRAMATIC: {
            "tempo_range": (80, 120),
            "scale": "minor",
            "instruments": ["orchestra", "brass", "timpani", "choir"],
            "energy": 0.9,
            "valence": 0.4,
        },
        BGMMood.PEACEFUL: {
            "tempo_range": (40, 70),
            "scale": "major",
            "instruments": ["piano", "flute", "strings", "harp"],
            "energy": 0.2,
            "valence": 0.7,
        },
        BGMMood.ENERGETIC: {
            "tempo_range": (120, 180),
            "scale": "major",
            "instruments": ["drums", "bass", "synth", "guitar"],
            "energy": 0.95,
            "valence": 0.8,
        },
        BGMMood.MYSTERIOUS: {
            "tempo_range": (60, 100),
            "scale": "minor",
            "instruments": ["synth", "piano", "strings", "pad"],
            "energy": 0.5,
            "valence": 0.3,
        },
        BGMMood.ROMANTIC: {
            "tempo_range": (60, 90),
            "scale": "major",
            "instruments": ["piano", "strings", "guitar", "flute"],
            "energy": 0.4,
            "valence": 0.8,
        },
        BGMMood.TENSE: {
            "tempo_range": (80, 140),
            "scale": "chromatic",
            "instruments": ["strings", "percussion", "synth"],
            "energy": 0.7,
            "valence": 0.2,
        },
        BGMMood.INSPIRATIONAL: {
            "tempo_range": (80, 120),
            "scale": "major",
            "instruments": ["orchestra", "piano", "choir", "brass"],
            "energy": 0.75,
            "valence": 0.85,
        },
        BGMMood.NEUTRAL: {
            "tempo_range": (60, 120),
            "scale": "major",
            "instruments": ["piano", "strings", "synth"],
            "energy": 0.5,
            "valence": 0.5,
        },
    }

    def __init__(
        self,
        music_library_path: Optional[str] = None,
        pixabay_api_key: Optional[str] = None,
        freemusicarchive_api_key: Optional[str] = None,
        output_dir: str = "outputs/bgm",
        cache_dir: str = "cache/bgm",
    ):
        """
        Initialize BGM Generator

        Args:
            music_library_path: Path to local music library
            pixabay_api_key: Pixabay API key for free music
            freemusicarchive_api_key: Free Music Archive API key
            output_dir: Directory for output files
            cache_dir: Directory for cached downloads
        """
        self.music_library_path = Path(music_library_path) if music_library_path else None
        self.pixabay_api_key = pixabay_api_key or os.getenv("PIXABAY_API_KEY")
        self.freemusicarchive_api_key = freemusicarchive_api_key or os.getenv("FMA_API_KEY")
        self.output_dir = Path(output_dir)
        self.cache_dir = Path(cache_dir)

        # Create directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Local music library index
        self._library_index: Dict[str, List[BGMTrack]] = {}
        self._is_indexed = False

        logger.info("BGMGenerator initialized")

    async def initialize(self) -> None:
        """Initialize the generator and index local library"""
        if self.music_library_path and self.music_library_path.exists():
            await self._index_local_library()
        self._is_indexed = True
        logger.info("BGM Generator initialized and ready")

    async def _index_local_library(self) -> None:
        """Index local music library"""
        if not self.music_library_path:
            return

        audio_extensions = {'.mp3', '.wav', '.ogg', '.flac', '.m4a'}
        self._library_index = {mood.value: [] for mood in BGMMood}

        # Look for mood-based folder structure
        for mood in BGMMood:
            mood_path = self.music_library_path / mood.value
            if mood_path.exists():
                for audio_file in mood_path.iterdir():
                    if audio_file.suffix.lower() in audio_extensions:
                        track = await self._create_track_from_file(audio_file, mood)
                        if track:
                            self._library_index[mood.value].append(track)

        # Also index generic folder
        generic_path = self.music_library_path / "generic"
        if generic_path.exists():
            for audio_file in generic_path.iterdir():
                if audio_file.suffix.lower() in audio_extensions:
                    track = await self._create_track_from_file(audio_file, BGMMood.NEUTRAL)
                    if track:
                        self._library_index[BGMMood.NEUTRAL.value].append(track)

        total_tracks = sum(len(tracks) for tracks in self._library_index.values())
        logger.info(f"Indexed {total_tracks} tracks from local library")

    async def _create_track_from_file(
        self,
        file_path: Path,
        mood: BGMMood
    ) -> Optional[BGMTrack]:
        """Create BGMTrack from local file"""
        try:
            duration = await self._get_audio_duration(str(file_path))

            return BGMTrack(
                file_path=str(file_path),
                title=file_path.stem,
                mood=mood,
                duration=duration,
                tempo=0,  # Unknown
                source=BGMSource.LOCAL_LIBRARY,
                metadata={"indexed_at": str(asyncio.get_event_loop().time())}
            )
        except Exception as e:
            logger.warning(f"Failed to index {file_path}: {e}")
            return None

    async def _get_audio_duration(self, file_path: str) -> float:
        """Get audio file duration"""
        if AUDIO_LIBS_AVAILABLE:
            try:
                duration = librosa.get_duration(path=file_path)
                return duration
            except Exception:
                pass

        # Fallback: estimate from file size (rough approximation)
        try:
            file_size = os.path.getsize(file_path)
            # Rough estimate: ~192kbps = 24KB/s
            estimated_duration = file_size / 24000
            return estimated_duration
        except Exception:
            return 60.0  # Default guess

    async def select_or_generate(
        self,
        settings: BGMSettings,
        output_filename: Optional[str] = None
    ) -> Tuple[str, BGMTrack]:
        """
        Select or generate BGM based on settings

        Args:
            settings: BGM settings
            output_filename: Output filename (without extension)

        Returns:
            Tuple of (output_file_path, track_info)
        """
        if output_filename is None:
            output_filename = f"bgm_{settings.mood.value}_{hashlib.md5(str(settings).encode()).hexdigest()[:8]}"

        output_path = self.output_dir / f"{output_filename}.wav"

        # Try to find suitable track from library
        if settings.source == BGMSource.LOCAL_LIBRARY or settings.source == BGMSource.LOCAL_LIBRARY:
            track = await self._select_from_library(settings)
            if track:
                result_path = await self._process_track(track, settings, output_path)
                return result_path, track

        # Try free music APIs
        if settings.source in [BGMSource.PIXABAY, BGMSource.FREE_MUSIC_ARCHIVE]:
            track = await self._search_free_music(settings)
            if track:
                result_path = await self._process_track(track, settings, output_path)
                return result_path, track

        # Generate procedurally
        track = await self._generate_music(settings, output_path)
        return str(output_path), track

    async def _select_from_library(self, settings: BGMSettings) -> Optional[BGMTrack]:
        """Select best matching track from local library"""
        if not self._is_indexed:
            await self.initialize()

        mood_tracks = self._library_index.get(settings.mood.value, [])

        if not mood_tracks:
            # Try neutral as fallback
            mood_tracks = self._library_index.get(BGMMood.NEUTRAL.value, [])

        if not mood_tracks:
            return None

        # Filter by tempo if specified
        if settings.tempo_range != (60, 120):
            filtered = [
                t for t in mood_tracks
                if t.tempo == 0 or settings.tempo_range[0] <= t.tempo <= settings.tempo_range[1]
            ]
            if filtered:
                mood_tracks = filtered

        # Score tracks by duration match
        def score_track(track: BGMTrack) -> float:
            duration_diff = abs(track.duration - settings.duration)
            # Prefer tracks close to target duration or slightly longer
            if track.duration >= settings.duration:
                return -duration_diff
            else:
                return -duration_diff * 2  # Penalize shorter tracks

        mood_tracks.sort(key=score_track, reverse=True)

        # Add some randomness to selection
        top_n = min(5, len(mood_tracks))
        selected = random.choice(mood_tracks[:top_n]) if top_n > 0 else mood_tracks[0]

        logger.info(f"Selected track from library: {selected.title}")
        return selected

    async def _search_free_music(self, settings: BGMSettings) -> Optional[BGMTrack]:
        """Search for free music from APIs"""
        # Try Pixabay
        if self.pixabay_api_key:
            track = await self._search_pixabay(settings)
            if track:
                return track

        # Try Free Music Archive
        if self.freemusicarchive_api_key:
            track = await self._search_fma(settings)
            if track:
                return track

        return None

    async def _search_pixabay(self, settings: BGMSettings) -> Optional[BGMTrack]:
        """Search Pixabay for free music"""
        mood_params = self.MOOD_PARAMS.get(settings.mood, self.MOOD_PARAMS[BGMMood.NEUTRAL])

        search_query = f"{settings.mood.value} {mood_params.get('genre', 'background')}"

        url = "https://pixabay.com/api/music/"
        params = {
            "key": self.pixabay_api_key,
            "q": search_query,
            "min_duration": int(settings.duration),
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        hits = data.get("hits", [])

                        if hits:
                            # Select best match
                            hit = hits[0]
                            return BGMTrack(
                                file_path=hit.get("audioFile", ""),
                                title=hit.get("name", "Unknown"),
                                mood=settings.mood,
                                duration=float(hit.get("duration", 60)),
                                tempo=0,
                                source=BGMSource.PIXABAY,
                                artist=hit.get("artist", "Unknown"),
                                license="Pixabay License",
                                preview_url=hit.get("audioFile"),
                                metadata=hit
                            )
        except Exception as e:
            logger.warning(f"Pixabay search failed: {e}")

        return None

    async def _search_fma(self, settings: BGMSettings) -> Optional[BGMTrack]:
        """Search Free Music Archive"""
        # FMA API is limited, implement basic search
        # This is a placeholder for actual FMA integration
        logger.warning("Free Music Archive API integration not fully implemented")
        return None

    async def _process_track(
        self,
        track: BGMTrack,
        settings: BGMSettings,
        output_path: Path
    ) -> str:
        """Process track: adjust duration, volume, fades"""
        if not AUDIO_LIBS_AVAILABLE:
            logger.warning("Audio libraries not available, copying file as-is")
            # Simple file copy
            import shutil
            shutil.copy(track.file_path, output_path)
            return str(output_path)

        # Load audio
        y, sr = librosa.load(track.file_path, sr=settings.sample_rate)

        # Adjust duration
        current_duration = librosa.get_duration(y=y, sr=sr)

        if settings.loop and current_duration < settings.duration:
            # Loop to extend
            loops_needed = int(np.ceil(settings.duration / current_duration))
            y = np.tile(y, loops_needed)

        # Trim to exact duration
        target_samples = int(settings.duration * sr)
        if len(y) > target_samples:
            y = y[:target_samples]

        # Apply volume
        y = y * settings.volume

        # Apply fade in
        if settings.fade_in > 0:
            fade_samples = int(settings.fade_in * sr)
            fade_in_curve = np.linspace(0, 1, fade_samples)
            y[:fade_samples] *= fade_in_curve

        # Apply fade out
        if settings.fade_out > 0:
            fade_samples = int(settings.fade_out * sr)
            fade_out_curve = np.linspace(1, 0, fade_samples)
            y[-fade_samples:] *= fade_out_curve

        # Save
        sf.write(str(output_path), y, sr)
        logger.info(f"Processed BGM saved to {output_path}")

        return str(output_path)

    async def _generate_music(
        self,
        settings: BGMSettings,
        output_path: Path
    ) -> BGMTrack:
        """Generate procedural background music"""
        logger.info(f"Generating procedural music for mood: {settings.mood.value}")

        if not SCIPY_AVAILABLE:
            # Generate simple sine wave as fallback
            return await self._generate_simple_tone(settings, output_path)

        mood_params = self.MOOD_PARAMS.get(settings.mood, self.MOOD_PARAMS[BGMMood.NEUTRAL])

        # Get musical parameters
        tempo_range = mood_params["tempo_range"]
        tempo = random.randint(tempo_range[0], tempo_range[1])

        # Generate audio
        sample_rate = settings.sample_rate
        duration = settings.duration
        num_samples = int(duration * sample_rate)
        t = np.linspace(0, duration, num_samples, dtype=np.float32)

        # Create base melody using chord progression
        scale = self._get_scale(mood_params["scale"])

        # Generate chord progression
        audio = np.zeros(num_samples, dtype=np.float32)

        # Add multiple layers
        # 1. Bass line
        bass_freq = self._note_to_freq(scale[0], octave=2)
        audio += self._generate_tone(t, bass_freq, 0.15) * self._generate_envelope(t, 0.5, tempo)

        # 2. Pad/ambience
        pad_notes = [scale[0], scale[2], scale[4]]  # Chord tones
        for note in pad_notes:
            freq = self._note_to_freq(note, octave=4)
            audio += self._generate_tone(t, freq, 0.08) * self._generate_lfo(t, 0.2)

        # 3. Melody (simple arpeggio)
        melody_pattern = [0, 2, 4, 2]  # Arpeggio pattern
        beat_duration = 60.0 / tempo
        samples_per_beat = int(beat_duration * sample_rate)

        for i, beat_start in enumerate(range(0, num_samples, samples_per_beat)):
            note_idx = melody_pattern[i % len(melody_pattern)]
            freq = self._note_to_freq(scale[note_idx], octave=5)
            end_sample = min(beat_start + samples_per_beat, num_samples)
            beat_t = t[beat_start:end_sample]
            audio[beat_start:end_sample] += self._generate_tone(beat_t, freq, 0.1)

        # Normalize
        audio = audio / np.max(np.abs(audio)) * 0.8

        # Apply volume
        audio = audio * settings.volume

        # Apply fades
        if settings.fade_in > 0:
            fade_samples = int(settings.fade_in * sample_rate)
            audio[:fade_samples] *= np.linspace(0, 1, fade_samples)

        if settings.fade_out > 0:
            fade_samples = int(settings.fade_out * sample_rate)
            audio[-fade_samples:] *= np.linspace(1, 0, fade_samples)

        # Convert to 16-bit and save
        audio_int = (audio * 32767).astype(np.int16)
        wavfile.write(str(output_path), sample_rate, audio_int)

        logger.info(f"Generated procedural music: {output_path}")

        return BGMTrack(
            file_path=str(output_path),
            title=f"Generated {settings.mood.value} music",
            mood=settings.mood,
            duration=duration,
            tempo=tempo,
            source=BGMSource.GENERATED,
            metadata={"generation_params": mood_params}
        )

    async def _generate_simple_tone(
        self,
        settings: BGMSettings,
        output_path: Path
    ) -> BGMTrack:
        """Generate simple ambient tone as absolute fallback"""
        sample_rate = settings.sample_rate
        duration = settings.duration
        num_samples = int(duration * sample_rate)
        t = np.linspace(0, duration, num_samples, dtype=np.float32)

        # Simple ambient drone
        freq = 220  # A3
        audio = np.sin(2 * np.pi * freq * t) * 0.3
        audio += np.sin(2 * np.pi * freq * 1.5 * t) * 0.2  # Fifth
        audio += np.sin(2 * np.pi * freq * 2 * t) * 0.15  # Octave

        # Add slow modulation
        modulation = 0.5 + 0.5 * np.sin(2 * np.pi * 0.1 * t)
        audio *= modulation

        # Normalize and apply volume
        audio = audio / np.max(np.abs(audio)) * settings.volume

        # Apply fades
        if settings.fade_in > 0:
            fade_samples = int(settings.fade_in * sample_rate)
            audio[:fade_samples] *= np.linspace(0, 1, fade_samples)

        if settings.fade_out > 0:
            fade_samples = int(settings.fade_out * sample_rate)
            audio[-fade_samples:] *= np.linspace(1, 0, fade_samples)

        # Save as WAV
        audio_int = (audio * 32767).astype(np.int16)
        wavfile.write(str(output_path), sample_rate, audio_int)

        return BGMTrack(
            file_path=str(output_path),
            title="Simple ambient drone",
            mood=settings.mood,
            duration=duration,
            tempo=60,
            source=BGMSource.GENERATED,
        )

    def _get_scale(self, scale_type: str) -> List[int]:
        """Get scale intervals"""
        scales = {
            "major": [0, 2, 4, 5, 7, 9, 11],
            "minor": [0, 2, 3, 5, 7, 8, 10],
            "chromatic": list(range(12)),
            "pentatonic": [0, 2, 4, 7, 9],
        }
        return scales.get(scale_type, scales["major"])

    def _note_to_freq(self, semitone: int, octave: int = 4) -> float:
        """Convert semitone to frequency"""
        # A4 = 440Hz
        a4 = 440
        notes_from_a4 = semitone - 9 + (octave - 4) * 12
        return a4 * (2 ** (notes_from_a4 / 12))

    def _generate_tone(self, t: np.ndarray, freq: float, amplitude: float) -> np.ndarray:
        """Generate a sine wave tone"""
        return amplitude * np.sin(2 * np.pi * freq * t)

    def _generate_envelope(self, t: np.ndarray, attack: float, tempo: int) -> np.ndarray:
        """Generate ADSR envelope"""
        duration = len(t) / 44100  # Assuming 44100 Hz
        beat_duration = 60.0 / tempo

        envelope = np.ones_like(t)
        attack_samples = int(attack * 44100)
        if attack_samples > 0:
            envelope[:attack_samples] = np.linspace(0, 1, attack_samples)

        return envelope

    def _generate_lfo(self, t: np.ndarray, rate: float) -> np.ndarray:
        """Generate low frequency oscillator"""
        return 0.5 + 0.5 * np.sin(2 * np.pi * rate * t)

    async def auto_adjust_volume(
        self,
        bgm_path: str,
        narration_path: str,
        output_path: Optional[str] = None,
        target_ratio: float = 0.25
    ) -> str:
        """
        Auto-adjust BGM volume relative to narration

        Args:
            bgm_path: Path to BGM file
            narration_path: Path to narration audio
            output_path: Output path (defaults to overwriting bgm_path)
            target_ratio: Target BGM/narration volume ratio

        Returns:
            Path to adjusted BGM file
        """
        if not AUDIO_LIBS_AVAILABLE:
            logger.warning("Audio libraries not available for volume adjustment")
            return bgm_path

        output_path = output_path or bgm_path

        # Load both files
        bgm, sr_bgm = librosa.load(bgm_path, sr=None)
        narration, sr_narr = librosa.load(narration_path, sr=None)

        # Calculate RMS (root mean square) for volume estimation
        bgm_rms = np.sqrt(np.mean(bgm ** 2))
        narration_rms = np.sqrt(np.mean(narration ** 2))

        if bgm_rms > 0 and narration_rms > 0:
            # Calculate adjustment factor
            current_ratio = bgm_rms / narration_rms
            adjustment = target_ratio / current_ratio

            # Apply adjustment (with limits)
            adjustment = np.clip(adjustment, 0.1, 2.0)
            bgm = bgm * adjustment

            logger.info(f"Volume adjusted by factor {adjustment:.2f}")

        # Save
        sf.write(output_path, bgm, sr_bgm)
        return output_path

    async def get_mood_recommendations(self, context: str) -> List[BGMMood]:
        """
        Get mood recommendations based on story context

        Args:
            context: Story context or description

        Returns:
            List of recommended moods
        """
        context_lower = context.lower()

        # Keyword-based mood detection
        mood_keywords = {
            BGMMood.HAPPY: ["happy", "joy", "celebration", "fun", "cheerful", "bright", "sunny"],
            BGMMood.SAD: ["sad", "sorrow", "grief", "tragedy", "loss", "tears", "melancholy"],
            BGMMood.DRAMATIC: ["dramatic", "intense", "epic", "climax", "confrontation", "battle"],
            BGMMood.PEACEFUL: ["peaceful", "calm", "serene", "quiet", "gentle", "nature", "relax"],
            BGMMood.ENERGETIC: ["energetic", "fast", "exciting", "action", "rush", "adventure"],
            BGMMood.MYSTERIOUS: ["mystery", "suspense", "unknown", "secret", "dark", "hidden"],
            BGMMood.ROMANTIC: ["love", "romantic", "heart", "passion", "tender", "kiss"],
            BGMMood.TENSE: ["tense", "suspense", "danger", "threat", "fear", "anxiety"],
            BGMMood.INSPIRATIONAL: ["inspire", "hope", "dream", "triumph", "victory", "overcome"],
        }

        scores = {}
        for mood, keywords in mood_keywords.items():
            score = sum(1 for kw in keywords if kw in context_lower)
            if score > 0:
                scores[mood] = score

        # Sort by score
        recommended = sorted(scores.keys(), key=lambda m: scores[m], reverse=True)

        # Always include neutral as fallback
        if BGMMood.NEUTRAL not in recommended:
            recommended.append(BGMMood.NEUTRAL)

        return recommended

    async def list_available_tracks(self, mood: Optional[BGMMood] = None) -> List[BGMTrack]:
        """
        List available tracks in library

        Args:
            mood: Filter by mood (optional)

        Returns:
            List of available tracks
        """
        if not self._is_indexed:
            await self.initialize()

        if mood:
            return self._library_index.get(mood.value, [])

        all_tracks = []
        for tracks in self._library_index.values():
            all_tracks.extend(tracks)

        return all_tracks
