# Story-to-Video Pipeline - Plan Document

> Feature: story-to-video-pipeline
> Created: 2026-04-01
> Status: Planning

---

## Executive Summary

| 관점 | 내용 |
|------|------|
| **Problem** | 스크립트 입력 시 캐릭터/장소 일관성 부족으로 장면마다 다른 외형의 캐릭터 생성 |
| **Solution** | 4개 모듈로 구성된 자동화 파이프라인: 캐릭터 추출 → 프롬프트 템플릿 → 장소 DB → IP-Adapter |
| **Function/UX Effect** | 스크립트만 입력하면 일관된 캐릭터의 비디오 자동 생성 |
| **Core Value** | 애니메이션/스토리텔링 품질 향상, 수동 작업 90% 감소 |

---

## Context Anchor

| 항목 | 내용 |
|------|------|
| **WHY** | 캐릭터 외형 불일치로 인한 콘텐츠 품질 저하 해결 |
| **WHO** | AI 쇼츠 제작자, 멀티미디어 콘텐츠 크리에이터 |
| **RISK** | IP-Adapter VRAM 요구사항, 다국어 처리 복잡도 |
| **SUCCESS** | 90% 이상 캐릭터 일관성 유지, 전체 파이프라인 자동화 |
| **SCOPE** | 캐릭터 추출, 프롬프트 생성, 장소 DB, IP-Adapter 통합 |

---

## 1. 개요

### 1.1 배경
현재 `autonomous-creator` 프로젝트는 스크립트에서 비디오 생성까지 파이프라인이 구축되어 있으나, 장면마다 캐릭터 외형이 달라지는 문제가 있다.

### 1.2 목표
- 스크립트 입력만으로 일관된 캐릭터/장소의 비디오 자동 생성
- 4가지 핵심 모듈 구현 및 통합

### 1.3 범위
| 포함 | 제외 |
|------|------|
| 캐릭터 정의 추출 | 음성 효과(SFX) 생성 |
| 캐릭터 프롬프트 템플릿 | 비디오 편집 UI |
| 장소 DB 확장 | 3D 렌더링 |
| IP-Adapter 연동 | 실시간 스트리밍 |

---

## 2. 기능 요구사항

### 2.1 캐릭터 정의 추출기 (Character Definition Extractor)

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| CDE-01 | 스크립트에서 캐릭터 이름/설명 자동 파싱 | P0 |
| CDE-02 | 외형, 의상, 액세서리, 능력 구조화 | P0 |
| CDE-03 | 히어로/빌런/엑스트라 타입 분류 | P1 |
| CDE-04 | 다국어 지원 (태국어/한국어/일본어) | P0 |
| CDE-05 | 복잡한 스크립트는 Claude API, 단순한 건 로컬 규칙 | P0 |

**입력 예시:**
```
ฮีโรโน (Hearono): เด็กหนุ่มที่มีพลังพิเศษ... ใส่หูฟังขนาดใหญ่
```

**출력 예시:**
```json
{
  "id": "char_001",
  "name": "Hearono",
  "name_local": "ฮีโรโน",
  "type": "hero",
  "appearance": {
    "age": "young adult",
    "clothing": "hooded cloak",
    "accessories": ["large noise-canceling headphones"],
    "build": "slim athletic"
  },
  "powers": ["sound wave control", "sound sensing"],
  "personality": "calm, determined"
}
```

### 2.2 캐릭터 프롬프트 템플릿 (Character Prompt Template)

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| CPT-01 | 캐릭터 JSON을 SD 3.5 프롬프트로 변환 | P0 |
| CPT-02 | 장면별 포즈/액션과 결합 | P0 |
| CPT-03 | 스타일 키워드 자동 추가 (anime/realistic) | P1 |
| CPT-04 | Negative 프롬프트 자동 생성 | P0 |

**템플릿 구조:**
```python
TEMPLATE = """
{character_base_description},
{pose_or_action},
{scene_background},
{style_keywords},
{quality_keywords}
"""
```

### 2.3 장소 DB 확장 (Location Database)

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| LOC-01 | 도시/장소/시간대 계층 구조 | P0 |
| LOC-02 | 동적 확장 (새 장소 자동 학습) | P2 |
| LOC-03 | 분위기/조명/날씨 속성 | P0 |
| LOC-04 | 카메라 앵글 프리셋 | P1 |

**계층 구조:**
```
locations/
├── cities/
│   ├── bangkok/
│   │   ├── bangkok_night.json
│   │   ├── bangkok_night_20xx.json (미래)
│   │   └── bangkok_day.json
│   ├── seoul/
│   └── tokyo/
├── place_types/
│   ├── rooftop.json
│   ├── police_station.json
│   ├── street.json
│   └── indoor.json
└── time_of_day/
    ├── day.json
    ├── night.json
    └── evening.json
```

### 2.4 IP-Adapter 연동 (Character Consistency)

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| IPA-01 | 캐릭터 기준 이미지 자동 생성 | P0 |
| IPA-02 | 사용자 제공 이미지로 덮어쓰기 가능 | P0 |
| IPA-03 | CPU offload 지원 (6GB VRAM) | P0 |
| IPA-04 | 다중 캐릭터 장면 지원 | P1 |
| IPA-05 | 캐릭터 ID 기반 캐싱 | P1 |

**동작 방식:**
```
1. 캐릭터 정의 → 기준 이미지 1장 생성 (사용자 덮어쓰기 가능)
2. IP-Adapter로 특징 추출
3. 각 장면에서 동일 얼굴, 다른 포즈로 생성
```

---

## 3. 통합 파이프라인

### 3.1 전체 흐름도

```
┌─────────────────────────────────────────────────────────────────────┐
│                     INPUT: 스크립트 (태국어/한국어/일본어)            │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  [Module 1] 캐릭터 정의 추출기                                        │
│  - 로컬 규칙 기반 1차 파싱                                            │
│  - 복잡한 경우 Claude API 호출                                        │
│  - 캐릭터 JSON 리스트 출력                                            │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  [Module 2] 캐릭터 프롬프트 템플릿                                    │
│  - 캐릭터 JSON → SD 3.5 프롬프트 변환                                 │
│  - 장면별 포즈/액션 결합                                              │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  [Module 3] 장소 DB 매칭                                             │
│  - 스크립트에서 장소 키워드 추출                                       │
│  - 계층 DB에서 적절한 배경 프롬프트 검색                               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  [Module 4] IP-Adapter 통합                                          │
│  - 각 캐릭터 기준 이미지 생성/로드                                     │
│  - 일관된 외형으로 모든 장면 이미지 생성                               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  [기존 파이프라인]                                                    │
│  - TTS (태국어/한국어/일본어)                                         │
│  - SVD (이미지 → 비디오)                                              │
│  - 최종 합성                                                          │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     OUTPUT: 완성된 비디오                             │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 기존 코드와의 통합 지점

| 기존 파일 | 통합 방식 |
|-----------|----------|
| `core/application/orchestrator.py` | `_generate_script()` 후 캐릭터 추출 호출 |
| `infrastructure/image/sd35_generator.py` | IP-Adapter 래핑 |
| `infrastructure/image/style_consistency.py` | 캐릭터 일관성 로직 확장 |
| `prompt_expander.py` (신규) | 장소 DB로 확장 |

---

## 4. 기술 명세

### 4.1 새로 생성할 파일

```
infrastructure/
├── script_parser/
│   ├── __init__.py
│   ├── character_extractor.py      # 캐릭터 정의 추출
│   ├── scene_parser.py             # 장면 파싱
│   └── llm_extractor.py            # Claude API 연동
├── prompt/
│   ├── __init__.py
│   ├── character_template.py       # 캐릭터 프롬프트 템플릿
│   ├── location_db.py              # 장소 DB
│   └── prompt_builder.py           # 통합 프롬프트 빌더
└── image/
    ├── ip_adapter_client.py        # IP-Adapter 클라이언트
    └── character_cache.py          # 캐릭터 이미지 캐시

data/
└── locations/                       # 장소 DB JSON 파일들
    ├── cities/
    ├── place_types/
    └── time_of_day/
```

### 4.2 수정할 파일

| 파일 | 수정 내용 |
|------|----------|
| `core/application/orchestrator.py` | 캐릭터 추출 단계 추가 |
| `infrastructure/image/sd35_generator.py` | IP-Adapter 통합 |
| `config/settings.py` | IP-Adapter 설정 추가 |

### 4.3 의존성

```
# requirements.txt 추가
ip-adapter>=1.0.0
insightface>=0.7.3
onnxruntime>=1.16.0
```

---

## 5. 구현 계획

### 5.1 Phase 1: 캐릭터 추출 (2일)

| 일차 | 작업 |
|------|------|
| 1 | `character_extractor.py` 로컬 규칙 구현 |
| 1 | `llm_extractor.py` Claude API 연동 |
| 2 | 다국어 지원 (태국어/한국어/일본어) |
| 2 | 통합 테스트 |

### 5.2 Phase 2: 프롬프트 템플릿 (1일)

| 일차 | 작업 |
|------|------|
| 3 | `character_template.py` 구현 |
| 3 | `prompt_builder.py` 통합 빌더 |
| 3 | 기존 `prompt_expander.py` 통합 |

### 5.3 Phase 3: 장소 DB (1일)

| 일차 | 작업 |
|------|------|
| 4 | `location_db.py` 구현 |
| 4 | 기본 장소 JSON 생성 (방콕, 서울, 도쿄) |
| 4 | 계층 검색 로직 |

### 5.4 Phase 4: IP-Adapter (2일)

| 일차 | 작업 |
|------|------|
| 5 | `ip_adapter_client.py` 구현 |
| 5 | CPU offload 설정 |
| 6 | 캐릭터 캐시 구현 |
| 6 | 기존 파이프라인 통합 |

### 5.5 Phase 5: 통합 테스트 (1일)

| 일차 | 작업 |
|------|------|
| 7 | 전체 파이프라인 E2E 테스트 |
| 7 | 사용자 제공 스크립트로 검증 |

---

## 6. 성공 기준

| 지표 | 목표 |
|------|------|
| 캐릭터 일관성 | 90% 이상 (동일 외형 유지) |
| 처리 시간 | 3분 스크립트 → 10분 내 완성 |
| 메모리 사용 | 6GB VRAM 이하 |
| 다국어 지원 | 태국어/한국어/일본어 100% |

---

## 7. 리스크 및 대응

| 리스크 | 확률 | 영향 | 대응 방안 |
|--------|------|------|----------|
| IP-Adapter VRAM 부족 | 중 | 높 | CPU offload, 이미지 해상도 조정 |
| 다국어 파싱 오류 | 중 | 중 | 언어별 규칙 분리, LLM 백업 |
| Claude API 비용 | 낮 | 중 | 로컬 우선, 복잡한 경우만 API |
| 캐릭터 추출 정확도 | 중 | 높 | 사용자 수정 UI 제공 |

---

## 8. 승인

| 역할 | 이름 | 일자 | 서명 |
|------|------|------|------|
| 작성자 | Claude Code | 2026-04-01 | - |
| 검토자 | - | - | - |
| 승인자 | User | - | - |

---

## 9. 참조

- 기존 코드: `D:\AI-Video\autonomous-creator\`
- 관련 문서: `docs/01-plan/features/autonomous-creator-migration.plan.md`
- IP-Adapter: https://github.com/tencent-ailab/IP-Adapter
