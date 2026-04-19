# -*- coding: utf-8 -*-
"""
Method 2 (개별 생성 + 합성) 테스트 스크립트

기존 대본의 다중 인물 씬을 개별 생성 + 합성 방식으로 처리하는지 확인합니다.
- scene_2: 2인물 (서준 + 하은)
- scene_3: 3인물 (서준 + 하은 + 민호)
"""
import asyncio
import json
import sys
import time
from pathlib import Path

logging_setup = __import__('logging')
logging_setup.basicConfig(
    level=logging_setup.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging_setup.StreamHandler(sys.stdout)],
)

import logging
logger = logging.getLogger(__name__)


def load_story_spec():
    """기존 대본 로드 -> StorySpec 변환"""
    from infrastructure.story.story_spec import (
        StorySpec, SceneSpec, CharacterSpec, ArcSpec,
        TargetFormat, ScenePurpose,
    )

    script_path = Path("output/e2e_test/script.json")
    if not script_path.exists():
        print(f"ERROR: 대본 파일 없음: {script_path}")
        sys.exit(1)

    with open(script_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 캐릭터 변환
    characters = []
    for c in data.get("characters", []):
        characters.append(CharacterSpec(
            id=c.get("id", f"char_{len(characters)+1}"),
            name=c.get("name", "Unknown"),
            appearance=c.get("appearance", ""),
            traits=c.get("traits", []),
        ))

    # 아크 변환
    arc_data = data.get("arc", {})
    arc = ArcSpec(
        hook=arc_data.get("hook", ""),
        build=arc_data.get("build", ""),
        climax=arc_data.get("climax", ""),
        resolution=arc_data.get("resolution", ""),
    )

    # 씬 변환
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

    return spec


async def main():
    print("=" * 60)
    print("Method 2 (개별 생성 + 합성) 테스트")
    print("=" * 60)
    print()

    # 1. 대본 로드
    spec = load_story_spec()
    print(f"대본 로드: {spec.title} ({len(spec.scenes)} 씬, {len(spec.characters)} 캐릭터)")
    print()

    # 캐릭터 정보 출력
    for c in spec.characters:
        print(f"  캐릭터: {c.id} ({c.name}) - {c.appearance}")
    print()

    # 테스트 대상 씬 확인
    target_scenes = ["scene_2", "scene_3"]
    test_scenes = [s for s in spec.scenes if s.id in target_scenes]

    print("테스트 대상 씬:")
    for s in test_scenes:
        chars = [c for c in spec.characters if c.id in s.characters]
        char_names = [f"{c.name}({c.id})" for c in chars]
        print(f"  - {s.id}: {len(s.characters)}명 ({', '.join(char_names)})")
        print(f"    action: {s.action[:80]}...")
        print(f"    location: {s.location}")
    print()

    # 2. SDXLGenerator + LoRA 로드
    from infrastructure.image.sdxl_generator import SDXLGenerator
    from infrastructure.image.multi_char_composite import MultiCharCompositeGenerator

    output_dir = Path("output/method2_composite")
    output_dir.mkdir(parents=True, exist_ok=True)
    debug_dir = output_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    # SDXLGenerator 생성 (test_chunking_only.py와 동일한 패턴)
    generator = SDXLGenerator()

    print("SDXL 모델 로드 중...")
    t0 = time.time()
    await generator.load_model()
    print(f"SDXL 모델 로드 완료 ({time.time()-t0:.1f}초)")
    print()

    # LoRA 로드
    lora_path = "D:/AI-Video/autonomous-creator/data/lora/3dModel_sdxl_v2.safetensors"
    if Path(lora_path).exists():
        print(f"LoRA 로드 중: {lora_path}")
        lora_loaded = generator.load_lora(lora_path, scale=0.5)
        if lora_loaded:
            print("LoRA 로드 완료 (scale=0.5)")
        else:
            print("LoRA 로드 실패, LoRA 없이 진행")
    else:
        print(f"LoRA 파일 없음: {lora_path}, LoRA 없이 진행")
    print()

    # IP-Adapter 상태 확인
    ip_status = generator.is_ip_adapter_loaded()
    print(f"IP-Adapter 상태: {'loaded' if ip_status else 'not loaded'}")
    print()

    # 3. MultiCharCompositeGenerator 생성
    composite_gen = MultiCharCompositeGenerator(
        generator=generator,
        debug_dir=str(debug_dir),
    )

    # 4. 씬별 테스트
    results = []
    for scene in test_scenes:
        chars_in_scene = [c for c in spec.characters if c.id in scene.characters]
        print("-" * 50)
        print(
            f"씬 {scene.id}: {len(chars_in_scene)}인물 "
            f"({', '.join(c.name for c in chars_in_scene)})"
        )
        print(f"  location: {scene.location}")
        print(f"  mood: {scene.mood}")
        print(f"  action: {scene.action[:100]}...")
        print()

        output_path = str(output_dir / f"{scene.id}_composite.png")

        try:
            t_start = time.time()
            result_path = await composite_gen.generate_multi_char(
                scene=scene,
                characters=spec.characters,
                output_path=output_path,
                width=576,
                height=1024,
                seed=12345,
                steps=20,
                cfg_scale=7.5,
            )
            elapsed = time.time() - t_start

            # 결과 확인
            result_file = Path(result_path)
            if result_file.exists():
                size_kb = result_file.stat().st_size / 1024
                img = __import__("PIL").Image.open(result_path)
                print(f"  결과: SUCCESS")
                print(f"  파일: {result_path}")
                print(f"  크기: {size_kb:.0f} KB, 해상도: {img.size}")
                print(f"  소요시간: {elapsed:.1f}초")
                results.append({
                    "scene": scene.id,
                    "success": True,
                    "path": result_path,
                    "size_kb": size_kb,
                    "resolution": img.size,
                    "time": elapsed,
                    "num_chars": len(chars_in_scene),
                })
            else:
                print(f"  결과: FAIL (파일 없음)")
                results.append({
                    "scene": scene.id,
                    "success": False,
                    "path": result_path,
                    "error": "파일 없음",
                    "time": elapsed,
                    "num_chars": len(chars_in_scene),
                })

        except Exception as e:
            elapsed = time.time() - t_start
            print(f"  결과: FAIL ({e})")
            logger.error(f"씬 {scene.id} 생성 실패", exc_info=True)
            results.append({
                "scene": scene.id,
                "success": False,
                "error": str(e),
                "time": elapsed,
                "num_chars": len(chars_in_scene),
            })

        print()

    # 5. 결과 요약
    print("=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)

    success_count = sum(1 for r in results if r["success"])
    total_count = len(results)
    total_time = sum(r["time"] for r in results)

    print(f"성공: {success_count}/{total_count}")
    print(f"총 소요시간: {total_time:.1f}초")
    print()

    for r in results:
        status = "SUCCESS" if r["success"] else "FAIL"
        print(
            f"  [{status}] {r['scene']} "
            f"({r['num_chars']}인물, {r['time']:.1f}초)"
        )
        if r["success"]:
            print(f"         -> {r['path']} ({r['size_kb']:.0f} KB)")
        elif "error" in r:
            print(f"         -> Error: {r['error']}")

    # 중간 결과물 확인
    print()
    print("디버그 중간 결과물:")
    for debug_file in sorted(debug_dir.rglob("*")):
        if debug_file.is_file():
            size_kb = debug_file.stat().st_size / 1024
            print(f"  {debug_file.relative_to(output_dir)} ({size_kb:.0f} KB)")

    # 결과 JSON 저장
    summary_path = output_dir / "test_results.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "method": "method2_composite",
            "total_time": total_time,
            "success": success_count,
            "total": total_count,
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n결과 JSON 저장: {summary_path}")

    # 정리
    await generator.unload_model()
    print("\n테스트 완료!")


if __name__ == "__main__":
    asyncio.run(main())
