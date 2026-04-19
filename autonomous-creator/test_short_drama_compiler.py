"""
숏 드라마 컴파일러 + 스토리 컴포넌트 DB 통합 테스트

테스트 항목:
1. 시드 데이터 / 축 구조 테스트 (5개 축, 개수, 중복, 그룹핑)
2. DB 테스트 (StoryComponentDB - 인메모리)
3. 논리 규칙 테스트 (TRIGGER_SECRET_COMPATIBILITY, TWIST_SECRET_COMPATIBILITY)
4. Import 테스트 (ShortDramaCompiler, 상수)
5. 카테고리 시스템 테스트
6. SHORT_DRAMA_CONSTRAINTS 테스트
7. TargetFormat 테스트
8. 컴파일러 테스트 (LLM 없이, DB 주입)
9. 조합 수 계산
"""

import sys
import os
import random
import sqlite3
from typing import Dict, List, Any, Optional, Tuple
from collections import Counter
from itertools import product

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ============================================================
# 테스트 유틸
# ============================================================

passed = 0
failed = 0
errors_list = []


def report(name: str, condition: bool, detail: str = ""):
    """PASS/FAIL 리포트 출력"""
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        msg = f"  [FAIL] {name}"
        if detail:
            msg += f" - {detail}"
        print(msg)
        errors_list.append(msg)


# ============================================================
# 1. 시드 데이터 / 축 구조 테스트
# ============================================================

print("\n=== 1. 시드 데이터 / 축 구조 테스트 ===")

SEED_CATEGORIES = None
SEED_RELATIONSHIPS = None
SEED_SECRETS = None
SEED_TRIGGERS = None
SEED_TWISTS = None

try:
    from infrastructure.db.seed_data import (
        SEED_CATEGORIES, SEED_RELATIONSHIPS, SEED_SECRETS,
        SEED_TRIGGERS, SEED_TWISTS,
    )
    report("seed_data 모듈 import", True)
except ImportError as e:
    report("seed_data 모듈 import", False, str(e))

if SEED_CATEGORIES is not None:
    # 1-1. Category: 5개
    report("Category 5개", len(SEED_CATEGORIES) == 5,
           f"실제: {len(SEED_CATEGORIES)}개 - {SEED_CATEGORIES}")

    # 1-2. Relationship: 20개 (value, category_group 튜플)
    report("Relationship 20개", len(SEED_RELATIONSHIPS) == 20,
           f"실제: {len(SEED_RELATIONSHIPS)}개")

    # 1-3. Relationship의 category_group이 SEED_CATEGORIES에 속하는지
    rel_categories = set(rg for _, rg in SEED_RELATIONSHIPS)
    all_in_categories = rel_categories.issubset(set(SEED_CATEGORIES))
    report("Relationship 카테고리 그룹핑 유효", all_in_categories,
           f"미포함 카테고리: {rel_categories - set(SEED_CATEGORIES)}")

    # 1-4. 카테고리당 4개 Relationship
    cat_counts = Counter(rg for _, rg in SEED_RELATIONSHIPS)
    all_four = all(c == 4 for c in cat_counts.values())
    report("카테고리당 4개 Relationship", all_four,
           f"분포: {dict(cat_counts)}")

    # 1-5. Secret: 12개
    report("Secret Type 12개", len(SEED_SECRETS) == 12,
           f"실제: {len(SEED_SECRETS)}개 - {SEED_SECRETS}")

    # 1-6. Trigger: 12개
    report("Event Trigger 12개", len(SEED_TRIGGERS) == 12,
           f"실제: {len(SEED_TRIGGERS)}개 - {SEED_TRIGGERS}")

    # 1-7. Twist: 10개
    report("Twist Pattern 10개", len(SEED_TWISTS) == 10,
           f"실제: {len(SEED_TWISTS)}개 - {SEED_TWISTS}")

    # 1-8. 5개 축 모두 존재
    all_axes = all([
        SEED_CATEGORIES, SEED_RELATIONSHIPS,
        SEED_SECRETS, SEED_TRIGGERS, SEED_TWISTS,
    ])
    report("5개 축 데이터 모두 존재", all_axes)

    # 1-9. 중복 값 없음 확인
    rel_values = [v for v, _ in SEED_RELATIONSHIPS]
    report("Relationship 값 중복 없음", len(rel_values) == len(set(rel_values)),
           f"중복: {[v for v, c in Counter(rel_values).items() if c > 1]}")
    report("Secret 값 중복 없음", len(SEED_SECRETS) == len(set(SEED_SECRETS)))
    report("Trigger 값 중복 없음", len(SEED_TRIGGERS) == len(set(SEED_TRIGGERS)))
    report("Twist 값 중복 없음", len(SEED_TWISTS) == len(set(SEED_TWISTS)))
else:
    print("  [SKIP] seed_data를 import할 수 없어 축 구조 테스트 스킵")


# ============================================================
# 2. DB 테스트 (StoryComponentDB - 인메모리)
# ============================================================

print("\n=== 2. DB 테스트 (StoryComponentDB) ===")

StoryComponentDB = None
try:
    from infrastructure.db.story_db import StoryComponentDB
    report("StoryComponentDB import", True)
except ImportError as e:
    report("StoryComponentDB import", False, str(e))
    print("  -> story_db.py가 아직 없음. 이후 DB 테스트는 스킵합니다.")

if StoryComponentDB is not None:
    # 2-1. 인메모리 DB 생성 (:memory:)
    db = None
    try:
        db = StoryComponentDB(db_path=":memory:")
        report("인메모리 DB 생성 (:memory:)", True)
    except Exception as e:
        report("인메모리 DB 생성 (:memory:)", False, str(e))

    if db is not None:
        # 2-2. 컴포넌트 추가 (모든 축 필수: 조합 생성 시 5개 축 모두 필요)
        try:
            db.add_component("category", "연애 배신")
            db.add_component("category", "가족 갈등")
            db.add_component("relationship", "연인", category_group="연애 배신")
            db.add_component("relationship", "모녀", category_group="가족 갈등")
            db.add_component("secret", "바람")
            db.add_component("secret", "거짓말")
            db.add_component("trigger", "문자 발견")
            db.add_component("trigger", "술자리")
            db.add_component("twist", "사실 알고 있었다")
            db.add_component("twist", "오해였다")
            report("컴포넌트 추가 (10개, 5축)", True)
        except Exception as e:
            report("컴포넌트 추가", False, str(e))

        # 2-3. 컴포넌트 조회
        try:
            cats = db.get_components("category")
            rels = db.get_components("relationship")
            secrets = db.get_components("secret")
            report("category 조회 2개", len(cats) == 2,
                   f"실제: {len(cats)}개 - {cats}")
            report("relationship 조회 2개", len(rels) == 2,
                   f"실제: {len(rels)}개 - {rels}")
            report("secret 조회 2개", len(secrets) == 2,
                   f"실제: {len(secrets)}개 - {secrets}")
        except Exception as e:
            report("컴포넌트 조회", False, str(e))

        # 2-4. 가중치 선택 (weighted_select) - {id, value, weight} dict 반환
        try:
            selected = db.weighted_select("category")
            report("weighted_select category dict 반환",
                   isinstance(selected, dict) and "value" in selected,
                   f"반환값: {selected}")
            # weighted_select는 {id, value, weight} dict 반환
            selected_value = selected.get("value", "") if isinstance(selected, dict) else ""
            report("weighted_select 결과가 등록된 값",
                   selected_value in ["연애 배신", "가족 갈등"],
                   f"선택된 값: {selected_value}")
        except Exception as e:
            report("weighted_select", False, str(e))

        # 2-5. 조합 생성 + 중복 방지
        try:
            combo = db.generate_combination()
            report("조합 생성 (dict 반환)", isinstance(combo, dict),
                   f"타입: {type(combo).__name__}")
            if isinstance(combo, dict):
                expected_keys = {"category", "relationship", "secret", "trigger", "twist"}
                has_required = expected_keys.issubset(set(combo.keys()))
                report("조합에 필수 키 존재", has_required,
                       f"키: {list(combo.keys())}")
        except Exception as e:
            report("조합 생성", False, str(e))

        # 2-6. 동일 조합 재생성 시도 (중복 방지 확인)
        try:
            combo2 = db.generate_combination()
            # 가중치가 같으므로 랜덤이지만, 기본적으로는 다른 조합이 나올 가능성이 높음
            report("두 번째 조합 생성 성공", combo2 is not None and len(combo2) > 0)
        except Exception as e:
            report("두 번째 조합 생성", False, str(e))

        # 2-7. 성과 기록 + 가중치 업데이트
        try:
            # 조합을 먼저 저장해 combination_id 획득
            combo_to_save = db.generate_combination()
            if combo_to_save and "hash" in combo_to_save:
                combo_id = db.save_combination(combo_to_save, story_title="테스트 스토리")
                report("조합 저장 (save_combination)", combo_id > 0,
                       f"combination_id: {combo_id}")

                # record_performance(combination_id, views, watch_time, retention, ctr)
                # score = retention*0.4 + ctr*0.3 + watch_time_norm*0.3
                # score > 0.7 이어야 weight 증가
                # 0.95*0.4 + 0.9*0.3 + min(55/60,1)*0.3 = 0.38+0.27+0.275 = 0.925
                db.record_performance(
                    combination_id=combo_id,
                    views=10000,
                    watch_time=55.0,
                    retention=0.95,
                    ctr=0.9,
                )
                report("성과 기록 (record_performance)", True)

                # 가중치 업데이트 확인 (score > 0.7이므로 weight 증가)
                updated_cats = db.get_components("category")
                weight_increased = any(c["weight"] > 1.0 for c in updated_cats)
                report("성과 기반 가중치 업데이트 확인",
                       weight_increased,
                       f"category 가중치: {[(c['value'], c['weight']) for c in updated_cats]}")
            else:
                report("성과 기록 - 조합 생성 실패로 스킵", False,
                       "조합을 생성할 수 없음")
        except Exception as e:
            report("성과 기록 / 가중치 업데이트", False, str(e))

        # 2-8. 시드 데이터로 DB 초기화 테스트
        try:
            if SEED_CATEGORIES is not None:
                seed_db = StoryComponentDB(db_path=":memory:")
                # 시드 데이터 삽입 (add_component의 category_group 파라미터 사용)
                for cat in SEED_CATEGORIES:
                    seed_db.add_component("category", cat)
                for val, grp in SEED_RELATIONSHIPS:
                    seed_db.add_component("relationship", val,
                                          category_group=grp)
                for s in SEED_SECRETS:
                    seed_db.add_component("secret", s)
                for t in SEED_TRIGGERS:
                    seed_db.add_component("trigger", t)
                for tw in SEED_TWISTS:
                    seed_db.add_component("twist", tw)

                cats = seed_db.get_components("category")
                rels = seed_db.get_components("relationship")
                secrets = seed_db.get_components("secret")
                triggers = seed_db.get_components("trigger")
                twists = seed_db.get_components("twist")

                report("시드 DB: category 5개", len(cats) == 5,
                       f"실제: {len(cats)}개")
                report("시드 DB: relationship 20개", len(rels) == 20,
                       f"실제: {len(rels)}개")
                report("시드 DB: secret 12개", len(secrets) == 12,
                       f"실제: {len(secrets)}개")
                report("시드 DB: trigger 12개", len(triggers) == 12,
                       f"실제: {len(triggers)}개")
                report("시드 DB: twist 10개", len(twists) == 10,
                       f"실제: {len(twists)}개")
        except Exception as e:
            report("시드 데이터 DB 초기화", False, str(e))
else:
    print("  [SKIP] StoryComponentDB를 import할 수 없어 DB 테스트 스킵")
    print("  -> infrastructure/db/story_db.py 생성 후 재실행하세요.")


# ============================================================
# 3. 논리 규칙 테스트
# ============================================================

print("\n=== 3. 논리 규칙 테스트 ===")

TRIGGER_SECRET_COMPAT = None
TWIST_SECRET_COMPAT = None

try:
    from infrastructure.story.short_drama_compiler import TRIGGER_SECRET_COMPATIBILITY
    TRIGGER_SECRET_COMPAT = TRIGGER_SECRET_COMPATIBILITY
    report("TRIGGER_SECRET_COMPATIBILITY import", True)
except ImportError:
    try:
        from infrastructure.db.story_db import TRIGGER_SECRET_COMPATIBILITY
        TRIGGER_SECRET_COMPAT = TRIGGER_SECRET_COMPATIBILITY
        report("TRIGGER_SECRET_COMPATIBILITY import (story_db)", True)
    except (ImportError, AttributeError):
        report("TRIGGER_SECRET_COMPATIBILITY import", False,
               "short_drama_compiler.py 또는 story_db.py에 정의되지 않음")

try:
    from infrastructure.story.short_drama_compiler import TWIST_SECRET_COMPATIBILITY
    TWIST_SECRET_COMPAT = TWIST_SECRET_COMPATIBILITY
    report("TWIST_SECRET_COMPATIBILITY import", True)
except ImportError:
    try:
        from infrastructure.db.story_db import TWIST_SECRET_COMPATIBILITY
        TWIST_SECRET_COMPAT = TWIST_SECRET_COMPATIBILITY
        report("TWIST_SECRET_COMPATIBILITY import (story_db)", True)
    except (ImportError, AttributeError):
        report("TWIST_SECRET_COMPATIBILITY import", False,
               "short_drama_compiler.py 또는 story_db.py에 정의되지 않음")

# 호환성 매핑이 있으면 검증
if TRIGGER_SECRET_COMPAT is not None:
    try:
        report("TRIGGER_SECRET_COMPATIBILITY dict 타입",
               isinstance(TRIGGER_SECRET_COMPAT, dict),
               f"타입: {type(TRIGGER_SECRET_COMPAT).__name__}")
        if isinstance(TRIGGER_SECRET_COMPAT, dict):
            # 키가 secret 이름이고 값이 호환되는 trigger 리스트인지 확인
            sample_key = next(iter(TRIGGER_SECRET_COMPAT))
            sample_val = TRIGGER_SECRET_COMPAT[sample_key]
            report("SECRET→TRIGGER 매핑 구조 (list 값)",
                   isinstance(sample_val, list),
                   f"샘플: {sample_key} -> {sample_val}")
            # 모든 값이 리스트인지 확인
            all_lists = all(isinstance(v, list) for v in TRIGGER_SECRET_COMPAT.values())
            report("모든 SECRET→TRIGGER 매핑 값이 list", all_lists)
    except Exception as e:
        report("TRIGGER_SECRET_COMPATIBILITY 검증", False, str(e))

if TWIST_SECRET_COMPAT is not None:
    try:
        report("TWIST_SECRET_COMPATIBILITY dict 타입",
               isinstance(TWIST_SECRET_COMPAT, dict),
               f"타입: {type(TWIST_SECRET_COMPAT).__name__}")
        if isinstance(TWIST_SECRET_COMPAT, dict):
            sample_key = next(iter(TWIST_SECRET_COMPAT))
            sample_val = TWIST_SECRET_COMPAT[sample_key]
            report("SECRET→TWIST 매핑 구조 (list 값)",
                   isinstance(sample_val, list),
                   f"샘플: {sample_key} -> {sample_val}")
            # 모든 값이 리스트인지 확인
            all_lists = all(isinstance(v, list) for v in TWIST_SECRET_COMPAT.values())
            report("모든 SECRET→TWIST 매핑 값이 list", all_lists)
    except Exception as e:
        report("TWIST_SECRET_COMPATIBILITY 검증", False, str(e))


# ============================================================
# 4. Import 테스트
# ============================================================

print("\n=== 4. Import 테스트 ===")

# ShortDramaCompiler import 시도
ShortDramaCompiler = None
try:
    from infrastructure.story.short_drama_compiler import ShortDramaCompiler
    report("ShortDramaCompiler import", True)
except ImportError as e:
    report("ShortDramaCompiler import", False, str(e))
    print("  -> short_drama_compiler.py가 아직 없음. 이후 컴파일러 테스트는 스킵합니다.")

# 축 상수 import 시도
CATEGORIES = None
RELATIONSHIPS = None
SECRET_TYPES = None
EVENT_TRIGGERS = None
TWIST_PATTERNS = None

try:
    from infrastructure.story.short_drama_compiler import (
        CATEGORIES, RELATIONSHIPS, SECRET_TYPES,
        EVENT_TRIGGERS, TWIST_PATTERNS,
    )
    report("축 상수 import (CATEGORIES, RELATIONSHIPS, SECRET_TYPES, EVENT_TRIGGERS, TWIST_PATTERNS)", True)
except ImportError as e:
    report("축 상수 import", False, str(e))

# DRAMA_CATEGORIES는 레거시 호환성 확인
DRAMA_CATEGORIES = None
try:
    from infrastructure.story.short_drama_compiler import DRAMA_CATEGORIES
    report("DRAMA_CATEGORIES import (레거시)", True)
except ImportError:
    report("DRAMA_CATEGORIES 없음 (v2 구조에서는 정상)", True)


# ============================================================
# 5. 카테고리 시스템 테스트
# ============================================================

print("\n=== 5. 카테고리 시스템 테스트 ===")

# CATEGORIES (리스트) 또는 DRAMA_CATEGORIES (dict) 사용
test_categories = CATEGORIES or (list(DRAMA_CATEGORIES.keys()) if DRAMA_CATEGORIES else None)

if test_categories is not None:
    # 5-1. 카테고리 5개
    try:
        report("카테고리 5개", len(test_categories) == 5,
               f"실제: {len(test_categories)}개 - {test_categories}")
    except Exception as e:
        report("카테고리 개수 확인", False, str(e))

    # 5-2. CATEGORIES 리스트인 경우
    if CATEGORIES is not None:
        report("CATEGORIES 리스트 타입", isinstance(CATEGORIES, list),
               f"타입: {type(CATEGORIES).__name__}")

    # 5-3. RELATIONSHIPS (tuple 리스트)
    if RELATIONSHIPS is not None:
        report("RELATIONSHIPS 리스트 타입", isinstance(RELATIONSHIPS, list),
               f"타입: {type(RELATIONSHIPS).__name__}")
        report("RELATIONSHIPS 20개", len(RELATIONSHIPS) == 20,
               f"실제: {len(RELATIONSHIPS)}개")
        # 각 항목이 (value, group) 튜플인지 확인
        all_tuples = all(isinstance(r, tuple) and len(r) == 2 for r in RELATIONSHIPS)
        report("RELATIONSHIPS 항목이 (value, group) 튜플", all_tuples)

    # 5-4. SECRET_TYPES 리스트
    if SECRET_TYPES is not None:
        report("SECRET_TYPES 12개", len(SECRET_TYPES) == 12,
               f"실제: {len(SECRET_TYPES)}개")

    # 5-5. EVENT_TRIGGERS 리스트
    if EVENT_TRIGGERS is not None:
        report("EVENT_TRIGGERS 12개", len(EVENT_TRIGGERS) == 12,
               f"실제: {len(EVENT_TRIGGERS)}개")

    # 5-6. TWIST_PATTERNS 리스트
    if TWIST_PATTERNS is not None:
        report("TWIST_PATTERNS 10개", len(TWIST_PATTERNS) == 10,
               f"실제: {len(TWIST_PATTERNS)}개")
else:
    print("  [SKIP] 카테고리 데이터를 import할 수 없어 스킵")


# ============================================================
# 6. SHORT_DRAMA_CONSTRAINTS 테스트
# ============================================================

print("\n=== 6. SHORT_DRAMA_CONSTRAINTS 테스트 ===")

try:
    from infrastructure.story.story_spec import SHORT_DRAMA_CONSTRAINTS

    report("SHORT_DRAMA_CONSTRAINTS import", True)
    report("min_duration == 45",
           SHORT_DRAMA_CONSTRAINTS["min_duration"] == 45,
           f"실제: {SHORT_DRAMA_CONSTRAINTS.get('min_duration')}")
    report("max_duration == None (무제한)",
           SHORT_DRAMA_CONSTRAINTS["max_duration"] is None,
           f"실제: {SHORT_DRAMA_CONSTRAINTS.get('max_duration')}")
    report("min_scenes == 5",
           SHORT_DRAMA_CONSTRAINTS["min_scenes"] == 5,
           f"실제: {SHORT_DRAMA_CONSTRAINTS.get('min_scenes')}")
    report("scene_duration_range 존재",
           "scene_duration_range" in SHORT_DRAMA_CONSTRAINTS,
           f"실제: {SHORT_DRAMA_CONSTRAINTS.get('scene_duration_range')}")
except ImportError as e:
    report("SHORT_DRAMA_CONSTRAINTS import", False, str(e))


# ============================================================
# 7. TargetFormat 테스트
# ============================================================

print("\n=== 7. TargetFormat 테스트 ===")

try:
    from infrastructure.story.story_spec import TargetFormat

    report("TargetFormat import", True)
    report("TargetFormat.SHORT_DRAMA 존재",
           hasattr(TargetFormat, "SHORT_DRAMA"),
           "SHORT_DRAMA 속성 없음")
    report("TargetFormat.SHORT_DRAMA 값 == 'short_drama'",
           TargetFormat.SHORT_DRAMA.value == "short_drama",
           f"실제: {TargetFormat.SHORT_DRAMA.value if hasattr(TargetFormat, 'SHORT_DRAMA') else 'N/A'}")
except ImportError as e:
    report("TargetFormat import", False, str(e))


# ============================================================
# 8. 컴파일러 테스트 (LLM 없이)
# ============================================================

print("\n=== 8. 컴파일러 테스트 (LLM 없이) ===")

compiler = None
if ShortDramaCompiler is not None:
    # 인메모리 DB 주입 테스트
    try:
        # db 파라미터 지원 여부 확인
        import inspect
        init_params = inspect.signature(ShortDramaCompiler.__init__).parameters

        if "db" in init_params and StoryComponentDB is not None:
            # StoryComponentDB 인메모리 DB 생성 및 시드 데이터 삽입
            in_memory_db = StoryComponentDB(db_path=":memory:")
            if SEED_CATEGORIES is not None:
                for cat in SEED_CATEGORIES:
                    in_memory_db.add_component("category", cat)
                for val, grp in SEED_RELATIONSHIPS:
                    in_memory_db.add_component("relationship", val, category_group=grp)
                for s in SEED_SECRETS:
                    in_memory_db.add_component("secret", s)
                for t in SEED_TRIGGERS:
                    in_memory_db.add_component("trigger", t)
                for tw in SEED_TWISTS:
                    in_memory_db.add_component("twist", tw)
            compiler = ShortDramaCompiler(llm_provider=None, db=in_memory_db)
            report("ShortDramaCompiler(db=인메모리DB) 생성", True)
        else:
            # db 파라미터가 없거나 StoryComponentDB 없으면 기본 생성
            compiler = ShortDramaCompiler(llm_provider=None)
            report("ShortDramaCompiler(llm_provider=None) 생성 (폴백)", True)
    except TypeError as e:
        # db 파라미터가 없으면 llm_provider만으로 재시도
        try:
            compiler = ShortDramaCompiler(llm_provider=None)
            report("ShortDramaCompiler(llm_provider=None) 생성 (db 없이)", True)
        except Exception as e2:
            report("ShortDramaCompiler 생성", False, str(e2))
    except Exception as e:
        report("ShortDramaCompiler 생성", False, str(e))

    if compiler is not None:
        # 8-1. _pick_category() 카테고리 선택 -> 문자열 반환
        try:
            random.seed(42)
            result = compiler._pick_category()
            report("_pick_category() 문자열 반환",
                   isinstance(result, str) and len(result) > 0,
                   f"반환값: {result}")
            if isinstance(result, str):
                report("_pick_category() 결과가 유효한 카테고리",
                       result in (CATEGORIES or test_categories or []),
                       f"선택된 카테고리: {result}")
        except Exception as e:
            report("_pick_category()", False, str(e))

        # 8-2. _generate_formula() 조합 생성
        try:
            random.seed(42)
            formula = compiler._generate_formula()
            is_dict = isinstance(formula, dict)
            report("_generate_formula() dict 반환", is_dict,
                   f"타입: {type(formula).__name__}")

            if is_dict:
                required_keys = ["category", "relation", "secret", "conflict_event", "twist"]
                for key in required_keys:
                    has_key = key in formula
                    report(f"_generate_formula() '{key}' 키 존재", has_key,
                           f"키 목록: {list(formula.keys())}")

                # 조합 내용이 실제 데이터에 있는지 확인
                if "category" in formula and CATEGORIES:
                    report("formula category가 CATEGORIES에 존재",
                           formula["category"] in CATEGORIES,
                           f"값: {formula['category']}")
                if "secret" in formula and SECRET_TYPES:
                    report("formula secret가 SECRET_TYPES에 존재",
                           formula["secret"] in SECRET_TYPES,
                           f"값: {formula['secret']}")
                if "conflict_event" in formula and EVENT_TRIGGERS:
                    report("formula trigger가 EVENT_TRIGGERS에 존재",
                           formula["conflict_event"] in EVENT_TRIGGERS,
                           f"값: {formula['conflict_event']}")
                if "twist" in formula and TWIST_PATTERNS:
                    report("formula twist가 TWIST_PATTERNS에 존재",
                           formula["twist"] in TWIST_PATTERNS,
                           f"값: {formula['twist']}")
        except Exception as e:
            report("_generate_formula() 조합 생성", False, str(e))

        # 8-3. _build_prompt() 프롬프트 생성
        try:
            prompt = compiler._build_prompt(
                category_key="연애 배신",
                formula={"relation": "연인", "secret": "바람",
                         "conflict_event": "문자 발견", "twist": "사실 알고 있었다"},
                tone="현실적"
            )
            report("_build_prompt() 프롬프트 생성",
                   isinstance(prompt, str) and len(prompt) > 0,
                   f"길이: {len(prompt) if isinstance(prompt, str) else 'N/A'}")
        except Exception as e:
            report("_build_prompt() 프롬프트 생성", False, str(e))

        # 8-4. list_categories() 동작
        try:
            cat_list = compiler.list_categories()
            report("list_categories() 5개 반환",
                   isinstance(cat_list, list) and len(cat_list) == 5,
                   f"실제: {cat_list}")
        except Exception as e:
            report("list_categories()", False, str(e))

        # 8-5. list_relationships() 동작
        try:
            all_rels = compiler.list_relationships()
            report("list_relationships() 전체 20개",
                   isinstance(all_rels, list) and len(all_rels) == 20,
                   f"실제: {len(all_rels)}개")
            # 카테고리 필터링
            love_rels = compiler.list_relationships(category="연애 배신")
            report("list_relationships('연애 배신') 4개",
                   isinstance(love_rels, list) and len(love_rels) == 4,
                   f"실제: {len(love_rels)}개")
        except Exception as e:
            report("list_relationships()", False, str(e))

        # 8-6. list_secret_types() 동작
        try:
            secrets_list = compiler.list_secret_types()
            report("list_secret_types() 12개",
                   isinstance(secrets_list, list) and len(secrets_list) == 12,
                   f"실제: {len(secrets_list)}개")
        except Exception as e:
            report("list_secret_types()", False, str(e))

        # 8-7. list_triggers() 동작
        try:
            all_triggers = compiler.list_triggers()
            report("list_triggers() 전체 12개",
                   isinstance(all_triggers, list) and len(all_triggers) == 12,
                   f"실제: {len(all_triggers)}개")
            # secret 필터링
            wind_triggers = compiler.list_triggers(secret="바람")
            report("list_triggers('바름') 호환 트리거",
                   isinstance(wind_triggers, list) and len(wind_triggers) > 0,
                   f"실제: {wind_triggers}")
        except Exception as e:
            report("list_triggers()", False, str(e))

        # 8-8. list_twists() 동작
        try:
            all_twists = compiler.list_twists()
            report("list_twists() 전체 10개",
                   isinstance(all_twists, list) and len(all_twists) == 10,
                   f"실제: {len(all_twists)}개")
            # secret 필터링
            wind_twists = compiler.list_twists(secret="바람")
            report("list_twists('바름') 호환 트위스트",
                   isinstance(wind_twists, list) and len(wind_twists) > 0,
                   f"실제: {wind_twists}")
        except Exception as e:
            report("list_twists()", False, str(e))

        # 8-9. _generate_formula()가 호환 가능한 조합만 생성하는지 (100회 반복)
        if TRIGGER_SECRET_COMPAT is not None and TWIST_SECRET_COMPAT is not None:
            try:
                random.seed(42)
                all_compatible = True
                incompatible_examples = []
                for i in range(100):
                    f = compiler._generate_formula()
                    if not f:
                        continue
                    secret = f.get("secret", "")
                    trigger = f.get("conflict_event", "")
                    twist = f.get("twist", "")

                    # TRIGGER_SECRET_COMPATIBILITY 검증
                    compat_triggers = TRIGGER_SECRET_COMPAT.get(secret, [])
                    if compat_triggers and trigger not in compat_triggers:
                        all_compatible = False
                        incompatible_examples.append(
                            f"[{i}] secret={secret}, trigger={trigger} "
                            f"(expected: {compat_triggers})"
                        )

                    # TWIST_SECRET_COMPATIBILITY 검증
                    compat_twists = TWIST_SECRET_COMPAT.get(secret, [])
                    if compat_twists and twist not in compat_twists:
                        all_compatible = False
                        incompatible_examples.append(
                            f"[{i}] secret={secret}, twist={twist} "
                            f"(expected: {compat_twists})"
                        )

                report("_generate_formula() 호환 조합만 생성 (100회)",
                       all_compatible,
                       f"비호환 {len(incompatible_examples)}건: "
                       f"{incompatible_examples[:3]}")
            except Exception as e:
                report("_generate_formula() 호환성 검증", False, str(e))

        # 8-10. 조합 중복 방지 (해시 기반)
        try:
            random.seed(42)
            hashes = set()
            unique_count = 0
            for i in range(20):
                f = compiler._generate_formula()
                if f and "combo_hash" in f:
                    h = f["combo_hash"]
                    if h not in hashes:
                        hashes.add(h)
                        unique_count += 1
            # 20번 생성 중 최소 10개 이상이 고유해야 함
            report("조합 중복 방지 (20회 생성 시 고유 조합 >= 10)",
                   unique_count >= 10,
                   f"고유 조합: {unique_count}/20")
        except Exception as e:
            report("조합 중복 방지", False, str(e))
else:
    print("  [SKIP] ShortDramaCompiler를 import할 수 없어 스킵")
    print("  -> short_drama_compiler.py 생성 후 재실행하세요.")


# ============================================================
# 9. 조합 수 계산
# ============================================================

print("\n=== 9. 조합 수 계산 ===")

# seed_data 또는 컴파일러 상수 중 사용 가능한 것 사용
calc_categories = SEED_CATEGORIES or CATEGORIES
calc_rels = SEED_RELATIONSHIPS or (RELATIONSHIPS if RELATIONSHIPS else [])
calc_secrets = SEED_SECRETS or SECRET_TYPES or []
calc_triggers = SEED_TRIGGERS or EVENT_TRIGGERS or []
calc_twists = SEED_TWISTS or TWIST_PATTERNS or []

if calc_categories and calc_secrets and calc_triggers and calc_twists:
    # 9-1. 이론적 최대 조합 수 (모든 축의 곱)
    try:
        total_rels = len(calc_rels)
        total_secrets = len(calc_secrets)
        total_triggers = len(calc_triggers)
        total_twists = len(calc_twists)

        # 이론적 최대 (카테고리 고려 안함)
        theoretical_max = total_rels * total_secrets * total_triggers * total_twists

        # 카테고리 포함 (Category x 각 축의 곱)
        full_theoretical = len(calc_categories) * theoretical_max

        print(f"  이론적 최대 조합 (Category 제외): {theoretical_max:,}")
        print(f"    = {total_rels} (rels) x {total_secrets} (secrets) x {total_triggers} (triggers) x {total_twists} (twists)")
        print(f"  이론적 최대 조합 (Category 포함): {full_theoretical:,}")
        print(f"    = {len(calc_categories)} (cats) x {theoretical_max:,}")

        report("이론적 최대 조합 > 10,000",
               theoretical_max > 10000,
               f"실제: {theoretical_max:,}")

        report("이론적 최대 조합 (Category 포함) > 50,000",
               full_theoretical > 50000,
               f"실제: {full_theoretical:,}")
    except Exception as e:
        report("조합 수 계산", False, str(e))

    # 9-2. 호환성 규칙 적용 시 유효 조합 수 (실제)
    if TRIGGER_SECRET_COMPAT is not None and TWIST_SECRET_COMPAT is not None:
        try:
            # 각 secret에 대해 호환되는 trigger x twist 곱
            valid_combos = 0
            for secret, compat_triggers in TRIGGER_SECRET_COMPAT.items():
                compat_twists = TWIST_SECRET_COMPAT.get(secret, calc_twists)
                # 각 (trigger, twist) 조합에 대해 relationship 곱
                secret_combos = len(compat_triggers) * len(compat_twists)
                valid_combos += secret_combos

            # relationship 수 곱하기
            valid_with_rels = valid_combos * total_rels

            print(f"  호환성 적용 시 secret당 유효 조합: {valid_combos:,}")
            print(f"  호환성 적용 시 전체 유효 조합 (rel 포함): {valid_with_rels:,}")

            report("호환성 적용 유효 조합 > 0", valid_combos > 0,
                   f"실제: {valid_combos:,}")
            report("호환성 적용 유효 조합 < 이론적 최대",
                   valid_with_rels < theoretical_max,
                   f"유효: {valid_with_rels:,}, 이론: {theoretical_max:,}")
        except Exception as e:
            report("호환성 기반 유효 조합 계산", False, str(e))

    # 9-3. 중복 없이 생성 가능한 조합 수 (시드 데이터 기준)
    try:
        # 각 카테고리별 Relationship 수
        if isinstance(calc_rels[0], tuple):
            rels_per_cat = Counter(rg for _, rg in calc_rels)
        else:
            rels_per_cat = Counter()

        if rels_per_cat:
            # 카테고리별 조합 수 합계
            unique_combos = sum(
                count * total_secrets * total_triggers * total_twists
                for count in rels_per_cat.values()
            )
            print(f"  카테고리별 유효 조합 합계: {unique_combos:,}")
            print(f"    카테고리별 Relationship 분포: {dict(rels_per_cat)}")

            report("유효 조합 수 > 0", unique_combos > 0,
                   f"실제: {unique_combos:,}")
            report("유효 조합 수 >= 이론적 최대 (Category 제외)",
                   unique_combos == theoretical_max,
                   f"유효: {unique_combos:,}, 이론: {theoretical_max:,}")
    except Exception as e:
        report("유효 조합 수 계산", False, str(e))
else:
    print("  [SKIP] 축 데이터를 import할 수 없어 조합 수 계산 스킵")


# ============================================================
# 결과 요약
# ============================================================

print("\n" + "=" * 50)
print(f"테스트 결과: {passed} PASS / {failed} FAIL / {passed + failed} TOTAL")
if errors_list:
    print("\n실패 항목:")
    for e in errors_list:
        print(e)
print("=" * 50)

sys.exit(0 if failed == 0 else 1)
