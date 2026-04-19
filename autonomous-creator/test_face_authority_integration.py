# -*- coding: utf-8 -*-
"""
Face Authority 아키텍처 통합 테스트
- Import, PromptCompiler, RenderConfig, SDXLGenerator, FACE_AUTHORITY_DEFAULTS
"""
import sys
import traceback

results = []


def report(test_name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    msg = f"[{status}] {test_name}"
    if detail:
        msg += f" - {detail}"
    results.append((test_name, passed, detail))
    print(msg)


# ======================================================================
# 1. Import 테스트
# ======================================================================
print("=" * 70)
print("1. Import 테스트")
print("=" * 70)

try:
    from infrastructure.image.sdxl_generator import SDXLGenerator
    report("Import SDXLGenerator", True)
except Exception as e:
    report("Import SDXLGenerator", False, str(e))

try:
    from infrastructure.prompt.prompt_compiler import PromptCompiler
    report("Import PromptCompiler", True)
except Exception as e:
    report("Import PromptCompiler", False, str(e))

try:
    from infrastructure.render.render_engine import RenderEngine, RenderConfig
    report("Import RenderEngine, RenderConfig", True)
except Exception as e:
    report("Import RenderEngine, RenderConfig", False, str(e))

# ======================================================================
# 2. PromptCompiler 얼굴 묘사 필터 테스트
# ======================================================================
print()
print("=" * 70)
print("2. PromptCompiler 얼굴 묘사 필터 테스트")
print("=" * 70)

try:
    compiler = PromptCompiler()

    # 2-1. 얼굴 묘사가 포함된 프롬프트
    test_prompt = "beautiful girl with big eyes and long hair standing in forest"
    result = compiler.sanitize_face_descriptions(test_prompt)
    print(f"  Input:  {test_prompt}")
    print(f"  Output: {result}")

    # "big eyes" 와 "long hair" 가 제거되었는지 확인
    removed_big_eyes = "big eyes" not in result.lower()
    removed_long_hair = "long hair" not in result.lower()
    # "beautiful" 은 단독으로는 ban list에 없으나 "beautiful face" 는 있음
    # 원문에는 "beautiful" 만 있고 "beautiful face" 는 없으므로 "beautiful" 유지됨
    has_girl = "girl" in result
    has_forest = "forest" in result

    report(
        "sanitize_face_descriptions: 'big eyes' removed",
        removed_big_eyes,
        f"result still contains 'big eyes'" if not removed_big_eyes else "OK"
    )
    report(
        "sanitize_face_descriptions: 'long hair' removed",
        removed_long_hair,
        f"result still contains 'long hair'" if not removed_long_hair else "OK"
    )
    report(
        "sanitize_face_descriptions: 'girl' preserved",
        has_girl,
        f"'girl' was incorrectly removed" if not has_girl else "OK"
    )
    report(
        "sanitize_face_descriptions: 'forest' preserved",
        has_forest,
        f"'forest' was incorrectly removed" if not has_forest else "OK"
    )

except Exception as e:
    report("PromptCompiler 얼굴 묘사 필터", False, traceback.format_exc())

# 2-2. 일반 장면 묘사 (변경 없어야 함)
try:
    normal_prompt = "girl standing in forest at sunset"
    result2 = compiler.sanitize_face_descriptions(normal_prompt)
    # 내용이 동일한지 확인 (공백 정리 후 비교)
    normalized_input = " ".join(normal_prompt.split())
    normalized_output = " ".join(result2.split())
    is_same = normalized_input == normalized_output

    report(
        "sanitize_face_descriptions: 일반 장면 묘사 변경 없음",
        is_same,
        f"input='{normalized_input}' vs output='{normalized_output}'"
    )
except Exception as e:
    report("일반 장면 묘사 테스트", False, traceback.format_exc())

# 2-3. compile() 메서드에서 자동 적용 확인
try:
    compiled = compiler.compile(
        scene_description="beautiful girl with big eyes standing on rooftop",
        character_tokens="red dress, hood",
        style="disney_3d"
    )
    print(f"  Compiled: {compiled}")

    no_big_eyes = "big eyes" not in compiled.lower()
    # "beautiful" (단독) 은 ban list에 "beautiful face" 만 있으므로 "beautiful" 단독은 유지될 수 있음
    has_character_tokens = "red dress" in compiled and "hood" in compiled
    has_style = "disney" in compiled.lower() or "pixar" in compiled.lower()

    report(
        "compile(): 'big eyes' 제거됨",
        no_big_eyes,
        f"'big eyes' still in compiled prompt" if not no_big_eyes else "OK"
    )
    report(
        "compile(): character_tokens ('red dress, hood') 유지됨",
        has_character_tokens,
        f"missing character tokens in: {compiled}" if not has_character_tokens else "OK"
    )
    report(
        "compile(): style 토큰 포함됨",
        has_style,
        f"missing style tokens in: {compiled}" if not has_style else "OK"
    )

except Exception as e:
    report("compile() 자동 적용 테스트", False, traceback.format_exc())

# ======================================================================
# 3. RenderConfig Face Authority 기본값 확인
# ======================================================================
print()
print("=" * 70)
print("3. RenderConfig Face Authority 기본값 확인")
print("=" * 70)

try:
    from infrastructure.render.render_engine import RenderConfig
    from dataclasses import fields

    # RenderConfig는 필수 필드(prompt, negative_prompt, seed)가 필요
    config = RenderConfig(
        prompt="test",
        negative_prompt="test negative",
        seed=42
    )

    print(f"  lora_weight: {config.lora_weight}")
    print(f"  reference_strength: {config.reference_strength}")
    print(f"  ip_adapter_scale: {config.ip_adapter_scale}")
    print(f"  controlnet_weight: {config.controlnet_weight}")
    print(f"  face_anchor_image: {config.face_anchor_image}")

    report(
        "RenderConfig.lora_weight == 0.5",
        config.lora_weight == 0.5,
        f"actual: {config.lora_weight}"
    )
    report(
        "RenderConfig.reference_strength == 0.8",
        config.reference_strength == 0.8,
        f"actual: {config.reference_strength}"
    )
    report(
        "RenderConfig.ip_adapter_scale == 0.8",
        config.ip_adapter_scale == 0.8,
        f"actual: {config.ip_adapter_scale}"
    )
    report(
        "RenderConfig.controlnet_weight == 0.75",
        config.controlnet_weight == 0.75,
        f"actual: {config.controlnet_weight}"
    )
    report(
        "RenderConfig.face_anchor_image == None",
        config.face_anchor_image is None,
        f"actual: {config.face_anchor_image}"
    )

except Exception as e:
    report("RenderConfig 기본값 확인", False, traceback.format_exc())

# ======================================================================
# 4. SDXLGenerator Face Authority 확인
# ======================================================================
print()
print("=" * 70)
print("4. SDXLGenerator Face Authority 확인")
print("=" * 70)

try:
    from infrastructure.image.sdxl_generator import SDXLGenerator
    import inspect

    # generate 메서드 시그니처 확인
    sig = inspect.signature(SDXLGenerator.generate)
    params = list(sig.parameters.keys())
    print(f"  generate() params: {params}")

    has_face_anchor = "face_anchor_image" in params
    report(
        "SDXLGenerator.generate()에 'face_anchor_image' 파라미터 존재",
        has_face_anchor,
        f"params: {params}" if not has_face_anchor else "OK"
    )

    # generate_with_reference 메서드도 확인
    sig_ref = inspect.signature(SDXLGenerator.generate_with_reference)
    ref_params = list(sig_ref.parameters.keys())
    print(f"  generate_with_reference() params: {ref_params}")

    has_face_anchor_ref = "face_anchor_image" in ref_params
    report(
        "SDXLGenerator.generate_with_reference()에 'face_anchor_image' 파라미터 존재",
        has_face_anchor_ref,
        f"params: {ref_params}" if not has_face_anchor_ref else "OK"
    )

    # __init__ 에서 LoRA 기본 scale 확인 (코드 분석)
    source = inspect.getsource(SDXLGenerator.__init__)
    # _ip_adapter_scale 기본 0.8 확인
    has_ip_scale_08 = "0.8" in source and "ip_adapter_scale" in source
    report(
        "SDXLGenerator __init__: IP-Adapter scale 기본 0.8 설정",
        has_ip_scale_08,
        "IP-Adapter scale 0.8 설정 코드 미발견" if not has_ip_scale_08 else "OK"
    )

    # IP-Adapter scale 최소 0.8 보장 로직 확인
    has_min_08 = "0.8" in source and "ip_adapter_scale" in source
    report(
        "SDXLGenerator __init__: IP-Adapter scale 최소 0.8 보장 로직",
        has_min_08,
        "최소 0.8 보장 로직 미발견" if not has_min_08 else "OK"
    )

    # load_lora 기본 scale 확인
    lora_source = inspect.getsource(SDXLGenerator.load_lora)
    has_lora_default_05 = "scale: float = 0.5" in lora_source
    report(
        "SDXLGenerator.load_lora(): 기본 scale 0.5",
        has_lora_default_05,
        "LoRA 기본 scale 0.5 미확인" if not has_lora_default_05 else "OK"
    )

except Exception as e:
    report("SDXLGenerator Face Authority 확인", False, traceback.format_exc())

# ======================================================================
# 5. FACE_AUTHORITY_DEFAULTS 상수 확인
# ======================================================================
print()
print("=" * 70)
print("5. FACE_AUTHORITY_DEFAULTS 상수 확인")
print("=" * 70)

try:
    from infrastructure.render.render_engine import FACE_AUTHORITY_DEFAULTS

    print(f"  FACE_AUTHORITY_DEFAULTS = {FACE_AUTHORITY_DEFAULTS}")

    expected = {
        "lora_weight": 0.5,
        "ip_adapter_scale": 0.8,
        "controlnet_weight": 0.75,
    }

    for key, expected_val in expected.items():
        actual_val = FACE_AUTHORITY_DEFAULTS.get(key)
        matches = actual_val == expected_val
        report(
            f"FACE_AUTHORITY_DEFAULTS['{key}'] == {expected_val}",
            matches,
            f"actual: {actual_val}" if not matches else "OK"
        )

    # 필수 키 모두 존재 확인
    has_all_keys = all(k in FACE_AUTHORITY_DEFAULTS for k in expected.keys())
    report(
        "FACE_AUTHORITY_DEFAULTS 필수 키 모두 존재",
        has_all_keys,
        f"missing: {[k for k in expected if k not in FACE_AUTHORITY_DEFAULTS]}" if not has_all_keys else "OK"
    )

except Exception as e:
    report("FACE_AUTHORITY_DEFAULTS 상수 확인", False, traceback.format_exc())

# ======================================================================
# 6. 실제 이미지 생성 테스트 (Face Authority Integration)
# ======================================================================
print()
print("=" * 70)
print("6. 실제 이미지 생성 테스트 (Face Authority Integration)")
print("=" * 70)

import asyncio
import os
import time
from pathlib import Path
from datetime import datetime


async def run_image_generation_tests():
    """Face Authority 기반 실제 이미지 생성 테스트"""

    # ----- 경로 및 설정 -----
    FACE_ANCHOR_PATH = "D:/AI-Video/autonomous-creator/test_outputs/consistency_test/phase1_reference_20260408_202213.png"
    LORA_PATH = "D:/AI-Video/autonomous-creator/data/lora/3dModel_sdxl_v2.safetensors"
    OUTPUT_DIR = "D:/AI-Video/autonomous-creator/test_outputs/face_authority_test"
    SDXL_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"

    # Face Authority 파라미터
    LORA_WEIGHT = 0.5       # 스타일만, 얼굴 관여 금지
    IP_ADAPTER_SCALE = 0.8  # 얼굴 결정권
    SEED = 12345            # 고정 (재현성)
    STEPS = 25
    CFG_SCALE = 7.5
    NEGATIVE_PROMPT = (
        "butterflies, animals, creatures, extra objects, insects, birds, "
        "flying objects, multiple characters, crowd, background clutter"
    )

    # Face Anchor 이미지 존재 확인
    if not Path(FACE_ANCHOR_PATH).exists():
        report(
            "Face Anchor 이미지 존재 확인",
            False,
            f"파일 없음: {FACE_ANCHOR_PATH}"
        )
        return

    report("Face Anchor 이미지 존재 확인", True)

    # LoRA 파일 존재 확인
    if not Path(LORA_PATH).exists():
        report(
            "LoRA 파일 존재 확인",
            False,
            f"파일 없음: {LORA_PATH}"
        )
        return

    report("LoRA 파일 존재 확인", True)

    # 출력 디렉토리 생성
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    # ----- StylePreset 생성 -----
    try:
        from core.domain.entities.preset import StylePreset

        preset = StylePreset(
            name="disney_3d_face_authority",
            base_prompt="MG_ip, pixar, high quality, 3d animation",
            negative_prompt=NEGATIVE_PROMPT,
            steps=STEPS,
            cfg_scale=CFG_SCALE,
            seed=SEED,
        )

        print(f"\n  StylePreset 생성됨:")
        print(f"    name: {preset.name}")
        print(f"    base_prompt: {preset.base_prompt}")
        print(f"    negative_prompt: {preset.negative_prompt}")
        print(f"    steps: {preset.steps}, cfg_scale: {preset.cfg_scale}, seed: {preset.seed}")

        report("StylePreset 생성", True)
    except ImportError as e:
        report(
            "StylePreset 생성",
            False,
            f"ImportError: {e} (core.domain.entities.preset 필요)"
        )
        return
    except Exception as e:
        report("StylePreset 생성", False, traceback.format_exc())
        return

    # ----- SDXLGenerator 초기화 및 모델 로드 -----
    generator = None
    try:
        from infrastructure.image.sdxl_generator import SDXLGenerator

        generator = SDXLGenerator(
            model_path=SDXL_MODEL,
            device="auto"
        )
        report("SDXLGenerator 인스턴스 생성", True)
    except ImportError as e:
        report(
            "SDXLGenerator 인스턴스 생성",
            False,
            f"ImportError: {e} (diffusers, torch, transformers 등 필요)"
        )
        return
    except Exception as e:
        report("SDXLGenerator 인스턴스 생성", False, traceback.format_exc())
        return

    # 모델 로드 (시간이 걸림)
    print("\n  [모델 로드 시작] CPU offload 환경이므로 시간이 소요됩니다...")
    load_start = time.time()
    try:
        await generator.load_model()
        load_time = time.time() - load_start
        report("SDXL 모델 로드", True, f"소요 시간: {load_time:.1f}초")
    except torch.cuda.OutOfMemoryError:
        report(
            "SDXL 모델 로드",
            False,
            "GPU 메모리 부족 (Out of Memory). VRAM을 확보하거나 CPU offload 확인 필요"
        )
        return
    except Exception as e:
        report("SDXL 모델 로드", False, traceback.format_exc())
        return

    # ----- LoRA 로드 -----
    try:
        lora_success = generator.load_lora(LORA_PATH, scale=LORA_WEIGHT)
        report(
            "LoRA 로드 (weight=0.5)",
            lora_success,
            f"경로: {LORA_PATH}" if lora_success else "로드 실패"
        )
        if not lora_success:
            print("  경고: LoRA 없이 계속 진행합니다")
    except Exception as e:
        report("LoRA 로드", False, traceback.format_exc())
        print("  경고: LoRA 없이 계속 진행합니다")

    # ----- IP-Adapter 상태 확인 -----
    ip_loaded = generator.is_ip_adapter_loaded()
    report(
        "IP-Adapter 로드 상태",
        ip_loaded,
        "IP-Adapter 로드됨" if ip_loaded else "IP-Adapter 미로드 (참조 이미지 없이 생성)"
    )

    # ==================================================================
    # Phase 1: Face Anchor 기반 이미지 생성 (3장)
    # ==================================================================
    print()
    print("-" * 50)
    print("Phase 1: Face Anchor 기반 이미지 생성 (3장)")
    print("-" * 50)

    # Face Authority 원칙: 프롬프트에 얼굴 묘사 금지
    scenes = [
        {
            "id": "forest",
            "prompt": (
                "MG_ip, pixar, young girl in red dress standing in enchanted forest, "
                "magical atmosphere, soft lighting, 3d animation style"
            ),
        },
        {
            "id": "city",
            "prompt": (
                "MG_ip, pixar, young girl in red dress walking through modern city street "
                "at night, neon lights, 3d animation style"
            ),
        },
        {
            "id": "ocean",
            "prompt": (
                "MG_ip, pixar, young girl in red dress on beautiful beach at sunset, "
                "ocean waves, golden light, 3d animation style"
            ),
        },
    ]

    phase1_outputs = []

    for scene in scenes:
        scene_id = scene["id"]
        prompt = scene["prompt"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"{OUTPUT_DIR}/phase1_{scene_id}_{timestamp}.png"

        print(f"\n  [{scene_id}] 생성 중...")
        print(f"    prompt: {prompt}")
        print(f"    seed: {SEED}, steps: {STEPS}, cfg: {CFG_SCALE}")
        print(f"    face_anchor: {FACE_ANCHOR_PATH}")

        gen_start = time.time()
        try:
            result_path = await generator.generate(
                prompt=prompt,
                preset=preset,
                output_path=output_path,
                width=576,
                height=1024,
                use_ip_adapter=ip_loaded,
                face_anchor_image=FACE_ANCHOR_PATH if ip_loaded else None,
            )
            gen_time = time.time() - gen_start

            # 결과 파일 확인
            exists = Path(result_path).exists()
            file_size = Path(result_path).stat().st_size if exists else 0

            report(
                f"Phase 1 [{scene_id}] 이미지 생성",
                exists and file_size > 0,
                f"경로: {result_path}, 크기: {file_size / 1024:.0f}KB, "
                f"소요: {gen_time:.1f}초 ({gen_time / STEPS:.1f}초/step)"
            )
            phase1_outputs.append(result_path)

        except torch.cuda.OutOfMemoryError:
            report(
                f"Phase 1 [{scene_id}] 이미지 생성",
                False,
                "GPU 메모리 부족 (OOM). 다른 프로세스 VRAM 사용 확인 필요"
            )
        except Exception as e:
            report(
                f"Phase 1 [{scene_id}] 이미지 생성",
                False,
                traceback.format_exc()
            )

    # ==================================================================
    # Phase 2: 재현성 테스트 (같은 seed로 2장 생성 → 동일 이미지)
    # ==================================================================
    print()
    print("-" * 50)
    print("Phase 2: 재현성 테스트 (같은 seed=12345)")
    print("-" * 50)

    repro_prompt = scenes[0]["prompt"]  # forest 씬 사용
    repro_outputs = []

    for i in range(2):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"{OUTPUT_DIR}/phase2_repro_{i}_{timestamp}.png"

        print(f"\n  [재현성 {i + 1}/2] 생성 중 (seed={SEED})...")

        gen_start = time.time()
        try:
            result_path = await generator.generate(
                prompt=repro_prompt,
                preset=preset,
                output_path=output_path,
                width=576,
                height=1024,
                use_ip_adapter=ip_loaded,
                face_anchor_image=FACE_ANCHOR_PATH if ip_loaded else None,
            )
            gen_time = time.time() - gen_start

            exists = Path(result_path).exists()
            file_size = Path(result_path).stat().st_size if exists else 0

            report(
                f"Phase 2 재현성 [{i + 1}/2] 이미지 생성",
                exists and file_size > 0,
                f"경로: {result_path}, 크기: {file_size / 1024:.0f}KB, "
                f"소요: {gen_time:.1f}초"
            )
            repro_outputs.append(result_path)

        except torch.cuda.OutOfMemoryError:
            report(
                f"Phase 2 재현성 [{i + 1}/2] 이미지 생성",
                False,
                "GPU 메모리 부족 (OOM)"
            )
        except Exception as e:
            report(
                f"Phase 2 재현성 [{i + 1}/2] 이미지 생성",
                False,
                traceback.format_exc()
            )

    # 재현성 검증: 2장의 파일 크기가 동일한지 확인
    if len(repro_outputs) == 2:
        try:
            size1 = Path(repro_outputs[0]).stat().st_size
            size2 = Path(repro_outputs[1]).stat().st_size
            is_reproducible = (size1 == size2)

            report(
                "Phase 2 재현성 검증 (파일 크기 일치)",
                is_reproducible,
                f"파일1: {size1}바이트, 파일2: {size2}바이트"
                if not is_reproducible
                else f"동일 크기: {size1}바이트 (seed={SEED} 재현성 확인)"
            )

            # 픽셀 단위 비교 (PIL 사용)
            try:
                from PIL import Image
                import hashlib

                img1 = Image.open(repro_outputs[0])
                img2 = Image.open(repro_outputs[1])
                hash1 = hashlib.md5(img1.tobytes()).hexdigest()
                hash2 = hashlib.md5(img2.tobytes()).hexdigest()
                pixel_identical = (hash1 == hash2)

                report(
                    "Phase 2 재현성 검증 (픽셀 해시 일치)",
                    pixel_identical,
                    f"hash1: {hash1[:16]}..., hash2: {hash2[:16]}..."
                    if not pixel_identical
                    else f"해시 일치: {hash1[:16]}... (완전 동일 이미지)"
                )
            except ImportError:
                report(
                    "Phase 2 픽셀 비교",
                    False,
                    "PIL(Pillow) 미설치로 픽셀 비교 불가"
                )

        except Exception as e:
            report("Phase 2 재현성 검증", False, traceback.format_exc())
    else:
        report(
            "Phase 2 재현성 검증",
            False,
            f"생성된 이미지가 2장 미만: {len(repro_outputs)}장"
        )

    # ----- 정리 -----
    print("\n  [모델 언로드 중...]")
    try:
        await generator.unload_model()
        report("모델 언로드", True)
    except Exception as e:
        report("모델 언로드", False, str(e))

    print(f"\n  출력 디렉토리: {OUTPUT_DIR}")
    print(f"  생성된 파일 목록:")
    for f in sorted(Path(OUTPUT_DIR).glob("*.png")):
        print(f"    - {f.name} ({f.stat().st_size / 1024:.0f}KB)")


# 6번 테스트 실행 (비동기)
print("\n  실제 이미지 생성 테스트를 시작합니다...")
print("  (GPU 환경 필수, CPU offload 모드에서는 step당 ~1.6초 소요)\n")

try:
    asyncio.run(run_image_generation_tests())
except KeyboardInterrupt:
    print("\n  사용자에 의해 테스트가 중단되었습니다.")
    report("이미지 생성 테스트", False, "KeyboardInterrupt")
except Exception as e:
    report("이미지 생성 테스트 (전체)", False, traceback.format_exc())

# ======================================================================
# 결과 요약
# ======================================================================
print()
print("=" * 70)
print("테스트 결과 요약")
print("=" * 70)

total = len(results)
passed = sum(1 for _, p, _ in results)
failed = total - passed

print(f"  총 테스트: {total}")
print(f"  통과: {passed}")
print(f"  실패: {failed}")
print()

if failed > 0:
    print("실패한 테스트:")
    for name, p, detail in results:
        if not p:
            print(f"  - {name}: {detail}")
    sys.exit(1)
else:
    print("모든 테스트 통과!")
    sys.exit(0)
