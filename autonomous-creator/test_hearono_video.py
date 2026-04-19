# -*- coding: utf-8 -*-
"""
Hearono Episode 1 - Final Video Generation (MoviePy Direct)
"""
import sys
import os
from pathlib import Path
from datetime import datetime

os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.path.insert(0, str(Path(__file__).parent))

OUTPUT_DIR = Path("D:/AI-Video/autonomous-creator/output/hearono_ep1")
IMAGES_DIR = OUTPUT_DIR / "images"
AUDIO_DIR = OUTPUT_DIR / "audio"
FINAL_DIR = OUTPUT_DIR / "final"

# 장면 구성
SCENES = [
    {
        "name": "scene_01_raven_enters",
        "image": "scene_01_raven_enters.png",
        "audio": None,
        "duration": 5.0
    },
    {
        "name": "scene_02_hearono_reveals",
        "image": "scene_02_hearono_reveals.png",
        "audio": "raven_01.wav",
        "duration": 5.0
    },
    {
        "name": "scene_03_final_battle",
        "image": "scene_03_final_battle.png",
        "audio": "eknat_01.wav",
        "duration": 5.0
    },
    {
        "name": "scene_04_headphones",
        "image": "scene_04_headphones.png",
        "audio": "hearono_01.wav",
        "duration": 8.0
    }
]


def main():
    """메인 실행"""
    print("="*60)
    print("  Hearono Episode 1 - Final Video Generation")
    print("="*60)
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
    from PIL import Image
    import numpy as np

    FINAL_DIR.mkdir(parents=True, exist_ok=True)

    print("\n[1/3] Creating video segments...")

    clips = []

    for i, scene in enumerate(SCENES):
        print(f"\n  Scene {i+1}: {scene['name']}")

        # 이미지 로드
        image_path = IMAGES_DIR / scene["image"]
        if not image_path.exists():
            print(f"    Image not found!")
            continue

        img = Image.open(image_path)
        img_array = np.array(img)

        # 오디오 확인
        audio_path = AUDIO_DIR / scene["audio"] if scene["audio"] else None
        duration = scene["duration"]

        if audio_path and audio_path.exists():
            audio_clip = AudioFileClip(str(audio_path))
            duration = audio_clip.duration + 0.5
            print(f"    Audio: {audio_clip.duration:.1f}s → Duration: {duration:.1f}s")
        else:
            audio_clip = None
            print(f"    No audio → Duration: {duration:.1f}s")

        # 이미지 클립 생성
        clip = ImageClip(img_array, duration=duration)

        # 오디오 추가
        if audio_clip:
            clip = clip.with_audio(audio_clip)

        clips.append(clip)
        print(f"    Clip created!")

    print(f"\n[2/3] Concatenating {len(clips)} clips...")

    if not clips:
        print("  No clips to process!")
        return

    final_video = concatenate_videoclips(clips, method="compose")

    total_duration = sum(c.duration for c in clips)
    print(f"  Total duration: {total_duration:.1f}s")

    print("\n[3/3] Writing final video...")

    output_path = FINAL_DIR / "hearono_ep1.mp4"

    final_video.write_videofile(
        str(output_path),
        fps=24,
        codec='libx264',
        audio_codec='aac',
        threads=4
    )

    # 정리
    final_video.close()
    for clip in clips:
        clip.close()

    size = os.path.getsize(output_path) / (1024 * 1024)

    print("\n" + "="*60)
    print("  Video Generation Complete!")
    print("="*60)
    print(f"  Output: {output_path}")
    print(f"  Size: {size:.1f} MB")
    print(f"  Duration: {total_duration:.1f}s")


if __name__ == "__main__":
    main()
