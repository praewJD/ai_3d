# -*- coding: utf-8 -*-
"""
Thai TTS + Full Pipeline Test

전체 파이프라인 테스트 (태국어)
"""
import sys
import io

# Windows UTF-8 설정
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import asyncio
from pathlib import Path

# 출력 디렉토리
OUTPUT_DIR = Path(r"D:\AI-Video\autonomous-creator\output\thai_test")


async def test_thai_tts_only():
    """Thai TTS만 테스트"""
    print("=" * 60)
    print("Test 1: Thai TTS Only")
    print("=" * 60)

    from infrastructure.tts.factory import TTSFactory
    from core.domain.entities.audio import VoiceSettings

    # Thai TTS 엔진 생성
    print("\n[1/3] Creating Thai TTS engine...")
    tts = TTSFactory.create("th")
    print(f"  Engine: {tts.get_engine_name()}")

    # 의존성 체크
    print("\n[2/3] Checking dependencies...")
    deps = tts.check_dependencies()
    for k, v in deps.items():
        status = "✅" if v else "❌"
        print(f"  {status} {k}: {v}")

    if not all(deps.values()):
        print("\n❌ Dependencies not met!")
        return None

    # TTS 생성
    print("\n[3/3] Generating Thai speech...")
    voice = VoiceSettings(
        language="th",
        speed=1.0
    )

    text = "สวัสดีค่ะ ยินดีที่ได้รู้จักทุกท่านนะคะ ขอบคุณมากค่ะ"
    output_path = str(OUTPUT_DIR / "test_tts.wav")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    result = await tts.generate(text, voice, output_path)

    import os
    size = os.path.getsize(result) / 1024

    print(f"\n✅ SUCCESS!")
    print(f"  File: {result}")
    print(f"  Size: {size:.2f} KB")

    return result


async def test_full_pipeline():
    """전체 파이프라인 테스트"""
    print("\n" + "=" * 60)
    print("Test 2: Full Pipeline (Story → Video)")
    print("=" * 60)

    from core.domain.entities.story import Story, Script, Scene
    from core.domain.entities.audio import VoiceSettings
    from infrastructure.tts.factory import TTSFactory

    # 테스트 스토리
    print("\n[1/4] Creating test story...")
    story = Story(
        id="thai_test_001",
        title="Thai Test Story",
        content="สวัสดีค่ะ นี่คือการทดสอบระบบสร้างวิดีโออัตโนมัติ",
        language="th"
    )
    print(f"  Story ID: {story.id}")
    print(f"  Language: {story.language}")

    # 스크립트 생성 (간단 버전)
    print("\n[2/4] Creating script...")
    script = Script(
        scenes=[
            Scene(
                description="Opening scene",
                narration="สวัสดีค่ะ ยินดีต้อนรับสู่วิดีโอของเรา",
                image_prompt="beautiful thai temple at sunset, golden hour, cinematic",
                duration=5.0,
                order=0
            ),
            Scene(
                description="Closing scene",
                narration="ขอบคุณมากค่ะ แล้วพบกันใหม่",
                image_prompt="thai landscape mountains, peaceful, serene",
                duration=4.0,
                order=1
            )
        ],
        total_duration=9.0,
        language="th"
    )
    print(f"  Scenes: {len(script.scenes)}")

    # TTS 생성
    print("\n[3/4] Generating Thai audio...")
    tts = TTSFactory.create("th")
    voice = VoiceSettings(language="th", speed=1.0)

    audio_paths = []
    audio_dir = OUTPUT_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    for i, scene in enumerate(script.scenes):
        output_path = str(audio_dir / f"scene_{i:03d}.wav")
        print(f"  Scene {i}: {scene.narration[:30]}...")
        await tts.generate(scene.narration, voice, output_path)
        audio_paths.append(output_path)

    print(f"  Generated: {len(audio_paths)} audio files")

    # 결과 요약
    print("\n[4/4] Summary...")
    print(f"  Story: {story.title}")
    print(f"  Audio files: {len(audio_paths)}")

    for i, path in enumerate(audio_paths):
        import os
        size = os.path.getsize(path) / 1024
        print(f"    - {Path(path).name}: {size:.2f} KB")

    print(f"\n✅ Pipeline test completed!")
    print(f"  Output dir: {OUTPUT_DIR}")

    return audio_paths


async def main():
    """메인 테스트 실행"""
    print("🚀 Thai TTS + Pipeline Test\n")

    try:
        # Test 1: TTS만
        await test_thai_tts_only()

        # Test 2: 전체 파이프라인
        await test_full_pipeline()

        print("\n" + "=" * 60)
        print("🎉 All tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
