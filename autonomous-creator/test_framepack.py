# -*- coding: utf-8 -*-
"""
FramePack 테스트 스크립트

D:\AI-Video\FramePack에 설치된 FramePack으로 비디오 생성 테스트
"""
import sys
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import asyncio
from pathlib import Path
import os


async def test_framepack_installation():
    """FramePack 설치 확인"""
    print("=" * 60)
    print("FramePack Installation Check")
    print("=" * 60)

    framepack_dir = Path(r"D:\AI-Video\FramePack")

    print(f"\nFramePack directory: {framepack_dir}")

    # 필수 파일 확인
    required_files = [
        "demo_gradio.py",
        "requirements.txt",
        "diffusers_helper",
    ]

    all_exists = True
    for f in required_files:
        path = framepack_dir / f
        exists = path.exists()
        status = "OK" if exists else "MISSING"
        print(f"  {f}: {status}")
        if not exists:
            all_exists = False

    if all_exists:
        print("\nAll required files found!")
        return True
    else:
        print("\nMissing files. Please check installation.")
        return False


async def test_svd_optimized():
    """SVD 6GB 최적화 테스트"""
    print("\n" + "=" * 60)
    print("SVD 6GB Optimized Test")
    print("=" * 60)

    try:
        from infrastructure.video.svd_generator_optimized import SVDGeneratorOptimized
        import torch

        # VRAM 확인
        if torch.cuda.is_available():
            vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            print(f"\nGPU: {torch.cuda.get_device_name(0)}")
            print(f"VRAM: {vram:.1f} GB")
        else:
            print("\nNo CUDA available")
            return None

        # 생성기 생성
        generator = SVDGeneratorOptimized()

        # 사용 가능 여부 확인
        available = await generator.is_available()
        print(f"\nSVD Available: {available}")

        if not available:
            print("SVD not available on this system")
            return None

        # 테스트 이미지 필요 (있으면 사용, 없으면 생성)
        output_dir = Path(r"D:\AI-Video\autonomous-creator\output\video_test")
        output_dir.mkdir(parents=True, exist_ok=True)

        test_image = output_dir / "test_image.png"

        if not test_image.exists():
            # 간단한 테스트 이미지 생성
            from PIL import Image, ImageDraw
            img = Image.new('RGB', (576, 1024), color=(40, 50, 80))
            draw = ImageDraw.Draw(img)
            draw.text((288, 512), "Test", fill=(255, 255, 255), anchor="mm")
            img.save(test_image)
            print(f"Created test image: {test_image}")

        # 비디오 생성 테스트
        output_video = str(output_dir / "test_svd_video.mp4")

        print(f"\nGenerating video...")
        print(f"  Input: {test_image}")
        print(f"  Output: {output_video}")
        print(f"  Frames: 12 (ultra-low mode)")

        result = await generator.generate_video(
            str(test_image),
            output_video,
            num_frames=12,
            fps=8,
            motion_bucket_id=100
        )

        if os.path.exists(result):
            size = os.path.getsize(result) / 1024
            print(f"\nSuccess!")
            print(f"  File: {result}")
            print(f"  Size: {size:.1f} KB")
            return result
        else:
            print("Video generation failed")
            return None

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return None


async def run_framepack_demo():
    """FramePack Gradio 데모 실행"""
    print("\n" + "=" * 60)
    print("FramePack Gradio Demo")
    print("=" * 60)

    framepack_dir = Path(r"D:\AI-Video\FramePack")

    print(f"\nFramePack directory: {framepack_dir}")
    print("\nTo run FramePack:")
    print(f"  1. Open terminal")
    print(f"  2. cd {framepack_dir}")
    print(f"  3. python demo_gradio.py")
    print(f"\nOr use the Windows one-click package:")
    print(f"  Download: https://github.com/lllyasviel/FramePack/releases")
    print(f"\nNote: First run will download ~30GB of models from HuggingFace")


async def main():
    print("=" * 60)
    print("Video Generation Test Suite")
    print("  1. FramePack Installation Check")
    print("  2. SVD 6GB Optimized Test")
    print("  3. FramePack Demo Guide")
    print("=" * 60)

    # Test 1: FramePack 설치 확인
    framepack_ok = await test_framepack_installation()

    # Test 2: SVD 최적화 테스트
    if framepack_ok:
        svd_result = await test_svd_optimized()

    # Test 3: FramePack 데모 가이드
    await run_framepack_demo()

    # 요약
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"FramePack Installed: {'Yes' if framepack_ok else 'No'}")
    print(f"SVD Test: {'Completed' if svd_result else 'Not run'}")

    print("\nNext Steps:")
    print("1. To use FramePack:")
    print("   cd D:\\AI-Video\\FramePack")
    print("   python demo_gradio.py")
    print("2. Or integrate SVD into your pipeline")


    print("3. Test with actual images from your storyboard")


if __name__ == "__main__":
    asyncio.run(main())
