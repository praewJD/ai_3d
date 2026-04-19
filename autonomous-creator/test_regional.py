# -*- coding: utf-8 -*-
"""
Regional Cross-Attention + ControlNet 다중 인물 생성 테스트

테스트 대상:
- scene_2: 2인물 (서준 + 하은, 가을 공원)
- scene_3: 3인물 (서준 + 하은 + 민호, 야외 카페)

사용법:
    cd D:\AI-Video\autonomous-creator
    python test_regional.py
"""
import asyncio
import json
import sys
import time
import logging
from pathlib import Path
from PIL import Image

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
    print("Regional Cross-Attention 다중 인물 생성 테스트")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 1. 테스트 데이터 로드
    # ------------------------------------------------------------------
    script_path = project_root / "output" / "e2e_test" / "script.json"
    if not script_path.exists():
        print(f"ERROR: 테스트 데이터 없음: {script_path}")
        return

    with open(script_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    from infrastructure.story.story_spec import (
        SceneSpec, CharacterSpec,
    )

    characters = [CharacterSpec.from_dict(c) for c in data["characters"]]
    print(f"\n스크립트: {data['title']}")
    print(f"캐릭터: {[c.name for c in characters]}")

    # 다중 인물 씬만 필터
    multi_char_scenes = []
    for s in data["scenes"]:
        if len(s["characters"]) >= 2:
            multi_char_scenes.append(s)

    print(f"다중 인물 씬: {len(multi_char_scenes)}개")
    for s in multi_char_scenes:
        char_names = []
        for cid in s["characters"]:
            for c in characters:
                if c.id == cid:
                    char_names.append(c.name)
        print(f"  - {s['id']}: {len(s['characters'])}명 ({', '.join(char_names)})")
    print()

    # ------------------------------------------------------------------
    # 2. SDXLGenerator 로드
    # ------------------------------------------------------------------
    print("-" * 70)
    print("SDXL 모델 로드 중...")
    print("-" * 70)

    from infrastructure.image.sdxl_generator import SDXLGenerator
    from infrastructure.image.multi_char_regional import MultiCharRegionalGenerator

    generator = SDXLGenerator()
    await generator.load_model()
    print("SDXL 베이스 모델 로드 완료")

    # LoRA 로드
    lora_path = "D:/AI-Video/autonomous-creator/data/lora/3dModel_sdxl_v2.safetensors"
    if Path(lora_path).exists():
        loaded = generator.load_lora(lora_path, scale=0.5)
        print(f"LoRA: {'loaded' if loaded else 'failed'} (scale=0.5)")

    ip_status = "loaded" if generator.is_ip_adapter_loaded() else "not loaded"
    print(f"IP-Adapter: {ip_status}")

    # ------------------------------------------------------------------
    # 3. RegionalGenerator 초기화
    # ------------------------------------------------------------------
    regional_gen = MultiCharRegionalGenerator(generator)

    # ------------------------------------------------------------------
    # 4. 마스크 디버그 시각화
    # ------------------------------------------------------------------
    print("\n영역 마스크 시각화...")
    debug_dir = "output/regional_test/debug_masks"
    regional_gen.debug_region_masks(num_chars=2, output_dir=debug_dir)
    regional_gen.debug_region_masks(num_chars=3, output_dir=debug_dir)
    print(f"마스크 저장: {debug_dir}")

    # ------------------------------------------------------------------
    # 5. 다중 인물 씬 생성
    # ------------------------------------------------------------------
    output_dir = project_root / "output" / "regional_test"
    output_dir.mkdir(parents=True, exist_ok=True)

    # scene_2, scene_3만 테스트
    target_scenes = ["scene_2", "scene_3"]
    test_scenes = [s for s in multi_char_scenes if s["id"] in target_scenes]

    results = []
    seed = 12345

    for scene_data in test_scenes:
        scene = SceneSpec.from_dict(scene_data)
        num_chars = len(scene.characters)

        char_names = []
        for cid in scene.characters:
            for c in characters:
                if c.id == cid:
                    char_names.append(c.name)

        print(f"\n{'=' * 70}")
        print(f"씬: {scene.id} ({num_chars}인물: {', '.join(char_names)})")
        print(f"Action: {scene.action[:80]}...")
        print(f"Camera: {scene.camera} | Mood: {scene.mood}")
        print(f"Location: {scene.location}")
        print(f"{'=' * 70}")

        output_path = str(output_dir / f"{scene.id}_regional_{num_chars}chars.png")

        try:
            start = time.time()
            image_path = await regional_gen.generate_multi_char(
                scene=scene,
                characters=characters,
                output_path=output_path,
                seed=seed,
                steps=25,
                cfg_scale=7.5,
                width=576,
                height=1024,
                controlnet_scale=0.4,
                use_controlnet=True,
            )
            elapsed = time.time() - start

            # 결과 확인
            result_file = Path(image_path)
            if result_file.exists():
                size_kb = result_file.stat().st_size / 1024
                img = Image.open(image_path)
                arr = __import__("numpy").array(img)
                print(f"\nSUCCESS: {image_path}")
                print(f"  크기: {size_kb:.0f} KB, 해상도: {img.size}")
                print(f"  픽셀: mean={arr.mean():.1f}, std={arr.std():.1f}")
                print(f"  소요시간: {elapsed:.1f}초")
                results.append({
                    "scene_id": scene.id,
                    "num_chars": num_chars,
                    "output_path": image_path,
                    "time_seconds": round(elapsed, 1),
                    "size_kb": round(size_kb, 0),
                    "pixel_mean": round(float(arr.mean()), 1),
                    "pixel_std": round(float(arr.std()), 1),
                    "status": "success",
                })
            else:
                print(f"\nFAIL: 파일 없음")
                results.append({
                    "scene_id": scene.id, "num_chars": num_chars,
                    "status": "fail", "error": "파일 없음",
                })

        except Exception as e:
            print(f"\nFAIL: {e}")
            logger.error(f"씬 {scene.id} 생성 실패", exc_info=True)
            results.append({
                "scene_id": scene.id, "num_chars": num_chars,
                "status": "fail", "error": str(e),
            })

    # ------------------------------------------------------------------
    # 6. 결과 리포트
    # ------------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print("Regional Cross-Attention 결과 리포트")
    print(f"{'=' * 70}")

    for r in results:
        status = "OK" if r["status"] == "success" else "FAIL"
        chars_str = f"{r['num_chars']}인물"
        time_str = f"{r.get('time_seconds', 'N/A')}s"
        print(f"  [{status}] {r['scene_id']} ({chars_str}): {time_str}")
        if r["status"] == "success":
            print(f"         -> {r['output_path']}")
            print(f"            {r['size_kb']:.0f}KB, mean={r['pixel_mean']}, std={r['pixel_std']}")
        elif "error" in r:
            print(f"         -> Error: {r['error']}")

    # 결과 JSON 저장
    report_path = output_dir / "regional_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "method": "Regional Cross-Attention + ControlNet",
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n리포트 저장: {report_path}")

    # 모델 언로드
    print("\n모델 언로드 중...")
    await generator.unload_model()
    print("완료!")


if __name__ == "__main__":
    asyncio.run(main())
