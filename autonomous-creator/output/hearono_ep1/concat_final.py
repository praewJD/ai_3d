# -*- coding: utf-8 -*-
"""
Hearono Episode 1 - Final Episode Concatenation (FFmpeg)
Concatenate all 4 scenes with audio into a single episode video
"""
import subprocess
import os
from pathlib import Path
from datetime import datetime

# Paths
OUTPUT_DIR = Path("D:/AI-Video/autonomous-creator/output/hearono_ep1")
FINAL_DIR = OUTPUT_DIR / "final"

# Scene files with audio (in order)
SCENES = [
    {"video": "scene_01_with_audio.mp4", "desc": "Scene 1: Raven enters"},
    {"video": "scene_02_with_audio.mp4", "desc": "Scene 2: Hearono reveals"},
    {"video": "scene_03_with_audio.mp4", "desc": "Scene 3: Final battle"},
    {"video": "scene_04_with_audio.mp4", "desc": "Scene 4: Headphones"},
]

def main():
    print("=" * 60)
    print("  Hearono Episode 1 - Final Episode Creation")
    print("=" * 60)
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Output: {FINAL_DIR}")
    print(f"  Scenes to merge: {len(SCENES)}")

    # Create file list for concat demuxer
    file_list = []
    for scene in SCENES:
        video_path = FINAL_DIR / scene["video"]
        if video_path.exists():
            file_list.append(str(video_path))
            print(f"  Found: {scene['desc']}: {video_path}")
        else:
            print(f"  Warning: {video_path} not found!")
            return

    if not file_list:
        print("  No files to concatenate!")
        return

    # Create concat list file (Windows paths need forward slashes)
    concat_file = FINAL_DIR / "concat_list.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for video_path in file_list:
            # Use forward slashes for ffmpeg
            video_path_unix = video_path.replace("\\", "/")
            f.write(f"file '{video_path_unix}'\n")
    print(f"  Created concat list with {len(file_list)} files")

    # Output file
    output_path = FINAL_DIR / "hearono_ep1_final.mp4"

    # Run ffmpeg concat
    print("\n  Running ffmpeg concat...")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c:v", "libx264",
        "-c:a", "aac",
        str(output_path)
    ]

    cmd_str = " ".join(cmd)
    print(f"  Command: {cmd_str}")
    result = subprocess.run(cmd, check=True, capture_output=True)

    # Check output
    if os.path.exists(output_path):
        size = os.path.getsize(output_path) / (1024 * 1024)
        print("\n" + "=" * 60)
        print("  Final Episode Created!")
        print("=" * 60)
        print(f"  Output: {output_path}")
        print(f"  Size: {size:.2f} MB")
        print("=" * 60)
    else:
        print("  Error creating final video!")

    # Clean up
    if os.path.exists(concat_file):
        os.remove(concat_file)
        print(f"  Cleaned up: {concat_file}")

if __name__ == "__main__":
    main()
