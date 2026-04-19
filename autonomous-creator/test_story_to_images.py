# -*- coding: utf-8 -*-
"""
Story to Images Test - 대본으로 이미지 생성 테스트
"""
import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()


async def generate_story():
    """대본 생성"""
    print("=" * 60)
    print("Step 1: 대본 생성")
    print("=" * 60)

    from infrastructure.ai import StoryLLMProvider
    from infrastructure.story import UnifiedStoryCompiler, TargetFormat

    provider = StoryLLMProvider()
    compiler = UnifiedStoryCompiler(llm_provider=provider)

    test_story = "옛날 옛날에 호랑이 한 마리가 살았습니다. 호랑이는 숲의 왕이었고, 모든 동물들이 두려워했습니다. 어느 날, 작은 토끼가 호랑이에게 용기를 보여줍니다."

    print(f"[*] 스토리: {test_story[:50]}...")

    result = await compiler.compile(
        raw_story=test_story,
        target_format=TargetFormat.SHORTS,
        language="ko"
    )

    if result.success:
        print(f"[OK] 대본 생성 성공!")
        print(f"     - Title: {result.story_spec.title}")
        print(f"     - Scenes: {len(result.story_spec.scenes)}")
        return result.story_spec
    else:
        print(f"[FAIL] {result.error}")
        return None


async def generate_images_from_story(story_spec):
    """대본에서 이미지 생성"""
    print("\n" + "=" * 60)
    print("Step 2: 이미지 생성")
    print("=" * 60)

    from infrastructure.image.sdxl_generator import SDXLGenerator
    from infrastructure.asset.style_preset import StylePresetAsset

    # SDXL 생성기 생성
    generator = SDXLGenerator()
    await generator.load_model()

    print(f"[OK] 이미지 생성기: {type(generator).__name__}")

    # Disney 3D 스타일 프리셋 생성
    preset = StylePresetAsset(
        id="disney_3d",
        name="Disney 3D",
        description="Disney 3D Animation Style",
        base_prompt="Disney 3D animation style, Pixar quality, smooth cel shading, vibrant colors, soft lighting, high detail, masterpiece, best quality",
        negative_prompt="realistic photo, live action, western cartoon, anime, dark, gritty, photorealistic, low quality, blurry",
        style_type="disney_3d",
        cfg_scale=7.5,
        steps=25,
    )

    # 출력 디렉토리
    output_dir = Path("outputs/story_images")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 씬별 이미지 생성
    for i, scene in enumerate(story_spec.scenes):
        print(f"\n[*] Scene {i+1}/{len(story_spec.scenes)}")
        print(f"    Action: {scene.action[:60]}...")

        # 프롬프트 조합
        full_prompt = f"{preset.base_prompt}, {scene.action}"
        output_path = output_dir / f"scene_{i+1:02d}.png"

        try:
            result_image = await generator.generate(
                prompt=full_prompt,
                preset=preset,
                output_path=str(output_path),
                width=1024,
                height=1024,
                use_ip_adapter=False,  # IP-Adapter 없이 기본 생성
            )

            if result_image:
                print(f"    [OK] 저장됨: {output_path}")
            else:
                print(f"    [FAIL] 이미지 생성 실패")

        except Exception as e:
            print(f"    [ERROR] {e}")
            import traceback
            traceback.print_exc()

    print(f"\n[*] 모든 이미지 저장 완료: {output_dir}")


async def main():
    print("\n" + "=" * 60)
    print("  Story to Images Test - 대본 → 이미지 생성")
    print("=" * 60)

    # Step 1: 대본 생성
    story_spec = await generate_story()

    if story_spec is None:
        print("\n[FAIL] 대본 생성 실패 - 이미지 생성 중단")
        return

    # Step 2: 이미지 생성
    await generate_images_from_story(story_spec)

    print("\n" + "=" * 60)
    print("  완료!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())