# -*- coding: utf-8 -*-
"""
FramePack 간단 실행 스크립트
이미지 → 비디오 변환
"""
import os
import sys

# FramePack 환경 설정
os.chdir(r"D:\AI-Video\FramePack\FramePack_Official\webui")
os.environ['HF_HOME'] = r"D:\AI-Video\FramePack\hf_download"

print("=" * 60)
print("FramePack WebUI 실행")
print("=" * 60)
print("\n사용 방법:")
print("1. 브라우저가 자동으로 열리면 http://localhost:7860 접속")
print("2. Input Image에 다음 이미지들을 순서대로 업로드:")
print("   - scene_morning_start.png")
print("   - scene_forest_discovery.png")
print("   - scene_rain_shelter.png")
print("   - scene_sunset_return.png")
print("\n3. 설정:")
print("   - Total Second Length: 5")
print("   - Steps: 25")
print("   - Seed: 31337")
print("4. Generate 클릭")
print("\n이미지 위치:")
print(r"D:\AI-Video\autonomous-creator\output\story_videos\robot_adventure_20260403_232612\images")
print("\n" + "=" * 60)

# FramePack 실행
os.system("python demo_gradio.py")
