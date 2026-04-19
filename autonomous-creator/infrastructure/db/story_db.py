"""
스토리 생성 제어 DB

단순 저장이 아니라 조합 생성, 품질 제어, 중복 방지를 수행하는 "두뇌 외부 기억장치".

역할:
    1. 조합 생성 (가중치 기반 선택)
    2. 품질 제어 (성과 기반 가중치 조정)
    3. 중복 방지 (해시 기반)
"""

import hashlib
import logging
import random
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class StoryComponentDB:
    """
    스토리 생성 제어 DB

    스토리 재료(component)를 관리하고, 가중치 기반으로 조합을 생성하며,
    성과 데이터를 바탕으로 가중치를 자동 조정한다.
    """

    def __init__(self, db_path: str = "data/story_components.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        logger.info("StoryComponentDB 초기화: %s", self.db_path)

    # ──── DB 연결 관리 ────

    def _get_conn(self) -> sqlite3.Connection:
        """DB 연결 (lazy init)"""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._init_tables()
            logger.debug("DB 연결 및 테이블 초기화 완료")
        return self._conn

    def _init_tables(self) -> None:
        """테이블 생성 (존재하지 않으면)"""
        conn = self._conn
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS story_components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                value TEXT NOT NULL,
                category_group TEXT DEFAULT '',
                weight REAL DEFAULT 1.0,
                usage_count INTEGER DEFAULT 0,
                success_score REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS story_combinations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                relationship TEXT NOT NULL,
                secret TEXT NOT NULL,
                trigger TEXT NOT NULL,
                twist TEXT NOT NULL,
                hash TEXT UNIQUE NOT NULL,
                story_title TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                combination_id INTEGER REFERENCES story_combinations(id),
                views INTEGER DEFAULT 0,
                watch_time REAL DEFAULT 0.0,
                retention REAL DEFAULT 0.0,
                ctr REAL DEFAULT 0.0,
                score REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 자주 조회되는 컬럼에 인덱스 생성
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_components_type "
            "ON story_components(type)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_components_type_group "
            "ON story_components(type, category_group)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_combinations_hash "
            "ON story_combinations(hash)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_performance_combination "
            "ON performance(combination_id)"
        )

        conn.commit()
        logger.debug("테이블 초기화 완료")

    # ──── Component 관리 ────

    def add_component(
        self,
        type: str,
        value: str,
        category_group: str = "",
        weight: float = 1.0,
    ) -> int:
        """
        컴포넌트 추가.

        Args:
            type: 컴포넌트 타입 (category / relationship / secret / trigger / twist)
            value: 컴포넌트 값
            category_group: relationship의 경우 소속 카테고리 (비어있으면 공통)
            weight: 선택 확률 가중치

        Returns:
            추가된 행의 id
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        weight = max(0.1, min(3.0, weight))
        cursor.execute(
            "INSERT INTO story_components (type, value, category_group, weight) "
            "VALUES (?, ?, ?, ?)",
            (type, value, category_group, weight),
        )
        conn.commit()
        row_id = cursor.lastrowid
        logger.debug("컴포넌트 추가: type=%s, value=%s, id=%d", type, value, row_id)
        return row_id

    def add_components_bulk(
        self,
        type: str,
        values: list,
        category_group: str = "",
    ) -> None:
        """컴포넌트 일괄 추가"""
        conn = self._get_conn()
        cursor = conn.cursor()
        rows = [(type, v, category_group, 1.0) for v in values]
        cursor.executemany(
            "INSERT INTO story_components (type, value, category_group, weight) "
            "VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        logger.info(
            "컴포넌트 일괄 추가: type=%s, count=%d, group=%s",
            type,
            len(values),
            category_group,
        )

    def get_components(
        self,
        type: str,
        category_group: Optional[str] = None,
    ) -> list[dict]:
        """
        타입별 컴포넌트 조회.

        Args:
            type: 컴포넌트 타입
            category_group: 필터링할 카테고리 그룹 (None이면 전체)

        Returns:
            컴포넌트 dict 리스트
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        if category_group is not None:
            cursor.execute(
                "SELECT * FROM story_components WHERE type = ? AND category_group = ?",
                (type, category_group),
            )
        else:
            cursor.execute(
                "SELECT * FROM story_components WHERE type = ?",
                (type,),
            )

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def weighted_select(
        self,
        type: str,
        category_group: Optional[str] = None,
    ) -> dict:
        """
        가중치 기반 랜덤 선택.

        weight가 높을수록 선택 확률이 증가한다.
        각 항목의 weight를 확률로 변환 후 랜덤 선택.

        Args:
            type: 컴포넌트 타입
            category_group: 필터링할 카테고리 그룹 (None이면 전체)

        Returns:
            선택된 컴포넌트 {id, value, weight}
            해당 타입에 컴포넌트가 없으면 빈 dict 반환
        """
        components = self.get_components(type, category_group)
        if not components:
            logger.warning("가중치 선택 실패: type=%s에 컴포넌트 없음", type)
            return {}

        weights = [c["weight"] for c in components]
        total = sum(weights)
        if total <= 0:
            # 모든 weight가 0 이하이면 균등 선택
            chosen = random.choice(components)
        else:
            chosen = random.choices(components, weights=weights, k=1)[0]

        return {
            "id": chosen["id"],
            "value": chosen["value"],
            "weight": chosen["weight"],
        }

    # ──── 조합 관리 ────

    def generate_combination(self, category: Optional[str] = None) -> dict:
        """
        가중치 기반 스토리 조합 생성.

        Args:
            category: 카테고리 (None이면 가중치 랜덤 선택)

        Returns:
            {category, relationship, secret, trigger, twist, hash}

        논리 규칙:
            - Rule 1: trigger는 secret과 논리적으로 연결 (같은 category_group 우선)
            - Rule 2: twist는 secret 기반으로만 생성
            - Rule 3: 중복 해시면 재생성 (최대 10회 시도)
        """
        for attempt in range(10):
            # 1. 카테고리 선택
            if category is None:
                cat_result = self.weighted_select("category")
                if not cat_result:
                    logger.error("카테고리 컴포넌트가 없어 조합 생성 불가")
                    return {}
                selected_category = cat_result["value"]
            else:
                selected_category = category

            # 2. 관계 선택 (같은 카테고리 그룹 우선)
            rel_result = self.weighted_select("relationship", selected_category)
            if not rel_result:
                # 해당 카테고리 그룹이 없으면 공통(빈 문자열)에서 선택
                rel_result = self.weighted_select("relationship", "")
            if not rel_result:
                rel_result = self.weighted_select("relationship")
            if not rel_result:
                logger.error("relationship 컴포넌트가 없어 조합 생성 불가")
                return {}

            # 3. 비밀 선택
            secret_result = self.weighted_select("secret")
            if not secret_result:
                logger.error("secret 컴포넌트가 없어 조합 생성 불가")
                return {}

            # 4. 트리거 선택 (Rule 1: secret과 같은 category_group 우선)
            # secret의 category_group을 확인하여 같은 그룹의 trigger 우선 선택
            secret_detail = self._get_component_by_id(secret_result["id"])
            secret_group = secret_detail.get("category_group", "") if secret_detail else ""

            trigger_result = self.weighted_select("trigger", secret_group) if secret_group else {}
            if not trigger_result:
                trigger_result = self.weighted_select("trigger")
            if not trigger_result:
                logger.error("trigger 컴포넌트가 없어 조합 생성 불가")
                return {}

            # 5. 트위스트 선택 (Rule 2: secret 기반 - 같은 category_group 우선)
            twist_result = self.weighted_select("twist", secret_group) if secret_group else {}
            if not twist_result:
                twist_result = self.weighted_select("twist")
            if not twist_result:
                logger.error("twist 컴포넌트가 없어 조합 생성 불가")
                return {}

            components = {
                "category": selected_category,
                "relationship": rel_result["value"],
                "secret": secret_result["value"],
                "trigger": trigger_result["value"],
                "twist": twist_result["value"],
            }

            # Rule 3: 중복 확인
            hash_value = self._compute_hash(components)
            components["hash"] = hash_value

            if not self.is_duplicate(hash_value):
                logger.info(
                    "조합 생성 성공 (시도 %d): %s",
                    attempt + 1,
                    selected_category,
                )
                return components

            logger.debug("중복 조합 감지, 재시도 (%d/10)", attempt + 1)

        logger.warning("10회 시도 후에도 고유 조합 생성 실패")
        return {}

    def _get_component_by_id(self, component_id: int) -> Optional[dict]:
        """ID로 컴포넌트 조회"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM story_components WHERE id = ?",
            (component_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def _compute_hash(self, components: dict) -> str:
        """조합 해시 생성 (MD5)"""
        key = (
            f"{components['category']}|{components['relationship']}|"
            f"{components['secret']}|{components['trigger']}|{components['twist']}"
        )
        return hashlib.md5(key.encode()).hexdigest()

    def is_duplicate(self, hash_value: str) -> bool:
        """중복 조합 확인"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM story_combinations WHERE hash = ?",
            (hash_value,),
        )
        return cursor.fetchone() is not None

    def save_combination(self, components: dict, story_title: str = "") -> int:
        """
        조합 기록 저장.

        Args:
            components: 조합 정보 (category, relationship, secret, trigger, twist, hash)
            story_title: 스토리 제목

        Returns:
            저장된 행의 id
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        hash_value = components.get("hash") or self._compute_hash(components)

        cursor.execute(
            "INSERT INTO story_combinations "
            "(category, relationship, secret, trigger, twist, hash, story_title) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                components["category"],
                components["relationship"],
                components["secret"],
                components["trigger"],
                components["twist"],
                hash_value,
                story_title,
            ),
        )

        # 각 컴포넌트의 사용 횟수 증가
        self._increment_usage(cursor, "category", components["category"])
        self._increment_usage(cursor, "relationship", components["relationship"])
        self._increment_usage(cursor, "secret", components["secret"])
        self._increment_usage(cursor, "trigger", components["trigger"])
        self._increment_usage(cursor, "twist", components["twist"])

        conn.commit()
        row_id = cursor.lastrowid
        logger.info("조합 저장: id=%d, title=%s", row_id, story_title)
        return row_id

    def _increment_usage(
        self,
        cursor: sqlite3.Cursor,
        type: str,
        value: str,
    ) -> None:
        """컴포넌트 사용 횟수 증가"""
        cursor.execute(
            "UPDATE story_components SET usage_count = usage_count + 1 "
            "WHERE type = ? AND value = ?",
            (type, value),
        )

    def get_recent_combinations(self, limit: int = 20) -> list[dict]:
        """최근 조합 목록"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM story_combinations ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    # ──── 성과 관리 ────

    def record_performance(
        self,
        combination_id: int,
        views: int,
        watch_time: float,
        retention: float,
        ctr: float,
    ) -> None:
        """
        성과 기록 및 가중치 업데이트.

        1. performance 테이블에 기록
        2. score 계산: (retention * 0.4 + ctr * 0.3 + watch_time_norm * 0.3)
        3. 관련 컴포넌트 가중치 업데이트
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # watch_time 정규화 (최대 60초 기준)
        watch_time_norm = min(watch_time / 60.0, 1.0)

        # 종합 점수 계산
        score = retention * 0.4 + ctr * 0.3 + watch_time_norm * 0.3

        cursor.execute(
            "INSERT INTO performance "
            "(combination_id, views, watch_time, retention, ctr, score) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (combination_id, views, watch_time, retention, ctr, score),
        )
        conn.commit()

        logger.info(
            "성과 기록: combination_id=%d, score=%.3f "
            "(retention=%.2f, ctr=%.2f, watch_time=%.1f)",
            combination_id,
            score,
            retention,
            ctr,
            watch_time,
        )

        # 가중치 업데이트
        self._update_weights(combination_id, score)

    def _update_weights(self, combination_id: int, score: float) -> None:
        """
        성과 기반 가중치 업데이트.

        - score > 0.7 → 각 컴포넌트 weight += 0.1
        - score <= 0.3 → 각 컴포넌트 weight -= 0.05
        - weight 범위: [0.1, 3.0]
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # 조합 정보 조회
        cursor.execute(
            "SELECT * FROM story_combinations WHERE id = ?",
            (combination_id,),
        )
        row = cursor.fetchone()
        if not row:
            logger.warning("가중치 업데이트 실패: combination_id=%d 없음", combination_id)
            return

        combination = dict(row)

        # 점수에 따른 가중치 변화량 결정
        if score > 0.7:
            delta = 0.1
            direction = "증가"
        elif score <= 0.3:
            delta = -0.05
            direction = "감소"
        else:
            logger.debug("가중치 변화 없음: score=%.3f (0.3~0.7 범위)", score)
            return

        # 각 컴포넌트 가중치 업데이트
        component_pairs = [
            ("category", combination["category"]),
            ("relationship", combination["relationship"]),
            ("secret", combination["secret"]),
            ("trigger", combination["trigger"]),
            ("twist", combination["twist"]),
        ]

        for comp_type, value in component_pairs:
            cursor.execute(
                "UPDATE story_components "
                "SET weight = MAX(0.1, MIN(3.0, weight + ?)), "
                "    success_score = (success_score * usage_count + ?) / (usage_count + 1) "
                "WHERE type = ? AND value = ?",
                (delta, score, comp_type, value),
            )

        conn.commit()
        logger.info(
            "가중치 %s: combination_id=%d, delta=%.2f, score=%.3f",
            direction,
            combination_id,
            delta,
            score,
        )

    def get_top_components(self, type: str, limit: int = 10) -> list[dict]:
        """성과 상위 컴포넌트"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM story_components "
            "WHERE type = ? "
            "ORDER BY success_score DESC, weight DESC "
            "LIMIT ?",
            (type, limit),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_stats(self) -> dict:
        """
        DB 통계.

        Returns:
            총 컴포넌트 수, 조합 수, 평균 점수 등 통계 정보
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # 타입별 컴포넌트 수
        cursor.execute(
            "SELECT type, COUNT(*) as count FROM story_components GROUP BY type"
        )
        type_counts = {row["type"]: row["count"] for row in cursor.fetchall()}

        # 전체 통계
        cursor.execute("SELECT COUNT(*) as total FROM story_components")
        total_components = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) as total FROM story_combinations")
        total_combinations = cursor.fetchone()["total"]

        cursor.execute(
            "SELECT AVG(score) as avg_score FROM performance WHERE score > 0"
        )
        avg_score_row = cursor.fetchone()
        avg_score = avg_score_row["avg_score"] if avg_score_row["avg_score"] else 0.0

        cursor.execute(
            "SELECT AVG(retention) as avg_retention FROM performance WHERE retention > 0"
        )
        avg_retention_row = cursor.fetchone()
        avg_retention = (
            avg_retention_row["avg_retention"]
            if avg_retention_row["avg_retention"]
            else 0.0
        )

        cursor.execute("SELECT COUNT(*) as total FROM performance")
        total_performance = cursor.fetchone()["total"]

        return {
            "total_components": total_components,
            "total_combinations": total_combinations,
            "total_performance_records": total_performance,
            "type_counts": type_counts,
            "avg_score": round(avg_score, 4),
            "avg_retention": round(avg_retention, 4),
        }

    def close(self) -> None:
        """DB 연결 종료"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            logger.info("DB 연결 종료")
