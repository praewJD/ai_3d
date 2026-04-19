# -*- coding: utf-8 -*-
"""
Full Pipeline Test: Audio + Video

전체 파이프라인 테스트 (MoviePy 2.x 호환)
1. Thai TTS (F5-TTS-THAI)
2. Placeholder Images
3. Video Composition (MoviePy)
"""
import sys
import io

# Windows UTF-8 설정
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import asyncio
from pathlib import Path
import os

# 출력 디렉토리
OUTPUT_DIR = Path(r"D:\AI-Video\autonomous-creator\output\full_pipeline_test")


async def test_tts():
    """Step 1: Thai TTS 테스트"""
    print("\n" + "=" * 60)
    print("Step 1: Thai TTS Generation")
    print("=" * 60)

    from infrastructure.tts.factory import TTSFactory
    from core.domain.entities.audio import VoiceSettings

    tts = TTSFactory.create("th")
    voice = VoiceSettings(language="th", speed=1.0)

    # 테스트 텍스트 (짧게)
    texts = [
        "สวัสดีค่ะ ยินดีต้อนรับ",
        "นี่คือการทดสอบ",
        "ขอบคุณมากค่ะ"
    ]

    audio_dir = OUTPUT_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    audio_paths = []
    for i, text in enumerate(texts):
        output_path = str(audio_dir / f"scene_{i:03d}.wav")
        print(f"\n  [{i+1}/{len(texts)}] Generating: {text}")

        await tts.generate(text, voice, output_path)
        audio_paths.append(output_path)

        size = os.path.getsize(output_path) / 1024
        print(f"    ✓ Saved: {size:.1f} KB")

    print(f"\n✅ TTS Complete: {len(audio_paths)} files")
    return audio_paths


async def create_placeholder_images(count):
    """Step 2: 플레이스홀더 이미지 생성"""
    print("\n" + "=" * 60)
    print("Step 2: Creating Placeholder Images")
    print("=" * 60)

    from PIL import Image, ImageDraw

    image_dir = OUTPUT_DIR / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    colors = [
        (255, 180, 100),  # Golden sunset
        (100, 150, 200),  # Blue sky
        (200, 130, 100),  # Warm earth
    ]

    image_paths = []
    for i in range(count):
        # 그라데이션 배경
        img = Image.new('RGB', (576, 1024), colors[i % len(colors)])
        draw = ImageDraw.Draw(img)

        # 간단한 패턴 (선)
        for y in range(0, 1024, 40):
            intensity = int(50 + 100 * (y / 1024))
            draw.line([(0, y), (576, y)], fill=(intensity, intensity, intensity), width=1)

        # 장면 번호
        text = f"Scene {i+1}"
        # 중앙에 원 그리기
        draw.ellipse([238, 462, 338, 562], fill=(255, 255, 255, 180))
        draw.text((288, 512), text, fill=(50, 50, 50), anchor="mm")

        output_path = str(image_dir / f"scene_{i:03d}.png")
        img.save(output_path, quality=95)

        size = os.path.getsize(output_path) / 1024
        print(f"  Scene {i}: {size:.1f} KB")

        image_paths.append(output_path)

    print(f"\n✅ Created {len(image_paths)} placeholder images")
    return image_paths


async def test_video_composition(audio_paths, image_paths):
    """Step 3: 비디오 합성 테스트"""
    print("\n" + "=" * 60)
    print("Step 3: Video Composition (MoviePy 2.x)")
    print("=" * 60)

    # MoviePy 2.x imports
    from moviepy.video.VideoClip import ImageClip
    from moviepy.video.compositing.CompositeVideoClip import concatenate_videoclips
    from moviepy.audio.io.AudioFileClip import AudioFileClip

    video_dir = OUTPUT_DIR / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)

    # 세그먼트 생성
    clips = []
    total_duration = 0

    for i in range(min(len(audio_paths), len(image_paths))):
        print(f"\n  Processing scene {i}...")

        # 오디오 길이 확인
        audio = AudioFileClip(audio_paths[i])
        duration = audio.duration
        print(f"    Audio duration: {duration:.2f}s")

        # 이미지 클립 생성
        clip = ImageClip(image_paths[i], duration=duration)
        clip = clip.resized((1080, 1920))

        # 오디오 추가
        clip = clip.with_audio(audio)

        clips.append(clip)
        total_duration += duration

    if not clips:
        print("❌ No clips to compose")
        return None

    # 최종 합성
    print(f"\n  Composing {len(clips)} clips...")

    final = concatenate_videoclips(clips, method="compose")

    output_path = str(video_dir / "final_output.mp4")

    print(f"  Rendering to: {output_path}")
    print(f"  Total duration: {total_duration:.2f}s")

    final.write_videofile(
        output_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="medium",
        bitrate="5000k",
        logger=None
    )

    # 정리
    final.close()
    for clip in clips:
        clip.close()

    size = os.path.getsize(output_path) / 1024 / 1024
    print(f"\n✅ Video Complete!")
    print(f"  File: {output_path}")
    print(f"  Size: {size:.2f} MB")
    print(f"  Duration: {total_duration:.2f}s")

    return output_path


async def test_full_pipeline():
    """전체 파이프라인 테스트"""
    print("=" * 60)
    print("🎬 Full Pipeline Test: TTS → Image → Video")
    print("=" * 60)
    print(f"Output: {OUTPUT_DIR}")

    # Step 1: TTS
    audio_paths = await test_tts()

    if not audio_paths:
        print("❌ TTS failed, stopping pipeline")
        return

    # Step 2: Placeholder Images
    image_paths = await create_placeholder_images(len(audio_paths))

    # Step 3: Video Composition
    video_path = await test_video_composition(audio_paths, image_paths)

    # 최종 요약
    print("\n" + "=" * 60)
    print("📊 Pipeline Summary")
    print("=" * 60)
    print(f"  Audio files: {len(audio_paths)}")
    print(f"  Image files: {len(image_paths)}")
    print(f"  Video: {'✅ Created' if video_path else '❌ Failed'}")
    print(f"\n  Output directory: {OUTPUT_DIR}")

    # 파일 목록
    print("\n📁 Generated Files:")
    for f in sorted(OUTPUT_DIR.rglob("*")):
        if f.is_file():
            size = f.stat().st_size / 1024
            if size > 1024:
                print(f"  {f.relative_to(OUTPUT_DIR)}: {size/1024:.2f} MB")
            else:
                print(f"  {f.relative_to(OUTPUT_DIR)}: {size:.2f} KB")

    if video_path:
        print("\n🎉 Full pipeline test SUCCESS!")
        print(f"\n🎬 Final video: {video_path}")
    else:
        print("\n⚠️ Pipeline completed with issues")


if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
