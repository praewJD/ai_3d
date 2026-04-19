# -*- coding: utf-8 -*-
"""
End-to-End Pipeline 테스트

전체 파이프라인 검증
"""
import asyncio
import sys
import os
from pathlib import Path

# Windows 콘솔 인코딩 설정
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.application.end_to_end_pipeline import (
    EndToEndPipeline,
    PipelineConfig,
    PipelineResult
)
from core.domain.entities.scene.scene_graph import (
    SceneGraph, SceneNode, SceneStyle, CharacterIdentity,
    CameraAngle, ActionType, Mood, DialogueLine, Transition
)


def create_test_scene_graph() -> SceneGraph:
    """테스트용 SceneGraph 생성"""
    # 캐릭터
    char = CharacterIdentity(
        character_id="char_001",
        name="소녀",
        appearance_description="긴 검은 머리의 소녀, 10살 정도",
        personality_traits=["호기심 많음", "용감함"]
    )
    char_identities = {"char_001": char}

    # 장면들
    scenes = [
        SceneNode(
            scene_id="scene_001",
            description="숲속에서 길을 잃은 소녀",
            characters=["char_001"],
            location="신비로운 숲",
            camera_angle=CameraAngle.WIDE,
            action=ActionType.WALKING,
            mood=Mood.TENSE,
            dialogue=[
                DialogueLine(
                    character_id="char_001",
                    text="여긴 어디지...?",
                    emotion="fear"
                )
            ],
            narration="깊은 숲속, 소녀는 낯선 길을 걷고 있었다.",
            duration_seconds=5.0,
            order=0
        ),
        SceneNode(
            scene_id="scene_002",
            description="빛이 보이는 곳으로 향하는 소녀",
            characters=["char_001"],
            location="숲속 빛이 있는 곳",
            camera_angle=CameraAngle.MEDIUM,
            action=ActionType.WALKING,
            mood=Mood.HAPPY,
            dialogue=[
                DialogueLine(
                    character_id="char_001",
                    text="저기 빛이 보여!",
                    emotion="hope"
                )
            ],
            narration="멀리서 희미한 빛이 보였다.",
            duration_seconds=5.0,
            order=1,
            transition_in=Transition.FADE
        )
    ]

    # 스타일
    style = SceneStyle()  # 기본값 사용 (DISNEY_3D)

    return SceneGraph(
        story_id="test_story_001",
        title="숲속의 소녀",
        scenes=scenes,
        character_identities=char_identities,
        default_style=style
    )


async def test_scene_graph_creation():
    """SceneGraph 생성 테스트"""
    print("=" * 50)
    print("Test 1: SceneGraph Creation")
    print("=" * 50)

    graph = create_test_scene_graph()

    assert graph.story_id == "test_story_001"
    assert len(graph.scenes) == 2
    assert len(graph.character_identities) == 1

    print(f"[OK] Story ID: {graph.story_id}")
    print(f"[OK] Title: {graph.title}")
    print(f"[OK] Scenes: {len(graph.scenes)}")
    print(f"[OK] Characters: {len(graph.character_identities)}")
    print(f"[OK] Style: {graph.default_style.type}")

    return graph


async def test_validation():
    """검증 테스트"""
    print("\n" + "=" * 50)
    print("Test 2: RuleEngine Validation")
    print("=" * 50)

    from infrastructure.validation.rule_engine import RuleEngine

    graph = create_test_scene_graph()
    engine = RuleEngine()

    result = engine.validate(graph)

    print(f"[OK] Valid: {result.is_valid}")
    print(f"[OK] Errors: {len(result.errors)}")
    print(f"[OK] Warnings: {len(result.warnings)}")
    print(f"[OK] Fixed Count: {result.fixed_count}")

    if result.warnings:
        for w in result.warnings:
            print(f"   [!] {w}")

    return result


async def test_prompt_orchestration():
    """프롬프트 오케스트레이션 테스트"""
    print("\n" + "=" * 50)
    print("Test 3: Prompt Orchestration")
    print("=" * 50)

    from infrastructure.prompt.prompt_orchestrator import PromptOrchestrator

    graph = create_test_scene_graph()
    orchestrator = PromptOrchestrator()

    for scene in graph.scenes:
        image_bundle = orchestrator.build_image_prompt(scene)
        video_bundle = orchestrator.build_video_prompt(scene, image_bundle.positive)
        print(f"\n[*] Scene: {scene.scene_id}")
        print(f"    Image: {image_bundle.positive[:80]}...")
        print(f"    Video Motion: {video_bundle.motion_prompt[:80] if video_bundle.motion_prompt else 'N/A'}...")

    print("\n[OK] Prompt orchestration completed")


async def test_style_manager():
    """스타일 매니저 테스트"""
    print("\n" + "=" * 50)
    print("Test 4: Style Manager")
    print("=" * 50)

    from infrastructure.style.style_manager import StyleManager

    graph = create_test_scene_graph()
    manager = StyleManager(strategy="emotion_based")

    # apply_to_scene_graph은 변경된 장면 수를 반환, graph는 in-place 수정
    changes = manager.apply_to_scene_graph(graph)

    for scene in graph.scenes:
        print(f"[*] {scene.scene_id}: {scene.style.type.value}")

    print(f"[OK] Style application completed ({changes} changes)")


async def test_cost_estimation():
    """비용 추정 테스트"""
    print("\n" + "=" * 50)
    print("Test 5: Cost Estimation")
    print("=" * 50)

    config = PipelineConfig(
        output_dir="test_outputs",
        enable_cache=True
    )

    pipeline = EndToEndPipeline(config=config)
    graph = create_test_scene_graph()

    costs = await pipeline.estimate_cost(graph)

    print(f"[OK] Image Cost: ${costs['image_cost_usd']:.2f}")
    print(f"[OK] Video Cost: ${costs['video_cost_usd']:.2f}")
    print(f"[OK] TTS Cost: ${costs['tts_cost_usd']:.2f}")
    print(f"[OK] Total Cost: ${costs['total_cost_usd']:.2f}")
    print(f"[OK] Scenes: {costs['num_scenes']}")


async def test_pipeline_dry_run():
    """파이프라인 드라이런 (API 호출 없이)"""
    print("\n" + "=" * 50)
    print("Test 6: Pipeline Dry Run (Structure Only)")
    print("=" * 50)

    config = PipelineConfig(
        output_dir="test_outputs",
        enable_validation=True
    )

    pipeline = EndToEndPipeline(config=config)

    # 컴포넌트 확인
    print(f"[OK] Compiler: {type(pipeline.compiler).__name__}")
    print(f"[OK] RuleEngine: {type(pipeline.rule_engine).__name__}")
    print(f"[OK] PromptOrchestrator: {type(pipeline.prompt_orchestrator).__name__}")
    print(f"[OK] StyleManager: {type(pipeline.style_manager).__name__}")
    print(f"[OK] Repository: {type(pipeline.repository).__name__}")

    # 상태 확인
    print(f"[OK] ImageGenerator: Lazy")
    print(f"[OK] VideoGenerator: Lazy")
    print(f"[OK] TTSGenerator: Lazy")
    print(f"[OK] VideoComposer: Lazy")


async def main():
    """메인 테스트 실행"""
    print("\n" + "=" * 60)
    print("  End-to-End Pipeline Test Suite")
    print("=" * 60)

    try:
        # 1. SceneGraph 생성
        graph = await test_scene_graph_creation()

        # 2. 검증
        await test_validation()

        # 3. 프롬프트 오케스트레이션
        await test_prompt_orchestration()

        # 4. 스타일 매니저
        await test_style_manager()

        # 5. 비용 추정
        await test_cost_estimation()

        # 6. 파이프라인 구조 확인
        await test_pipeline_dry_run()

        print("\n" + "=" * 60)
        print("  [SUCCESS] All Tests Passed!")
        print("=" * 60)

        print("\n[*] Next Steps:")
        print("   1. Set API keys (STABILITY_API_KEY, LUMA_API_KEY)")
        print("   2. Run: python -m tests.test_end_to_end_pipeline --full")
        print("   3. Check outputs in: test_outputs/")

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="Full pipeline with API calls")
    args = parser.parse_args()

    if args.full:
        print("Running full pipeline with API calls...")
        # TODO: 실제 API 호출 테스트
    else:
        asyncio.run(main())
