# -*- coding: utf-8 -*-
"""
MiniMax Character Consistency Test
Step 1: LLM이 캐릭터 상세 묘사 생성
Step 2: 캐릭터 참조 이미지 생성
Step 3: 이후 장면에 참조 이미지로 캐릭터 일관성 유지
"""
import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()


# ═══════════════════════════════════════════════════════════════
# Step 1: 캐릭터 상세 묘사 생성
# ═══════════════════════════════════════════════════════════════

CHARACTER_PROMPT = """Based on the story below, create detailed character descriptions that can be used for AI image generation.

STORY:
{story}

Create a detailed description of the main character(s) including:
- Physical appearance (fur color, eye color, distinctive features, build)
- Expressions and emotions they convey
- Visual style consistent with Disney 3D animation

Return ONLY this JSON structure:
{{
    "characters": [
        {{
            "name": "character name",
            "description": "Detailed visual description for AI image generation. Include ALL physical details: fur/hair color, eye color and shape, body build, distinctive markings, clothing style, and how they carry themselves. Be specific enough that an AI can generate a consistent character.",
            "traits": ["trait1", "trait2", "trait3"]
        }}
    ]
}}

IMPORTANT: Write description in English for image generation AI. Be extremely detailed."""


async def generate_character_descriptions(story: str) -> dict:
    """Step 1: 캐릭터 상세 묘사 생성"""
    print("=" * 60)
    print("Step 1: 캐릭터 상세 묘사 생성 (LLM)")
    print("=" * 60)

    from infrastructure.ai import StoryLLMProvider

    provider = StoryLLMProvider()

    prompt = CHARACTER_PROMPT.format(story=story)

    try:
        result = await provider.generate(
            system_prompt="You are a professional character designer for Disney 3D animation.",
            user_message=prompt,
            max_tokens=2048
        )

        # JSON 파싱
        import json
        text = result.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        data = json.loads(text.strip())

        print(f"[OK] 캐릭터 {len(data.get('characters', []))}명 생성됨")
        for char in data.get('characters', []):
            print(f"  - {char['name']}: {char['description'][:80]}...")

        return data

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return {"characters": []}


# ═══════════════════════════════════════════════════════════════
# Step 2: 캐릭터 참조 이미지 생성
# ═══════════════════════════════════════════════════════════════

async def generate_character_reference_image(char_name: str, char_description: str, output_path: str) -> str:
    """Step 2: 캐릭터 참조 이미지 생성"""
    print(f"\n[Step 2] 캐릭터 참조 이미지 생성: {char_name}")

    from infrastructure.api.providers.image.minimax_image import MiniMaxImageClient

    client = MiniMaxImageClient()

    # Disney 3D 스타일 + 캐릭터 묘사
    prompt = f"Disney 3D animation, Pixar quality, {char_description}, character portrait, upper body, clear face visible, vibrant colors, soft cel shading, masterpiece, best quality"

    print(f"    Prompt: {prompt[:80]}...")

    result = await client.generate_and_save(
        prompt=prompt,
        output_path=output_path,
        aspect_ratio="1:1",
    )

    if result.success:
        print(f"    [OK] 참조 이미지 저장: {output_path}")
        return output_path
    else:
        print(f"    [FAIL] {result.error_message}")
        return ""


# ═══════════════════════════════════════════════════════════════
# Step 3: 이후 장면에 참조 이미지로 캐릭터 일관성 유지
# ═══════════════════════════════════════════════════════════════

async def generate_scene_with_character_reference(
    client,
    scene_action: str,
    reference_image_path: str,
    output_path: str,
    aspect_ratio: str = "16:9"
) -> bool:
    """Step 3: 참조 이미지로 캐릭터 일관성 유지しながら 장면 생성"""
    # Disney 3D 스타일 프롬프트
    style_prefix = "Disney 3D animation, Pixar quality, smooth cel shading, vibrant colors, soft lighting, high detail, masterpiece"
    full_prompt = f"{style_prefix}, {scene_action}"

    print(f"    Prompt: {full_prompt[:60]}...")
    print(f"    Reference: {reference_image_path}")

    result = await client.generate_with_reference_and_save(
        prompt=full_prompt,
        reference_image_path=reference_image_path,
        output_path=output_path,
        aspect_ratio=aspect_ratio,
    )

    if result.success:
        print(f"    [OK] 저장됨: {output_path}")
        return True
    else:
        print(f"    [FAIL] {result.error_message}")
        return False


# ═══════════════════════════════════════════════════════════════
# 메인 테스트
# ═══════════════════════════════════════════════════════════════

async def main():
    print("\n" + "=" * 60)
    print("  MiniMax Character Consistency Test")
    print("  캐릭터 일관성 유지 이미지 생성")
    print("=" * 60)

    test_story = """
    옛날 옛날에 호랑이 한 마리가 살았습니다.
    호랑이는 숲의 왕이었고, 황금빛 털에 날카로운 송곳니를 가진 강력한 전사였습니다.
    모든 동물들이 호랑이에게 두려움을 느끼었습니다.
    어느 날, 작은 회색 토끼가 호랑이에게 용기를 보여줍니다.
    """

    # 출력 디렉토리
    output_dir = Path("outputs/character_consistency_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: 캐릭터 상세 묘사 생성
    char_data = await generate_character_descriptions(test_story)

    if not char_data.get('characters'):
        print("\n[FAIL] 캐릭터 생성 실패")
        return

    # Step 2: 각 캐릭터의 참조 이미지 생성
    reference_images = {}
    for i, char in enumerate(char_data['characters']):
        ref_path = output_dir / f"char_{i+1}_{char['name'].replace(' ', '_')}_ref.png"
        ref_path_str = await generate_character_reference_image(
            char['name'],
            char['description'],
            str(ref_path)
        )
        if ref_path_str:
            reference_images[char['name']] = ref_path_str

    if not reference_images:
        print("\n[FAIL] 참조 이미지 생성 실패")
        return

    # Step 3: 장면들 생성 (참조 이미지 사용)
    print("\n" + "=" * 60)
    print("Step 3: 참조 이미지로 장면 생성 (캐릭터 일관성)")
    print("=" * 60)

    # 호랑이 기준 장면들
    tiger_name = char_data['characters'][0]['name']
    tiger_ref = reference_images.get(tiger_name, "")

    scenes = [
        {
            "name": "Scene 1 - 호랑이 등장 (참조 없음)",
            "action": "A majestic golden tiger with fierce golden eyes standing on a rocky cliff, mouth open in a mighty roar",
            "use_ref": False
        },
        {
            "name": "Scene 2 - 호랑이 숲을 걸어다님 (참조 있음)",
            "action": "A powerful golden tiger walking majestically through misty forest, dramatic lighting",
            "use_ref": True
        },
        {
            "name": "Scene 3 - 호랑이 토끼를 발견 (참조 있음)",
            "action": "A curious golden tiger lowering its massive head to look at a small gray rabbit, intense eyes",
            "use_ref": True
        },
        {
            "name": "Scene 4 - 호랑이 숙종 (참조 있음)",
            "action": "A gentle golden tiger sitting peacefully, soft expression, morning sunlight",
            "use_ref": True
        },
    ]

    from infrastructure.api.providers.image.minimax_image import MiniMaxImageClient
    client = MiniMaxImageClient()

    for i, scene in enumerate(scenes, start=1):
        print(f"\n[*] {scene['name']}")

        if scene['use_ref'] and tiger_ref:
            # 참조 이미지로 생성
            await generate_scene_with_character_reference(
                client,
                scene['action'],
                tiger_ref,
                str(output_dir / f"scene_{i:02d}_with_ref.png"),
                aspect_ratio="16:9"
            )
        else:
            # 참조 없이 생성 (첫 번째 장면)
            style_prefix = "Disney 3D animation, Pixar quality, smooth cel shading, vibrant colors, soft lighting, high detail, masterpiece"
            prompt = f"{style_prefix}, {scene['action']}"

            print(f"    Prompt: {prompt[:60]}...")

            result = await client.generate_and_save(
                prompt=prompt,
                output_path=str(output_dir / f"scene_{i:02d}_without_ref.png"),
                aspect_ratio="16:9",
            )

            if result.success:
                print(f"    [OK] 저장됨: scene_{i:02d}_without_ref.png")

    print("\n" + "=" * 60)
    print("  완료!")
    print(f"  결과: {output_dir}")
    print("=" * 60)

    print("\n[비교]")
    print("  scene_01_without_ref.png - 참조 없이 생성 (첫 번째 호랑이)")
    print("  scene_02_with_ref.png - 참조 이미지로 생성 (같은 호랑이?)")
    print("  scene_03_with_ref.png - 참조 이미지로 생성 (같은 호랑이?)")
    print("  scene_04_with_ref.png - 참조 이미지로 생성 (같은 호랑이?)")
    print("\n  캐릭터 일관성이 유지되었는지 확인해보세요!")


if __name__ == "__main__":
    asyncio.run(main())