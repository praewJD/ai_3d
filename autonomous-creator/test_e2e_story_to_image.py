# -*- coding: utf-8 -*-
"""
E2E 테스트: StorySpec -> 이미지 시퀀스 생성

StorySpec을 직접 생성해서 (LLM 호출 없이) StoryToImagePipeline에 전달하여
이미지 생성하는 통합 테스트.

테스트 구성:
1. Import 테스트: 모듈 임포트 검증
2. 프롬프트 빌드 테스트: ScenePromptBuilder로 각 씬 프롬프트 생성
3. 이미지 생성 테스트 (GPU 환경에서만): StoryToImagePipeline E2E 실행
"""
import sys
import os
import asyncio
import logging
from pathlib import Path
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_e2e")


# ============================================================
# 테스트용 StorySpec 데이터
# ============================================================

def create_test_story():
    """테스트용 StorySpec 생성 (숲속의 소녀)"""
    from infrastructure.story.story_spec import (
        StorySpec, SceneSpec, CharacterSpec, ArcSpec,
        TargetFormat, ScenePurpose,
    )

    test_story = StorySpec(
        title="숲속의 소녀",
        genre="fantasy",
        target=TargetFormat.SHORTS,
        duration=21.0,
        characters=[
            CharacterSpec(
                id="char_girl",
                name="Lily",
                appearance="young girl with short brown hair, wearing red dress",
                traits=["brave", "curious"],
                seed=12345,
            )
        ],
        arc=ArcSpec(
            hook="Lily discovers a glowing flower in the forest",
            build="She follows a mysterious path deeper into the woods",
            climax="She finds a magical hidden pond",
            resolution="Lily smiles as magical fireflies surround her",
        ),
        scenes=[
            SceneSpec(
                id="scene_1", purpose=ScenePurpose.HOOK, camera="close-up",
                mood="mysterious",
                action="young girl discovers a glowing flower on the forest floor, eyes wide with wonder",
                characters=["char_girl"], location="dark enchanted forest",
                duration=3.0, emotion="surprise",
            ),
            SceneSpec(
                id="scene_2", purpose=ScenePurpose.BUILD, camera="medium_shot",
                mood="mysterious",
                action="girl walks along a mysterious path deeper into the enchanted forest",
                characters=["char_girl"], location="forest path with tall trees",
                duration=3.0, emotion="curiosity",
            ),
            SceneSpec(
                id="scene_3", purpose=ScenePurpose.BUILD, camera="wide_shot",
                mood="dark",
                action="girl stands before a massive ancient tree with glowing roots",
                characters=["char_girl"], location="ancient tree clearing",
                duration=3.0, emotion="awe",
            ),
            SceneSpec(
                id="scene_4", purpose=ScenePurpose.CLIMAX, camera="wide_shot",
                mood="bright",
                action="girl discovers a magical hidden pond glowing with blue light",
                characters=["char_girl"], location="hidden magical pond",
                duration=3.0, emotion="wonder",
            ),
            SceneSpec(
                id="scene_5", purpose=ScenePurpose.CLIMAX, camera="close-up",
                mood="bright",
                action="girl reaches hand toward the glowing water, reflection shimmering",
                characters=["char_girl"], location="magical pond edge",
                duration=3.0, emotion="joy",
            ),
            SceneSpec(
                id="scene_6", purpose=ScenePurpose.RESOLUTION, camera="wide_shot",
                mood="bright",
                action="magical fireflies surround the girl as she smiles peacefully",
                characters=["char_girl"], location="enchanted forest pond at dusk",
                duration=6.0, emotion="peace",
            ),
        ],
        emotion_curve=[0.3, 0.5, 0.7, 0.9, 1.0, 0.4],
    )
    return test_story


# ============================================================
# Face Anchor 참조 이미지 경로
# ============================================================

FACE_ANCHOR_PATH = (
    "D:/AI-Video/autonomous-creator/"
    "test_outputs/consistency_test/phase1_reference_20260408_202213.png"
)


# ============================================================
# 테스트 결과 유틸리티
# ============================================================

class TestResults:
    """테스트 결과 수집기"""

    def __init__(self):
        self.results = []

    def record(self, name: str, passed: bool, detail: str = ""):
        status = "PASS" if passed else "FAIL"
        self.results.append((name, status, detail))
        marker = "V" if passed else "X"
        print(f"  [{marker}] {status}: {name}")
        if detail:
            print(f"       {detail}")

    def summary(self):
        """최종 결과 요약 출력"""
        total = len(self.results)
        passed = sum(1 for _, s, _ in self.results if s == "PASS")
        failed = total - passed

        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        for name, status, detail in self.results:
            marker = "V" if status == "PASS" else "X"
            print(f"  [{marker}] {status}: {name}")
            if detail:
                print(f"       {detail}")
        print("-" * 60)
        print(f"  총 {total}개, PASS {passed}개, FAIL {failed}개")
        print("=" * 60)

        return failed == 0


# ============================================================
# 테스트 1: Import 테스트
# ============================================================

def test_imports(results: TestResults):
    """모듈 임포트 검증"""
    print("\n--- Import 테스트 ---")

    # ScenePromptBuilder 임포트
    try:
        from infrastructure.pipeline.scene_prompt_builder import ScenePromptBuilder
        results.record("ScenePromptBuilder import", True)
    except Exception as e:
        results.record("ScenePromptBuilder import", False, str(e))
        return False

    # StoryToImagePipeline 임포트
    try:
        from infrastructure.pipeline.story_to_image_pipeline import (
            StoryToImagePipeline, PipelineConfig, PipelineResult,
        )
        results.record("StoryToImagePipeline import", True)
        results.record("PipelineConfig import", True)
        results.record("PipelineResult import", True)
    except Exception as e:
        results.record("StoryToImagePipeline import", False, str(e))
        return False

    # __init__.py 패키지 임포트
    try:
        from infrastructure.pipeline import (
            ScenePromptBuilder,
            StoryToImagePipeline,
            PipelineConfig,
            PipelineResult,
        )
        results.record("__init__.py 패키지 임포트", True)
    except Exception as e:
        results.record("__init__.py 패키지 임포트", False, str(e))
        return False

    return True


# ============================================================
# 테스트 2: 프롬프트 빌드 테스트
# ============================================================

def test_prompt_building(results: TestResults):
    """ScenePromptBuilder로 각 씬의 프롬프트 생성 테스트 (모델 없이)"""
    print("\n--- 프롬프트 빌드 테스트 ---")

    from infrastructure.pipeline.scene_prompt_builder import ScenePromptBuilder

    story = create_test_story()
    builder = ScenePromptBuilder()

    all_passed = True

    for scene in story.scenes:
        try:
            prompt = builder.build_prompt(
                scene=scene,
                characters=story.characters,
                style="disney_3d",
            )

            # 프롬프트가 비어있지 않은지 확인
            if not prompt or len(prompt) < 10:
                results.record(
                    f"프롬프트 생성: {scene.id}",
                    False,
                    f"프롬프트가 너무 짧음 (len={len(prompt)})"
                )
                all_passed = False
                continue

            # trigger_words 포함 확인
            has_trigger = "MG_ip" in prompt
            # 스타일 토큰 포함 확인
            has_style = "Disney 3D" in prompt or "pixar" in prompt.lower()

            results.record(
                f"프롬프트 생성: {scene.id}",
                True,
                f"len={len(prompt)}, trigger={has_trigger}, style={has_style}"
            )

            # 각 씬 프롬프트 내용 출력 (디버깅용)
            print(f"       프롬프트: {prompt[:120]}...")

        except Exception as e:
            results.record(
                f"프롬프트 생성: {scene.id}",
                False,
                str(e)
            )
            all_passed = False

    # 네거티브 프롬프트 테스트
    try:
        neg_prompt = builder.build_negative_prompt()
        if neg_prompt:
            results.record("네거티브 프롬프트 생성", True, f"len={len(neg_prompt)}")
        else:
            results.record("네거티브 프롬프트 생성", False, "빈 네거티브 프롬프트")
            all_passed = False
    except Exception as e:
        results.record("네거티브 프롬프트 생성", False, str(e))
        all_passed = False

    return all_passed


# ============================================================
# 테스트 3: 이미지 생성 E2E 테스트 (GPU 있을 때만)
# ============================================================

def check_gpu_available() -> bool:
    """GPU 사용 가능 여부 확인"""
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            logger.info(f"GPU 감지: {gpu_name}")
            return True
        else:
            logger.info("CUDA 사용 불가 - CPU 환경")
            return False
    except ImportError:
        logger.info("PyTorch 미설치 - GPU 확인 불가")
        return False


async def test_image_generation(results: TestResults):
    """StoryToImagePipeline E2E 이미지 생성 테스트 (GPU 필요)"""
    print("\n--- 이미지 생성 E2E 테스트 ---")

    from infrastructure.pipeline.story_to_image_pipeline import (
        StoryToImagePipeline, PipelineConfig,
    )

    # GPU 확인
    if not check_gpu_available():
        results.record(
            "이미지 생성 (스킵)",
            True,
            "GPU 없음 - 이미지 생성 테스트 스킵"
        )
        print("  [i] GPU가 없어 이미지 생성 테스트를 스킵합니다.")
        return True

    # Face Anchor 이미지 확인
    ref_image = FACE_ANCHOR_PATH
    if not Path(ref_image).exists():
        logger.warning(f"Face Anchor 이미지 없음: {ref_image}")
        ref_image = None
        print(f"  [!] Face Anchor 이미지를 찾을 수 없습니다: {ref_image}")
        print("  [!] Face Anchor 없이 진행합니다.")
    else:
        print(f"  [i] Face Anchor 이미지 확인: {ref_image}")

    # PipelineConfig 설정
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = str(PROJECT_ROOT / "test_outputs" / f"e2e_test_{timestamp}")

    config = PipelineConfig(
        character_ref_images={
            "char_girl": ref_image,
        } if ref_image else {},
        output_dir=output_dir,
        lora_scale=0.5,       # Face Authority: 스타일만
        ip_adapter_scale=0.8,  # Face Authority: 얼굴 결정권
    )

    print(f"  [i] 출력 디렉토리: {output_dir}")
    print(f"  [i] LoRA scale: {config.lora_scale}")
    print(f"  [i] IP-Adapter scale: {config.ip_adapter_scale}")
    print(f"  [i] Face Anchor: {'있음' if ref_image else '없음'}")

    # StorySpec 생성
    story = create_test_story()

    # 파이프라인 실행
    try:
        pipeline = StoryToImagePipeline(config)

        # 모델 로드
        print("\n  [i] 모델 로드 시작...")
        await pipeline.load()
        results.record("모델 로드", True)

        # 이미지 생성
        print("  [i] 이미지 생성 시작...")
        result = await pipeline.run(story)

        # 결과 검증
        results.record(
            "파이프라인 실행 완료",
            result.success,
            f"images={len(result.image_paths)}/{result.scene_count}, "
            f"failed={result.failed_scenes}, time={result.total_time:.1f}s"
        )

        if result.image_paths:
            results.record(
                "이미지 파일 생성",
                True,
                f"{len(result.image_paths)}개 이미지 생성됨"
            )
            # 각 이미지 파일 존재 확인
            for path in result.image_paths:
                exists = Path(path).exists()
                results.record(
                    f"이미지 파일 확인: {Path(path).name}",
                    exists,
                    f"path={path}"
                )
        else:
            results.record("이미지 파일 생성", False, "생성된 이미지 없음")

        if result.failed_scenes:
            results.record(
                "실패한 씬",
                False,
                f"failed_scenes={result.failed_scenes}"
            )

        # 모델 언로드
        try:
            await pipeline.unload()
            results.record("모델 언로드", True)
        except Exception as e:
            results.record("모델 언로드", False, str(e))

        return result.success

    except Exception as e:
        results.record("이미지 생성 E2E", False, str(e))
        logger.error(f"이미지 생성 실패: {e}", exc_info=True)
        return False


# ============================================================
# 메인 실행
# ============================================================

async def main():
    """전체 테스트 실행"""
    print("=" * 60)
    print("E2E 테스트: StorySpec -> 이미지 시퀀스")
    print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    results = TestResults()

    # 테스트 1: Import
    imports_ok = test_imports(results)
    if not imports_ok:
        print("\n[!] Import 실패 - 이후 테스트를 중단합니다.")
        results.summary()
        return 1

    # 테스트 2: 프롬프트 빌드
    prompts_ok = test_prompt_building(results)
    if not prompts_ok:
        print("\n[!] 프롬프트 빌드 실패 - 이미지 생성 테스트를 중단합니다.")
        results.summary()
        return 1

    # 테스트 3: 이미지 생성 (GPU 있을 때만)
    await test_image_generation(results)

    # 결과 요약
    all_passed = results.summary()
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
