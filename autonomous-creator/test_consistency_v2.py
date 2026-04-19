# -*- coding: utf-8 -*-
"""
Character Consistency Test v2
수정 후 1장 생성 확인
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from infrastructure.api.providers.image.minimax_image import MiniMaxImageClient


async def test():
    ref_image = "outputs/character_consistency_test/char_1_Shan,_the_Golden_Tiger_ref.png"

    if not Path(ref_image).exists():
        print(f"[ERROR] 참조 이미지 없음")
        return

    client = MiniMaxImageClient()

    # 참조 이미지의 캐릭터에 집중한 프롬프트
    prompt = "A majestic golden tiger with golden-orange fur, smiling gently, showing teeth, wet nose, looking at camera, Disney 3D animation, Pixar quality"

    output_path = "outputs/consistency_v2/test_01.png"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Test v2 - 참조 이미지와 유사한 tiger 생성")
    print("=" * 60)
    print(f"Prompt: {prompt}")

    result = await client.generate_with_reference_and_save(
        prompt=prompt,
        reference_image_path=ref_image,
        output_path=output_path,
        aspect_ratio="1:1",  # 정방향 1:1
    )

    if result.success:
        print(f"[OK] 저장됨: {output_path}")
    else:
        print(f"[FAIL] {result.error_message}")


if __name__ == "__main__":
    asyncio.run(test())