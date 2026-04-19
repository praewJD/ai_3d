# -*- coding: utf-8 -*-
"""
프롬프트 청킹 테스트: 기존 대본으로 이미지 생성만
API 호출 없이 프롬프트 청킹이 정상 동작하는지 확인
"""
import asyncio
import json
import sys
import time
from pathlib import Path

logging_setup = __import__('logging')
logging_setup.basicConfig(level=logging_setup.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", handlers=[logging_setup.StreamHandler(sys.stdout)])


async def main():
    # 기존 대본 로드
    script_path = Path("output/e2e_test/script.json")
    with open(script_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # StorySpec으로 변환
    from infrastructure.story.story_spec import StorySpec, SceneSpec, CharacterSpec, ArcSpec, TargetFormat, ScenePurpose

    characters = []
    for c in data.get("characters", []):
        characters.append(CharacterSpec(
            id=c.get("id", f"char_{len(characters)+1}"),
            name=c.get("name", "Unknown"),
            appearance=c.get("appearance", ""),
            traits=c.get("traits", []),
        ))

    arc_data = data.get("arc", {})
    arc = ArcSpec(
        hook=arc_data.get("hook", ""),
        build=arc_data.get("build", ""),
        climax=arc_data.get("climax", ""),
        resolution=arc_data.get("resolution", ""),
    )

    scenes = []
    for s in data.get("scenes", []):
        purpose_str = s.get("purpose", "build")
        try:
            purpose = ScenePurpose(purpose_str)
        except ValueError:
            purpose = ScenePurpose.BUILD
        scenes.append(SceneSpec(
            id=s.get("id", f"scene_{len(scenes)+1}"),
            purpose=purpose,
            camera=s.get("camera", "medium_shot"),
            mood=s.get("mood", "neutral"),
            action=s.get("action", ""),
            characters=s.get("characters", []),
            location=s.get("location", ""),
            dialogue=s.get("dialogue", ""),
            narration=s.get("narration", ""),
            duration=float(s.get("duration", 3.0)),
            emotion=s.get("emotion", "neutral"),
        ))

    total_duration = sum(s.duration for s in scenes)
    spec = StorySpec(
        title=data.get("title", "Test"),
        genre=data.get("genre", "drama"),
        target=TargetFormat.SHORTS,
        duration=total_duration,
        characters=characters,
        arc=arc,
        scenes=scenes,
        emotion_curve=data.get("emotion_curve", []),
        metadata=data.get("metadata", {}),
    )

    print(f"대본 로드: {spec.title} ({len(spec.scenes)} 씬)")
    print()

    # 이미지 생성 (처음 3개 씬만)
    from infrastructure.pipeline.story_to_image_pipeline import StoryToImagePipeline, PipelineConfig

    config = PipelineConfig(
        output_dir="output/chunking_test",
        seed=12345,
        steps=20,
        cfg_scale=7.5,
    )

    pipeline = StoryToImagePipeline(config)

    # 테스트용으로 씬 3개만
    test_spec = StorySpec(
        title=spec.title,
        genre=spec.genre,
        target=spec.target,
        duration=sum(s.duration for s in spec.scenes[:3]),
        characters=spec.characters,
        arc=spec.arc,
        scenes=spec.scenes[:3],
        emotion_curve=spec.emotion_curve[:3] if spec.emotion_curve else [],
        metadata=spec.metadata,
    )

    print("SDXL 모델 로드 중...")
    t0 = time.time()
    await pipeline.load()
    print(f"모델 로드 완료 ({time.time()-t0:.1f}초)")
    print()

    print(f"이미지 생성 시작 ({len(test_spec.scenes)}개 씬, 프롬프트 청킹 적용)")
    t1 = time.time()
    result = await pipeline.run(test_spec)
    gen_time = time.time() - t1

    print()
    print("=" * 50)
    print(f"이미지 생성: {'SUCCESS' if result.success else 'FAIL'}")
    print(f"생성된 이미지: {len(result.image_paths)}/{result.scene_count}")
    print(f"소요 시간: {gen_time:.1f}초")
    print()
    for p in result.image_paths:
        size = Path(p).stat().st_size / 1024
        print(f"  - {p} ({size:.0f} KB)")

    # 매니페스트에서 청킹 적용 여부 확인
    for mf in sorted(Path("output/chunking_test").glob("scene_*_manifest.json")):
        d = json.load(open(mf, "r", encoding="utf-8"))
        prompt_len = len(d.get("prompt_used", ""))
        print(f"\n{mf.name}:")
        print(f"  prompt 길이: {prompt_len}자")
        print(f"  prompt: {d.get('prompt_used', '')[:200]}...")

    await pipeline.unload()
    print("\n테스트 완료!")


if __name__ == "__main__":
    asyncio.run(main())
