# -*- coding: utf-8 -*-
"""
StoryToImagePipeline E2E 테스트
- 1인물 씬: SDXLGenerator 직접 생성
- 2/3인물 씬: MultiCharRegionalGenerator (Regional Cross-Attention)
"""
import asyncio
import json
import sys
import time
import logging
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main():
    print("=" * 70)
    print("StoryToImagePipeline E2E 테스트")
    print("=" * 70)

    # 1. 스크립트 로드
    script_path = project_root / "output" / "e2e_test" / "script.json"
    if not script_path.exists():
        print(f"ERROR: 테스트 데이터 없음: {script_path}")
        return

    with open(script_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    from infrastructure.story.story_spec import StorySpec

    story_spec = StorySpec.from_dict(data)
    print(f"\n스토리: {story_spec.title}")
    print(f"캐릭터: {[c.name for c in story_spec.characters]}")
    print(f"총 씬: {len(story_spec.scenes)}")

    # 씬별 인물 수 요약
    for s in story_spec.scenes:
        char_names = []
        for cid in s.characters:
            for c in story_spec.characters:
                if c.id == cid:
                    char_names.append(c.name)
        mode = "Regional" if len(s.characters) >= 2 else "Standard"
        print(f"  {s.id}: {len(s.characters)}인물 ({', '.join(char_names)}) → {mode}")

    # 2. 파이프라인 생성 + 실행
    from infrastructure.pipeline.story_to_image_pipeline import (
        StoryToImagePipeline,
        PipelineConfig,
    )

    config = PipelineConfig(
        output_dir="output/pipeline_e2e_test",
        seed=12345,
        steps=25,
        cfg_scale=7.5,
        width=576,
        height=1024,
    )

    pipeline = StoryToImagePipeline(config)

    print(f"\n{'=' * 70}")
    print("파이프라인 실행 시작...")
    print(f"{'=' * 70}")

    start = time.time()
    result = await pipeline.run(story_spec)
    elapsed = time.time() - start

    # 3. 결과 리포트
    print(f"\n{'=' * 70}")
    print("결과 리포트")
    print(f"{'=' * 70}")
    print(f"성공: {result.success}")
    print(f"생성 이미지: {len(result.image_paths)}/{result.scene_count}")
    print(f"실패 씬: {result.failed_scenes}")
    print(f"총 소요시간: {elapsed:.1f}s")

    for path in result.image_paths:
        p = Path(path)
        if p.exists():
            size_kb = p.stat().st_size / 1024
            print(f"  OK: {p.name} ({size_kb:.0f}KB)")

    # 4. 언로드
    await pipeline.unload()
    print("\n완료!")


if __name__ == "__main__":
    asyncio.run(main())
