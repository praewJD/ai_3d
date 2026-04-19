# -*- coding: utf-8 -*-
"""
E2E 테스트: 실제 API 호출 → 대본 생성 → 이미지 생성

Step 1: ShortDramaCompiler + StoryLLMProvider → GLM API 호출 → 대본 생성
Step 2: StoryToImagePipeline → SDXL 이미지 생성
"""
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("e2e_test")


async def main():
    print("=" * 60)
    print("  E2E 테스트: API 대본 생성 → SDXL 이미지 생성")
    print("=" * 60)
    print()

    # ─────────────────────────────────────────────
    # Step 1: 대본 생성 (GLM API 호출)
    # ─────────────────────────────────────────────
    print("[Step 1] 대본 생성 - GLM API 호출")
    print("-" * 40)

    from infrastructure.ai import StoryLLMProvider
    from infrastructure.story.short_drama_compiler import ShortDramaCompiler

    provider = StoryLLMProvider()
    compiler = ShortDramaCompiler(llm_provider=provider)

    # 카테고리 목록 출력
    categories = compiler.list_categories()
    print(f"사용 가능한 카테고리: {categories}")
    print()

    # "연애 배신" 카테고리로 대본 생성
    selected_category = "연애 배신"
    print(f"선택된 카테고리: {selected_category}")
    print("GLM API 호출 중...")

    t0 = time.time()
    result = await compiler.compile(
        category=selected_category,
        tone="현실적",
        hint="남자가 여자친구의 핸드폰에서 충격적인 메시지를 발견하는 이야기",
    )
    api_time = time.time() - t0

    if not result.success:
        print(f"대본 생성 실패: {result.error}")
        return

    spec = result.story_spec
    print(f"\n대본 생성 완료! ({api_time:.1f}초)")
    print(f"  제목: {spec.title}")
    print(f"  장르: {spec.genre}")
    print(f"  총 길이: {spec.duration:.1f}초")
    print(f"  씬 수: {len(spec.scenes)}")
    print(f"  캐릭터 수: {len(spec.characters)}")
    print(f"  Hook Score: {result.hook_score:.1f}")
    print(f"  재시도: {result.retry_count}회")

    # 캐릭터 정보
    print(f"\n  [캐릭터]")
    for c in spec.characters:
        print(f"    - {c.id}: {c.name} ({', '.join(c.traits)})")
        print(f"      외형: {c.appearance[:80]}...")

    # 씬 정보
    print(f"\n  [씬 구성]")
    for i, s in enumerate(spec.scenes):
        print(f"    {i+1}. [{s.purpose.value}] {s.action[:60]}... ({s.duration}초)")

    # 대본 JSON 저장
    output_dir = Path("output/e2e_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    script_path = output_dir / "script.json"
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(spec.to_dict() if hasattr(spec, 'to_dict') else str(spec), f, ensure_ascii=False, indent=2)
    print(f"\n  대본 저장: {script_path}")

    # ─────────────────────────────────────────────
    # Step 2: 이미지 생성 (SDXL)
    # ─────────────────────────────────────────────
    print()
    print("[Step 2] 이미지 생성 - SDXL (CPU offload)")
    print("-" * 40)

    from infrastructure.pipeline.story_to_image_pipeline import (
        StoryToImagePipeline,
        PipelineConfig,
    )

    config = PipelineConfig(
        output_dir=str(output_dir / "images"),
        seed=12345,
        steps=20,       # 테스트용으로 줄임
        cfg_scale=7.5,
    )

    pipeline = StoryToImagePipeline(config)

    print("SDXL 모델 로드 중...")
    t1 = time.time()
    await pipeline.load()
    load_time = time.time() - t1
    print(f"모델 로드 완료 ({load_time:.1f}초)")

    print(f"\n이미지 생성 시작 ({len(spec.scenes)}개 씬)...")
    t2 = time.time()
    img_result = await pipeline.run(spec)
    gen_time = time.time() - t2

    # 결과 출력
    print()
    print("=" * 60)
    print("  E2E 테스트 결과")
    print("=" * 60)
    print(f"  대본 생성: {'SUCCESS' if result.success else 'FAIL'} ({api_time:.1f}초)")
    print(f"  모델 로드: {'SUCCESS' if pipeline._is_loaded else 'FAIL'} ({load_time:.1f}초)")
    print(f"  이미지 생성: {'SUCCESS' if img_result.success else 'FAIL'} ({gen_time:.1f}초)")
    print(f"  생성된 이미지: {len(img_result.image_paths)}/{img_result.scene_count}")
    if img_result.failed_scenes:
        print(f"  실패한 씬: {img_result.failed_scenes}")
    print()
    print(f"  총 소요 시간: {time.time() - t0:.1f}초")
    print()

    # 생성된 이미지 목록
    if img_result.image_paths:
        print("  생성된 이미지:")
        for p in img_result.image_paths:
            size = Path(p).stat().st_size / 1024
            print(f"    - {p} ({size:.0f} KB)")

    # 정리
    await pipeline.unload()
    await provider.close()
    print("\n테스트 완료!")


if __name__ == "__main__":
    asyncio.run(main())
