# -*- coding: utf-8 -*-
"""
Method 4: Mask-Based Prompt Conditioning 테스트 스크립트

커스텀 디노이징 루프에서 영역별 노이즈 예측을 혼합하여
한 번의 패스로 다중 인물 씬을 생성합니다.

테스트 대상:
- scene_2: 2인물 (서준 + 하은, 가을 공원)
- scene_3: 3인물 (서준 + 하은 + 민호, 야외 카페)

사용법:
    cd D:\AI-Video\autonomous-creator
    python test_method4_masked.py
"""
import asyncio
import json
import sys
import time
import logging
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main():
    """Method 4 테스트 실행"""
    print("=" * 70)
    print("Method 4: Mask-Based Prompt Conditioning 테스트")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 1. 테스트 데이터 로드
    # ------------------------------------------------------------------
    script_path = project_root / "output" / "e2e_test" / "script.json"
    if not script_path.exists():
        print(f"ERROR: 테스트 데이터 없음: {script_path}")
        print("먼저 story compiler를 실행하여 script.json을 생성하세요.")
        return

    with open(script_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    print(f"\n스크립트: {script_data['title']}")
    print(f"캐릭터: {[c['name'] for c in script_data['characters']]}")
    print(f"씬 수: {len(script_data['scenes'])}")

    # ------------------------------------------------------------------
    # 2. StorySpec 객체로 변환
    # ------------------------------------------------------------------
    from infrastructure.story.story_spec import (
        StorySpec, SceneSpec, CharacterSpec, ScenePurpose,
    )

    characters = [CharacterSpec.from_dict(c) for c in script_data["characters"]]
    scenes_raw = script_data["scenes"]

    # 다중 인물 씬만 필터
    multi_char_scenes = []
    for s in scenes_raw:
        if len(s["characters"]) >= 2:
            multi_char_scenes.append(s)

    if not multi_char_scenes:
        print("\nERROR: 다중 인물 씬이 없습니다.")
        return

    print(f"\n다중 인물 씬 ({len(multi_char_scenes)}개):")
    for s in multi_char_scenes:
        char_names = []
        for cid in s["characters"]:
            for c in characters:
                if c.id == cid:
                    char_names.append(c.name)
        print(f"  - {s['id']}: {s['purpose']} | {', '.join(char_names)} | {s['action'][:60]}...")

    # ------------------------------------------------------------------
    # 3. SDXLGenerator 로드 (LoRA + IP-Adapter 포함)
    # ------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("SDXL 모델 로드 중...")
    print("-" * 70)

    from infrastructure.image.sdxl_generator import SDXLGenerator

    generator = SDXLGenerator()
    await generator.load_model()
    print("SDXL 베이스 모델 로드 완료")

    # LoRA 로드
    lora_path = "D:/AI-Video/autonomous-creator/data/lora/3dModel_sdxl_v2.safetensors"
    if Path(lora_path).exists():
        lora_loaded = generator.load_lora(lora_path, scale=0.5)
        if lora_loaded:
            print(f"LoRA 로드 완료: {Path(lora_path).name} (scale=0.5)")
        else:
            print(f"WARNING: LoRA 로드 실패, 스타일 없이 진행")
    else:
        print(f"WARNING: LoRA 파일 없음: {lora_path}")

    ip_status = "로드됨" if generator.is_ip_adapter_loaded() else "미로드"
    print(f"IP-Adapter 상태: {ip_status}")

    # ------------------------------------------------------------------
    # 4. MultiCharMaskedGenerator 초기화
    # ------------------------------------------------------------------
    from infrastructure.image.multi_char_masked import MultiCharMaskedGenerator

    masked_gen = MultiCharMaskedGenerator(generator)

    # ------------------------------------------------------------------
    # 5. 디버그: 영역 마스크 시각화
    # ------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("영역 마스크 디버그 시각화...")
    print("-" * 70)

    debug_dir = "output/method4_masked/debug_masks"
    try:
        # 2인물 마스크
        mask_paths_2 = masked_gen.debug_region_masks(
            num_chars=2, width=576, height=1024,
            output_dir=debug_dir, feather=0.15,
        )
        print(f"2인물 마스크 시각화: {mask_paths_2}")

        # 3인물 마스크
        mask_paths_3 = masked_gen.debug_region_masks(
            num_chars=3, width=576, height=1024,
            output_dir=debug_dir, feather=0.15,
        )
        print(f"3인물 마스크 시각화: {mask_paths_3}")
    except Exception as e:
        print(f"WARNING: 마스크 시각화 실패: {e}")

    # ------------------------------------------------------------------
    # 6. 다중 인물 씬 생성
    # ------------------------------------------------------------------
    output_dir = project_root / "output" / "method4_masked"
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    seed = 12345

    for scene_data in multi_char_scenes:
        scene = SceneSpec.from_dict(scene_data)
        num_chars = len(scene.characters)

        print("\n" + "=" * 70)
        char_names = []
        for cid in scene.characters:
            for c in characters:
                if c.id == cid:
                    char_names.append(c.name)
        print(f"씬: {scene.id} ({num_chars}인물: {', '.join(char_names)})")
        print(f"Action: {scene.action[:80]}...")
        print(f"Camera: {scene.camera} | Mood: {scene.mood}")
        print("=" * 70)

        output_path = str(output_dir / f"{scene.id}_method4_{num_chars}chars.png")

        try:
            start = time.time()
            image_path = await masked_gen.generate_multi_char(
                scene=scene,
                characters=characters,
                output_path=output_path,
                seed=seed,
                steps=25,
                cfg_scale=7.5,
                width=576,
                height=1024,
                feather_strength=0.15,
            )
            elapsed = time.time() - start

            print(f"\nSUCCESS: {image_path} ({elapsed:.1f}s)")
            results.append({
                "scene_id": scene.id,
                "num_chars": num_chars,
                "output_path": image_path,
                "time_seconds": round(elapsed, 1),
                "status": "success",
            })

        except Exception as e:
            print(f"\nFAILED: {e}")
            logger.error(f"씬 {scene.id} 생성 실패", exc_info=True)
            results.append({
                "scene_id": scene.id,
                "num_chars": num_chars,
                "output_path": None,
                "error": str(e),
                "status": "failed",
            })

    # ------------------------------------------------------------------
    # 7. 결과 리포트
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("Method 4 결과 리포트")
    print("=" * 70)

    success_count = sum(1 for r in results if r["status"] == "success")
    total_count = len(results)

    for r in results:
        status = "OK" if r["status"] == "success" else "FAIL"
        chars_str = f"{r['num_chars']}인물"
        time_str = f"{r['time_seconds']:.1f}s" if "time_seconds" in r else "N/A"
        path_str = r["output_path"] or r.get("error", "unknown error")
        print(f"  [{status}] {r['scene_id']} ({chars_str}): {time_str} - {path_str}")

    print(f"\n총: {success_count}/{total_count} 성공")

    # 결과 JSON 저장
    report_path = output_dir / "method4_report.json"
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump({
                "method": "Method 4: Mask-Based Prompt Conditioning",
                "total_scenes": total_count,
                "success_count": success_count,
                "results": results,
            }, f, ensure_ascii=False, indent=2)
        print(f"리포트 저장: {report_path}")
    except Exception as e:
        print(f"WARNING: 리포트 저장 실패: {e}")

    # ------------------------------------------------------------------
    # 8. 모델 언로드
    # ------------------------------------------------------------------
    print("\n모델 언로드 중...")
    await generator.unload_model()
    print("완료!")


if __name__ == "__main__":
    asyncio.run(main())
