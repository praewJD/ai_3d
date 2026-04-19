# -*- coding: utf-8 -*-
"""
프롬프트 + 이미지 생성 테스트

SceneGraph → Prompt → Image (기존 SD35Generator 사용)
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.domain.entities.scene.scene_graph import (
    SceneGraph, SceneNode, SceneStyle, CharacterIdentity,
    CameraAngle, ActionType, Mood, DialogueLine, Transition, StyleType
)
from infrastructure.prompt.prompt_orchestrator import PromptOrchestrator
from infrastructure.style.style_manager import StyleManager
from infrastructure.image.sd35_generator import SD35Generator
from core.domain.entities.preset import StylePreset


def create_test_scene_graph() -> SceneGraph:
    """테스트용 SceneGraph 생성"""
    char = CharacterIdentity(
        character_id="char_001",
        name="เด็กสาว",  # 태국어: 소녀
        appearance_description="สาวน้อยผมดำยาว อายุประมาณ 10 ขวบ",
        personality_traits=["อยากรู้", "กล้าหาญ"]
    )
    char_identities = {"char_001": char}

    scenes = [
        SceneNode(
            scene_id="scene_001",
            description="เด็กสาวหลงทางในป่า",  # 숲속에서 길 잃은 소녀
            characters=["char_001"],
            location="ป่าลึกลับ",  # 신비로운 숲
            camera_angle=CameraAngle.WIDE,
            action=ActionType.WALKING,
            mood=Mood.TENSE,
            dialogue=[
                DialogueLine(
                    character_id="char_001",
                    text="ที่นี่คือที่ไหน?",
                    emotion="fear"
                )
            ],
            narration="ในป่าลึก เด็กสาวกำลังเดินบนทางที่ไม่คุ้นเคย",
            duration_seconds=5.0,
            order=0
        ),
        SceneNode(
            scene_id="scene_002",
            description="เด็กสาวเดินไปหาแสง",
            characters=["char_001"],
            location="ที่มีแสงในป่า",
            camera_angle=CameraAngle.MEDIUM,
            action=ActionType.WALKING,
            mood=Mood.HAPPY,
            dialogue=[
                DialogueLine(
                    character_id="char_001",
                    text="ดูสิ! มีแสงอยู่ที่นั่น!",
                    emotion="hope"
                )
            ],
            narration="มองเห็นแสงสว่างจางๆ อยู่ไกลออกไป",
            duration_seconds=5.0,
            order=1,
            transition_in=Transition.FADE
        )
    ]

    style = SceneStyle(type=StyleType.DISNEY_3D)

    return SceneGraph(
        story_id="test_thai_001",
        title="เด็กสาวในป่า",
        scenes=scenes,
        character_identities=char_identities,
        default_style=style
    )


async def test_prompt_generation():
    """프롬프트 생성 테스트"""
    print("=" * 50)
    print("Test 1: Prompt Generation")
    print("=" * 50)

    graph = create_test_scene_graph()
    orchestrator = PromptOrchestrator()

    for scene in graph.scenes:
        image_bundle = orchestrator.build_image_prompt(scene)
        video_prompt = orchestrator.build_video_prompt(scene, image_bundle.positive)

        print(f"\n[*] Scene: {scene.scene_id}")
        print(f"    Image Prompt: {image_bundle.positive[:100]}...")
        print(f"    Video Motion: {video_prompt.motion_prompt[:60] if video_prompt.motion_prompt else 'N/A'}...")

    print("\n[OK] Prompt generation completed")
    return graph


async def test_style_application():
    """스타일 적용 테스트"""
    print("\n" + "=" * 50)
    print("Test 2: Style Application")
    print("=" * 50)

    graph = create_test_scene_graph()
    manager = StyleManager(strategy="emotion_based")

    changes = manager.apply_to_scene_graph(graph)

    for scene in graph.scenes:
        print(f"[*] {scene.scene_id}: {scene.style.type.value}")

    print(f"[OK] Style applied ({changes} changes)")


async def test_image_generation():
    """이미지 생성 테스트 (기존 SD35Generator)"""
    print("\n" + "=" * 50)
    print("Test 3: Image Generation (SD35Generator)")
    print("=" * 50)

    graph = create_test_scene_graph()
    orchestrator = PromptOrchestrator()

    # SD35Generator 초기화
    generator = SD35Generator()

    # 모델 로드 확인
    print(f"[*] Model loaded: {generator.is_loaded()}")

    if not generator.is_loaded():
        print("[!] Loading model (first run may take time)...")
        await generator.load_model()

    # 출력 디렉토리
    output_dir = Path("test_outputs/images")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 프리셋
    preset = StylePreset.create_default()

    for i, scene in enumerate(graph.scenes):
        image_bundle = orchestrator.build_image_prompt(scene)

        output_path = str(output_dir / f"scene_{i:03d}.png")

        print(f"\n[*] Generating image for: {scene.scene_id}")
        print(f"    Prompt: {image_bundle.positive[:80]}...")

        try:
            result_path = await generator.generate(
                prompt=image_bundle.positive,
                preset=preset,
                output_path=output_path
            )
            print(f"    [OK] Saved: {result_path}")
        except Exception as e:
            print(f"    [ERROR] {e}")

    print("\n[OK] Image generation completed")


async def main():
    """메인 테스트"""
    print("\n" + "=" * 60)
    print("  Prompt + Image Pipeline Test")
    print("  (Using existing SD35Generator)")
    print("=" * 60)

    try:
        # 1. 프롬프트 생성
        graph = await test_prompt_generation()

        # 2. 스타일 적용
        await test_style_application()

        # 3. 이미지 생성 (GPU 필요)
        print("\n[?] Run image generation? (requires GPU)")
        print("    Press Enter to continue, or Ctrl+C to skip...")

        try:
            input()
            await test_image_generation()
        except KeyboardInterrupt:
            print("\n[SKIP] Image generation skipped")

        print("\n" + "=" * 60)
        print("  [SUCCESS] Tests Completed!")
        print("=" * 60)

        print("\n[*] Outputs saved in: test_outputs/")

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
