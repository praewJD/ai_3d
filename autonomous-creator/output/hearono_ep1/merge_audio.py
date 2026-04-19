# -*- coding: utf-8 -*-
"""
Hearono Episode 1 - Audio Merger

FramePack 영상에 태국어 TTS 오디오 입히기
"""
import subprocess
from pathlib import Path

OUTPUT_DIR = Path("D:/AI-Video/autonomous-creator/output/hearono_ep1")
VIDEO_DIR = OUTPUT_DIR / "final"
AUDIO_DIR = OUTPUT_DIR / "audio"

# 장면 구성 (영상, 오디오 매칭)
SCENES = [
    {
        "video": "scene_01_raven_enters_framepack.mp4",
        "audio": None,  # 첫 장면은 대사 없음
        "output": "scene_01_with_audio.mp4"
    },
    {
        "video": "scene_02_hearono_reveals_framepack.mp4",
        "audio": "raven_01.wav",
        "output": "scene_02_with_audio.mp4"
    },
    {
        "video": "scene_03_final_battle_framepack.mp4",
        "audio": "eknat_01.wav",
        "output": "scene_03_with_audio.mp4"
    },
    {
        "video": "scene_04_headphones_framepack.mp4",
        "audio": "hearono_01.wav",
        "output": "scene_04_with_audio.mp4"
    }
]


def merge_audio(video_path: str, audio_path: str, output_path: str):
    """ffmpeg로 영상에 오디오 입히기"""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        output_path
    ]
    subprocess.run(cmd, check=True)


def main():
    print("=" * 50)
    print("Hearono Episode 1 - Audio Merger")
    print("=" * 50)

    for i, scene in enumerate(SCENES):
        print(f"\nScene {i+1}:")

        video_path = VIDEO_DIR / scene["video"]
        output_path = VIDEO_DIR / scene["output"]

        if not video_path.exists():
            print(f"  Video not found: {video_path}")
            continue

        if scene["audio"]:
            audio_path = AUDIO_DIR / scene["audio"]
            if audio_path.exists():
                print(f"  Merging: {scene['video']} + {scene['audio']}")
                merge_audio(str(video_path), str(audio_path), str(output_path))
                print(f"  Output: {output_path}")
            else:
                print(f"  Audio not found: {audio_path}")
        else:
            print(f"  No audio for this scene, copying...")
            import shutil
            shutil.copy(video_path, output_path)
            print(f"  Output: {output_path}")

    print("\n" + "=" * 50)
    print("Audio merge complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
