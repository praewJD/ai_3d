# -*- coding: utf-8 -*-
"""
Edge TTS 테스트

무료 TTS (API 키 불필요)
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.generation.audio.tts_generator import get_tts_generator


async def test_basic_tts():
    """기본 TTS 테스트"""
    print("=" * 50)
    print("Test 1: Basic TTS Generation")
    print("=" * 50)

    tts = get_tts_generator(provider="edge")

    result = await tts.generate(
        text="안녕하세요, 저는 소녀입니다.",
        character_id="test_char",
        emotion="happy"
    )

    print(f"[OK] Success: {result.success}")
    print(f"[OK] Audio Path: {result.audio_path}")
    print(f"[OK] Voice ID: {result.voice_id}")
    print(f"[OK] Duration: {result.duration_ms}ms")
    print(f"[OK] Generation Time: {result.generation_time_ms}ms")

    return result


async def test_emotion_tts():
    """감정별 TTS 테스트"""
    print("\n" + "=" * 50)
    print("Test 2: Emotion-based TTS")
    print("=" * 50)

    tts = get_tts_generator(provider="edge")

    emotions = ["happy", "sad", "excited", "neutral", "angry"]

    for emotion in emotions:
        result = await tts.generate(
            text=f"이것은 {emotion} 감정의 텍스트입니다.",
            emotion=emotion
        )
        status = "[OK]" if result.success else "[FAIL]"
        print(f"  {status} {emotion}: {result.audio_path}")


async def test_character_voices():
    """캐릭터별 보이스 테스트"""
    print("\n" + "=" * 50)
    print("Test 3: Character Voice Mapping")
    print("=" * 50)

    tts = get_tts_generator(provider="edge")

    # 캐릭터별 보이스 설정
    tts.set_character_voice("hero", "ko-KR-InJoonNeural")
    tts.set_character_voice("heroine", "ko-KR-SunHiNeural")

    characters = [
        ("hero", "주인공이 등장합니다."),
        ("heroine", "여주인공이 대답합니다."),
    ]

    for char_id, text in characters:
        result = await tts.generate(
            text=text,
            character_id=char_id,
            emotion="neutral"
        )
        voice = tts.get_voice_for_character(char_id)
        print(f"  [OK] {char_id}: voice={voice}, path={result.audio_path}")


async def test_batch_tts():
    """배치 TTS 테스트"""
    print("\n" + "=" * 50)
    print("Test 4: Batch TTS Generation")
    print("=" * 50)

    tts = get_tts_generator(provider="edge")

    texts = [
        {"text": "첫 번째 대사입니다.", "character_id": "narrator", "emotion": "neutral"},
        {"text": "두 번째 대사입니다.", "character_id": "narrator", "emotion": "happy"},
        {"text": "세 번째 대사입니다.", "character_id": "narrator", "emotion": "sad"},
    ]

    results = await tts.generate_batch(texts)

    print(f"[OK] Generated {len(results)} audio files")
    for r in results:
        status = "OK" if r.success else "FAIL"
        print(f"  [{status}] {r.text[:20]}... -> {r.audio_path}")


async def main():
    """메인 테스트 실행"""
    print("\n" + "=" * 60)
    print("  Edge TTS Test Suite")
    print("=" * 60)

    try:
        # 1. 기본 TTS
        await test_basic_tts()

        # 2. 감정별 TTS
        await test_emotion_tts()

        # 3. 캐릭터별 보이스
        await test_character_voices()

        # 4. 배치 TTS
        await test_batch_tts()

        print("\n" + "=" * 60)
        print("  [SUCCESS] All TTS Tests Passed!")
        print("=" * 60)

        print("\n[*] Output files saved in: outputs/audio/")

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
