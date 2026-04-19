# -*- coding: utf-8 -*-
"""
MiniMax Character Consistency Retry Test
동일 캐릭터 나올 때까지 계속 생성
"""
import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from infrastructure.api.providers.image.minimax_image import MiniMaxImageClient


async def test_consistency():
    """동일 캐릭터 나올 때까지 반복 생성"""

    # 기존 참조 이미지
    ref_image = "outputs/character_consistency_test/char_1_Shan,_the_Golden_Tiger_ref.png"

    if not Path(ref_image).exists():
        print(f"[ERROR] 참조 이미지 없음: {ref_image}")
        return

    client = MiniMaxImageClient()

    # 동일한 프롬프트 + 참조 이미지로 여러 번 생성
    prompt = "A majestic golden tiger with luxurious golden-orange fur, fierce golden eyes, muscular body, Disney 3D animation style, Pixar quality, vibrant colors, soft cel shading, high detail, masterpiece"

    output_dir = Path("outputs/consistency_retry_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Character Consistency Retry Test")
    print("동일 캐릭터가 나올 때까지 생성 반복")
    print("=" * 60)
    print(f"참조 이미지: {ref_image}")
    print(f"프롬프트: {prompt[:60]}...")
    print("=" * 60)

    for i in range(1, 11):  # 10번 시도
        print(f"\n[*] 시도 {i}/10...")

        output_path = output_dir / f"test_{i:02d}.png"

        result = await client.generate_with_reference_and_save(
            prompt=prompt,
            reference_image_path=ref_image,
            output_path=str(output_path),
            aspect_ratio="16:9",
        )

        if result.success:
            print(f"    [OK] 저장됨: test_{i:02d}.png")
            print(f"    (이 이미지를 확인해서 호랑이가 일관성 있는지 확인하세요)")
        else:
            print(f"    [FAIL] {result.error_message}")

        # 잠시 대기 (API 제한 고려)
        await asyncio.sleep(2)

    print("\n" + "=" * 60)
    print(f"완료! 결과: {output_dir}")
    print("모든 이미지 비교해서 동일한 캐릭터가 있는지 확인!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_consistency())