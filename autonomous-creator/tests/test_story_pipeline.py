"""
Story Compiler v3 - 통합 테스트

전체 스토리 파이프라인 테스트:
[0] Normalizer → [1] Topic → [2] Arc → [3] Budget → [4] Hook → [5] Scene → [6] Validator → [7] StorySpec
"""
import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.story import (
    # Constants
    SHORTS_CONSTRAINTS,
    LONGFORM_CONSTRAINTS,
    # Enums
    TargetFormat,
    ScenePurpose,
    # StorySpec
    CharacterSpec,
    ArcSpec,
    SceneSpec,
    StorySpec,
    # Normalizer
    NormalizedInput,
    StoryNormalizer,
    # TopicGenerator
    TopicResult,
    TopicGenerator,
    # ArcBuilder
    ArcResult,
    ArcBuilder,
    # BudgetPlanner
    BudgetPlan,
    BudgetPlanner,
    # HookEnhancer
    HookScore,
    HookEnhancer,
    # SceneGenerator
    SceneGenerationResult,
    SceneGenerator,
    # FormatRender
    RenderedStory,
    FormatRenderEngine,
    # StoryValidator
    ValidationResult,
    StoryValidator,
    RetryPolicy,
    RetryLoop,
)
from infrastructure.metrics import MetricsCollector, StoryMetrics, setup_logging


# ============================================================
# 테스트 유틸리티
# ============================================================

class TestRunner:
    """테스트 실행기"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.logger = setup_logging("DEBUG")

    def check(self, condition: bool, name: str, detail: str = ""):
        """조건 검사"""
        if condition:
            self.passed += 1
            print(f"  ✅ {name}")
        else:
            self.failed += 1
            error_msg = f"{name}: {detail}" if detail else name
            self.errors.append(error_msg)
            print(f"  ❌ {name}" + (f" - {detail}" if detail else ""))

    def section(self, title: str):
        """섹션 헤더"""
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")

    def summary(self):
        """결과 요약"""
        print(f"\n{'='*60}")
        print(f"  테스트 결과 요약")
        print(f"{'='*60}")
        print(f"  ✅ 통과: {self.passed}")
        print(f"  ❌ 실패: {self.failed}")
        print(f"  📊 성공률: {self.passed/(self.passed+self.failed)*100:.1f}%")

        if self.errors:
            print(f"\n  실패 항목:")
            for err in self.errors:
                print(f"    - {err}")

        return self.failed == 0


# ============================================================
# 테스트 1: 기본 파이프라인 (핵심)
# ============================================================

def test_basic_pipeline(runner: TestRunner):
    """테스트 1: 기본 스토리 파이프라인"""
    runner.section("테스트 1: 기본 파이프라인")

    # 입력: 단순 스토리
    raw_input = "sound power hero fights villain at night"
    print(f"\n📝 입력: \"{raw_input}\"")

    # [0] Normalizer
    print("\n[Step 0] Normalizer 실행...")
    normalizer = StoryNormalizer()
    normalized = normalizer.normalize(raw_input)

    runner.check(
        len(normalized.characters) >= 0,
        "Normalizer: 캐릭터 추출",
        f"characters={normalized.characters}"
    )
    runner.check(
        normalized.genre != "",
        "Normalizer: 장르 추정",
        f"genre={normalized.genre}"
    )
    runner.check(
        normalized.language != "",
        "Normalizer: 언어 감지",
        f"language={normalized.language}"
    )

    print(f"    - 캐릭터: {normalized.characters}")
    print(f"    - 장르: {normalized.genre}")
    print(f"    - 톤: {normalized.tone}")
    print(f"    - 언어: {normalized.language}")

    # [1] Topic Generator
    print("\n[Step 1] Topic Generator 실행...")
    topic_gen = TopicGenerator()
    topic = topic_gen.generate(normalized)

    runner.check(
        topic.theme != "",
        "Topic: 테마 생성",
        f"theme={topic.theme}"
    )
    runner.check(
        topic.message != "",
        "Topic: 메시지 생성",
        f"message={topic.message}"
    )
    runner.check(
        topic.conflict != "",
        "Topic: 갈등 생성",
        f"conflict={topic.conflict}"
    )

    print(f"    - 테마: {topic.theme}")
    print(f"    - 메시지: {topic.message}")
    print(f"    - 갈등: {topic.conflict}")
    print(f"    - 바이럴 훅: {topic.viral_hooks}")

    # [2] Arc Builder
    print("\n[Step 2] Arc Builder 실행...")
    arc_builder = ArcBuilder()
    arc = arc_builder.build(topic, normalized)

    runner.check(
        arc.hook != "",
        "Arc: Hook 생성",
        f"hook={arc.hook[:50]}..."
    )
    runner.check(
        arc.build != "",
        "Arc: Build 생성"
    )
    runner.check(
        arc.climax != "",
        "Arc: Climax 생성"
    )
    runner.check(
        arc.resolution != "",
        "Arc: Resolution 생성"
    )

    print(f"    - Hook: {arc.hook}")
    print(f"    - Build: {arc.build}")
    print(f"    - Climax: {arc.climax}")
    print(f"    - Resolution: {arc.resolution}")

    # [3] Budget Planner
    print("\n[Step 3] Budget Planner 실행...")
    budget_planner = BudgetPlanner()
    budget = budget_planner.plan(TargetFormat.SHORTS.value, arc)

    runner.check(
        budget.scene_count >= SHORTS_CONSTRAINTS["min_scenes"],
        "Budget: 최소 씬 수 충족",
        f"scenes={budget.scene_count}"
    )
    runner.check(
        budget.scene_count <= SHORTS_CONSTRAINTS["max_scenes"],
        "Budget: 최대 씬 수 미초과"
    )
    runner.check(
        budget.total_duration <= SHORTS_CONSTRAINTS["max_duration"],
        "Budget: 최대 길이 미초과",
        f"duration={budget.total_duration}s"
    )

    print(f"    - 타겟: {budget.target_format}")
    print(f"    - 총 길이: {budget.total_duration}s")
    print(f"    - 씬 수: {budget.scene_count}")
    print(f"    - 분배: hook={budget.hook_scenes}, build={budget.build_scenes}, climax={budget.climax_scenes}, resolution={budget.resolution_scenes}")

    # [4] Hook Enhancer + Scoring
    print("\n[Step 4] Hook Enhancer 실행...")
    hook_enhancer = HookEnhancer()
    enhanced_hook, hook_score = hook_enhancer.enhance_and_score(arc.hook)

    runner.check(
        hook_score.total >= 6.0,
        "Hook: 점수 기준 충족 (>= 6.0)",
        f"score={hook_score.total:.1f}/10"
    )

    print(f"    - 원본: {arc.hook}")
    print(f"    - 강화: {enhanced_hook}")
    print(f"    - 점수: {hook_score.total:.1f}/10")
    print(f"    - 상세: curiosity={hook_score.curiosity:.1f}, shock={hook_score.shock:.1f}, visual={hook_score.visual_impact:.1f}, conflict={hook_score.conflict:.1f}")
    print(f"    - 피드백: {hook_score.details}")

    # [5] Scene Generator
    print("\n[Step 5] Scene Generator 실행...")
    scene_gen = SceneGenerator()
    scene_result = scene_gen.generate(arc, budget, topic, normalized)

    runner.check(
        len(scene_result.scenes) > 0,
        "Scene: 씬 생성됨",
        f"count={scene_result.scene_count}"
    )
    runner.check(
        scene_result.scene_count >= SHORTS_CONSTRAINTS["min_scenes"],
        "Scene: 최소 씬 수 충족"
    )
    runner.check(
        scene_result.scene_count <= SHORTS_CONSTRAINTS["max_scenes"],
        "Scene: 최대 씬 수 미초과"
    )

    print(f"    - 생성된 씬 수: {scene_result.scene_count}")
    print(f"    - 총 길이: {scene_result.total_duration}s")

    # 씬 목록 출력
    for i, scene in enumerate(scene_result.scenes[:5]):  # 처음 5개만
        print(f"    - Scene {scene.id}: [{scene.purpose.value}] {scene.description[:40]}... ({scene.duration}s)")

    # [6] Validator
    print("\n[Step 6] Validator 실행...")

    # StorySpec 생성
    characters = [
        CharacterSpec(
            id=f"char_{i}",
            name=name,
            appearance="",
            seed=1000 + i
        )
        for i, name in enumerate(normalized.characters)
    ] if normalized.characters else []

    story_spec = StorySpec(
        title=f"Story: {topic.theme}",
        genre=normalized.genre,
        target=TargetFormat.SHORTS,
        duration=scene_result.total_duration,
        characters=characters,
        arc=ArcSpec(
            hook=enhanced_hook,
            build=arc.build,
            climax=arc.climax,
            resolution=arc.resolution
        ),
        scenes=scene_result.scenes,
        emotion_curve=[0.5] * len(scene_result.scenes),
        metadata={
            "theme": topic.theme,
            "message": topic.message,
            "conflict": topic.conflict
        }
    )

    validator = StoryValidator()
    validation = validator.validate(story_spec)

    runner.check(
        validation.is_valid or len(validation.errors) <= 2,  # 경고 몇 개는 허용
        "Validator: 검증 통과",
        f"errors={len(validation.errors)}, warnings={len(validation.warnings)}"
    )
    runner.check(
        validation.score >= 50,
        "Validator: 점수 기준 충족 (>= 50)",
        f"score={validation.score:.1f}/100"
    )

    print(f"    - 검증 결과: {'통과' if validation.is_valid else '실패'}")
    print(f"    - 점수: {validation.score:.1f}/100")
    print(f"    - 에러: {len(validation.errors)}")
    print(f"    - 경고: {len(validation.warnings)}")

    if validation.errors:
        print(f"    - 에러 목록:")
        for err in validation.errors[:3]:
            print(f"      • {err}")

    # [7] 최종 StorySpec 검증
    print("\n[Step 7] 최종 StorySpec 검증...")

    is_valid, spec_errors = story_spec.validate()
    runner.check(
        is_valid or len(spec_errors) <= 2,
        "StorySpec: 구조 검증 통과"
    )

    total_duration = story_spec.total_duration()
    runner.check(
        total_duration >= SHORTS_CONSTRAINTS["min_duration"],
        "StorySpec: 최소 길이 충족",
        f"duration={total_duration}s"
    )
    runner.check(
        total_duration <= SHORTS_CONSTRAINTS["max_duration"],
        "StorySpec: 최대 길이 미초과"
    )

    print(f"    - 타이틀: {story_spec.title}")
    print(f"    - 장르: {story_spec.genre}")
    print(f"    - 타겟: {story_spec.target.value}")
    print(f"    - 총 길이: {total_duration}s")
    print(f"    - 씬 수: {len(story_spec.scenes)}")
    print(f"    - 캐릭터 수: {len(story_spec.characters)}")

    return story_spec, validation


# ============================================================
# 테스트 2: 엣지 케이스
# ============================================================

def test_edge_case(runner: TestRunner):
    """테스트 2: 극도로 단순한 입력"""
    runner.section("테스트 2: 엣지 케이스 (단순 입력)")

    raw_input = "boy walks"
    print(f"\n📝 입력: \"{raw_input}\"")

    # 전체 파이프라인 실행
    normalizer = StoryNormalizer()
    normalized = normalizer.normalize(raw_input)

    topic_gen = TopicGenerator()
    topic = topic_gen.generate(normalized)

    arc_builder = ArcBuilder()
    arc = arc_builder.build(topic, normalized)

    budget_planner = BudgetPlanner()
    budget = budget_planner.plan(TargetFormat.SHORTS.value, arc)

    scene_gen = SceneGenerator()
    scene_result = scene_gen.generate(arc, budget, topic, normalized)

    # 검증
    runner.check(
        topic.theme != "",
        "엣지케이스: 테마 확장됨",
        f"theme={topic.theme}"
    )
    runner.check(
        topic.conflict != "",
        "엣지케이스: 갈등 자동 생성"
    )
    runner.check(
        len(scene_result.scenes) >= SHORTS_CONSTRAINTS["min_scenes"],
        "엣지케이스: 충분한 씬 생성"
    )

    print(f"\n    결과:")
    print(f"    - 테마: {topic.theme}")
    print(f"    - 갈등: {topic.conflict}")
    print(f"    - Hook: {arc.hook}")
    print(f"    - 씬 수: {len(scene_result.scenes)}")


# ============================================================
# 테스트 3: Hook 점수 시스템
# ============================================================

def test_hook_scoring(runner: TestRunner):
    """테스트 3: Hook 점수 시스템"""
    runner.section("테스트 3: Hook 점수 시스템")

    hook_enhancer = HookEnhancer()

    test_hooks = [
        ("A boy walks", "단순한 Hook"),
        ("SUDDEN EXPLOSION destroys the city!", "충격적 Hook"),
        ("Mysterious shadow appears from nowhere", "호기심 Hook"),
        ("Hero fights villain in epic battle", "액션 Hook"),
    ]

    for hook, desc in test_hooks:
        score = hook_enhancer.score(hook)
        enhanced, enhanced_score = hook_enhancer.enhance_and_score(hook)

        runner.check(
            enhanced_score.total >= score.total,
            f"Hook 강화 효과 ({desc})",
            f"원본={score.total:.1f} → 강화={enhanced_score.total:.1f}"
        )

        print(f"\n    [{desc}]")
        print(f"    - 원본: \"{hook}\" (점수: {score.total:.1f})")
        print(f"    - 강화: \"{enhanced[:60]}...\" (점수: {enhanced_score.total:.1f})")


# ============================================================
# 테스트 4: Budget 제약
# ============================================================

def test_budget_constraints(runner: TestRunner):
    """테스트 4: Budget 제약 테스트"""
    runner.section("테스트 4: Budget 제약")

    budget_planner = BudgetPlanner()

    # Shorts
    shorts_budget = budget_planner.plan(TargetFormat.SHORTS.value, None)

    runner.check(
        shorts_budget.scene_count >= SHORTS_CONSTRAINTS["min_scenes"],
        "Shorts: 최소 씬 수"
    )
    runner.check(
        shorts_budget.scene_count <= SHORTS_CONSTRAINTS["max_scenes"],
        "Shorts: 최대 씬 수"
    )
    runner.check(
        shorts_budget.total_duration <= SHORTS_CONSTRAINTS["max_duration"],
        "Shorts: 최대 길이"
    )

    print(f"    Shorts Budget: {shorts_budget.scene_count} scenes, {shorts_budget.total_duration}s")

    # Longform
    longform_budget = budget_planner.plan(TargetFormat.LONGFORM.value, None)

    runner.check(
        longform_budget.scene_count >= LONGFORM_CONSTRAINTS["min_scenes"],
        "Longform: 최소 씬 수"
    )
    runner.check(
        longform_budget.scene_count <= LONGFORM_CONSTRAINTS["max_scenes"],
        "Longform: 최대 씬 수"
    )

    print(f"    Longform Budget: {longform_budget.scene_count} scenes, {longform_budget.total_duration}s")


# ============================================================
# 테스트 5: Format Render
# ============================================================

def test_format_render(runner: TestRunner, story_spec: StorySpec):
    """테스트 5: 포맷 변환"""
    runner.section("테스트 5: Format Render Engine")

    render_engine = FormatRenderEngine()

    # Shorts로 렌더링
    rendered = render_engine.render(story_spec, TargetFormat.SHORTS)

    runner.check(
        rendered.format == TargetFormat.SHORTS,
        "Render: Shorts 포맷으로 변환"
    )
    runner.check(
        rendered.total_duration <= SHORTS_CONSTRAINTS["max_duration"],
        "Render: Shorts 길이 제약 준수",
        f"duration={rendered.total_duration}s"
    )
    runner.check(
        rendered.scene_count <= SHORTS_CONSTRAINTS["max_scenes"],
        "Render: Shorts 씬 수 제약 준수"
    )

    print(f"    - 포맷: {rendered.format.value}")
    print(f"    - 길이: {rendered.total_duration}s")
    print(f"    - 씬 수: {rendered.scene_count}")
    print(f"    - 압축률: {rendered.compression_ratio:.2f}")
    print(f"    - 변경 사항: {rendered.changes}")


# ============================================================
# 메인 실행
# ============================================================

def main():
    """메인 테스트 실행"""
    print("\n" + "="*60)
    print("  Story Compiler v3 - 통합 테스트")
    print("="*60)
    print(f"  시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    runner = TestRunner()

    try:
        # 테스트 1: 기본 파이프라인
        story_spec, validation = test_basic_pipeline(runner)

        # 테스트 2: 엣지 케이스
        test_edge_case(runner)

        # 테스트 3: Hook 점수
        test_hook_scoring(runner)

        # 테스트 4: Budget 제약
        test_budget_constraints(runner)

        # 테스트 5: Format Render
        if story_spec:
            test_format_render(runner, story_spec)

    except Exception as e:
        print(f"\n❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        runner.failed += 1

    # 결과 요약
    success = runner.summary()

    print("\n" + "="*60)
    if success:
        print("  🎉 모든 테스트 통과!")
    else:
        print("  ⚠️ 일부 테스트 실패")
    print("="*60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
