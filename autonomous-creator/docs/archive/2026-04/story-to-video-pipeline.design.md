# Story-to-Video Pipeline - Design Document

> Feature: story-to-video-pipeline
> Created: 2026-04-01
> Architecture: Option C - Pragmatic Balance
> Status: Design

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

### 1.1 목표
스크립트 입력만으로 일관된 캐릭터/장소의 비디오를 자동 생성하는 파이프라인 구축

### 1.2 설계 원칙
- 기존 구조 존중 (infrastructure 레이어 패턴 유지)
- 필요한 곳에만 분리 (과도한 추상화 지양)
- 6GB VRAM 제약 고려 (CPU offload 기본)

### 1.3 아키텍처 선택 이유
| 기준 | 선택 이유 |
|------|----------|
| 유지보수 | 기존 패턴 따라 새 모듈 추가 |
| 구현 시간 | 4일 예상 (균형) |
| 확장성 | 모듈 단위로 독립 확장 가능 |

---

## 2. 아키텍처 설계

### 2.1 전체 구조

```
autonomous-creator/
├── core/
│   ├── domain/
│   │   └── entities/
│   │       └── character.py          # [신규] 캐릭터 엔티티
│   └── application/
│       └── orchestrator.py           # [수정] 새 모듈 호출 추가
│
├── infrastructure/
│   ├── script_parser/                # [신규] 모듈
│   │   ├── __init__.py
│   │   ├── character_extractor.py    # 로컬 규칙 기반 추출
│   │   ├── scene_parser.py           # 장면 파싱
│   │   └── llm_extractor.py          # Claude API 연동
│   │
│   ├── prompt/                       # [신규] 모듈
│   │   ├── __init__.py
│   │   ├── character_template.py     # 캐릭터 프롬프트 템플릿
│   │   ├── location_db.py            # 장소 DB 관리
│   │   └── prompt_builder.py         # 통합 프롬프트 빌더
│   │
│   └── image/
│       ├── sd35_generator.py         # [수정] IP-Adapter 통합
│       ├── ip_adapter_client.py      # [신규] IP-Adapter 클라이언트
│       └── character_cache.py        # [신규] 캐릭터 이미지 캐시
│
├── data/
│   └── locations/                    # [신규] 장소 DB JSON
│       ├── cities/
│       ├── place_types/
│       └── time_of_day/
│
└── config/
    └── settings.py                   # [수정] IP-Adapter 설정 추가
```

### 2.2 모듈 의존성

```
┌─────────────────────────────────────────────────────────────┐
│                     orchestrator.py                          │
└─────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│script_parser │ │   prompt     │ │location_db   │ │ ip_adapter   │
│              │ │              │ │              │ │              │
│ - character  │ │ - template   │ │ - cities     │ │ - client     │
│ - scene      │ │ - builder    │ │ - places     │ │ - cache      │
│ - llm        │ └──────────────┘ │ - time       │ └──────────────┘
└──────────────┘                  └──────────────┘
         │
         ▼
┌──────────────┐
│ Character    │
│ Entity       │
└──────────────┘
```

---

## 3. 모듈 상세 설계

### 3.1 Character Entity

**파일:** `core/domain/entities/character.py`

```python
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

class CharacterType(Enum):
    HERO = "hero"
    VILLAIN = "villain"
    SUPPORTING = "supporting"
    EXTRA = "extra"

@dataclass
class CharacterAppearance:
    age: str = "adult"
    gender: str = "unknown"
    body_type: str = "average"
    hair: str = ""
    clothing: list[str] = field(default_factory=list)
    accessories: list[str] = field(default_factory=list)
    distinctive_features: list[str] = field(default_factory=list)

@dataclass
class Character:
    id: str
    name: str
    name_local: Optional[str] = None
    type: CharacterType = CharacterType.SUPPORTING
    appearance: CharacterAppearance = field(default_factory=CharacterAppearance)
    personality: list[str] = field(default_factory=list)
    powers: list[str] = field(default_factory=list)
    
    # IP-Adapter용
    reference_image_path: Optional[str] = None
    embedding_cache: Optional[str] = None
    
    def to_prompt_segment(self) -> str:
        """프롬프트용 문자열 변환"""
        ...
```

### 3.2 Script Parser Module

#### 3.2.1 Character Extractor

**파일:** `infrastructure/script_parser/character_extractor.py`

```python
class CharacterExtractor:
    """
    로컬 규칙 기반 캐릭터 추출
    
    지원 형식:
    - "이름 (영문): 설명"
    - "이름: 설명"
    """
    
    # 언어별 패턴
    PATTERNS = {
        "th": r"([ก-๙]+)\s*\(([A-Za-z]+)\):\s*(.+)",
        "ko": r"([가-힣]+)\s*\(([A-Za-z]+)\):\s*(.+)",
        "ja": r"([ぁ-んァ-ン一-龥]+)\s*\(([A-Za-z]+)\):\s*(.+)",
        "en": r"([A-Za-z]+):\s*(.+)"
    }
    
    def extract(self, script: str, language: str) -> list[Character]:
        """스크립트에서 캐릭터 추출"""
        ...
    
    def _parse_description(self, desc: str) -> CharacterAppearance:
        """설명에서 외형 속성 추출"""
        ...
```

#### 3.2.2 LLM Extractor

**파일:** `infrastructure/script_parser/llm_extractor.py`

```python
class LLMExtractor:
    """
    Claude API 기반 복잡한 스크립트 분석
    """
    
    EXTRACTION_PROMPT = """
    다음 스크립트에서 등장인물 정보를 추출하세요.
    
    스크립트:
    {script}
    
    출력 형식 (JSON):
    {{
      "characters": [
        {{
          "name": "영문명",
          "name_local": "원어명",
          "type": "hero|villain|supporting|extra",
          "appearance": {{
            "age": "...",
            "clothing": ["..."],
            "accessories": ["..."]
          }},
          "powers": ["..."],
          "personality": ["..."]
        }}
      ]
    }}
    """
    
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
    
    async def extract(self, script: str) -> list[Character]:
        """API 호출로 캐릭터 추출"""
        ...
```

#### 3.2.3 Scene Parser

**파일:** `infrastructure/script_parser/scene_parser.py`

```python
@dataclass
class ParsedScene:
    index: int
    description: str
    characters: list[str]  # 캐릭터 ID
    location: str
    time_of_day: str
    action: str
    dialogue: str
    camera_angle: Optional[str] = None

class SceneParser:
    """장면 단위 파싱"""
    
    def parse(self, script: str) -> list[ParsedScene]:
        """스크립트를 장면으로 분리"""
        ...
```

### 3.3 Prompt Module

#### 3.3.1 Character Template

**파일:** `infrastructure/prompt/character_template.py`

```python
class CharacterTemplate:
    """캐릭터 프롬프트 템플릿"""
    
    BASE_TEMPLATE = """
{gender} {age}, {body_type} build,
{hair_description},
wearing {clothing},
{accessories},
{distinctive_features}
""".strip()

    POSE_TEMPLATES = {
        "standing": "standing upright, confident posture",
        "sitting": "sitting on {surface}, relaxed",
        "action": "{action_description}, dynamic pose",
        "fighting": "combat stance, ready to strike",
        "flying": "floating in air, {power_effect}"
    }
    
    def build_prompt(
        self, 
        character: Character, 
        pose: str = "standing",
        action: Optional[str] = None
    ) -> str:
        """캐릭터 프롬프트 생성"""
        ...
    
    def build_negative(self, character: Character) -> str:
        """Negative 프롬프트 생성"""
        ...
```

#### 3.3.2 Location DB

**파일:** `infrastructure/prompt/location_db.py`

```python
@dataclass
class LocationData:
    id: str
    name: str
    elements: list[str]
    lighting: str
    atmosphere: str
    colors: list[str]
    negative: str

class LocationDB:
    """장소 데이터베이스 관리"""
    
    def __init__(self, data_dir: str = "data/locations"):
        self._cities: dict[str, LocationData] = {}
        self._place_types: dict[str, LocationData] = {}
        self._time_of_day: dict[str, LocationData] = {}
        self._load_all()
    
    def find(
        self, 
        city: Optional[str] = None,
        place_type: Optional[str] = None,
        time: Optional[str] = None
    ) -> LocationData:
        """계층 검색으로 장소 프롬프트 조회"""
        ...
    
    def get_prompt(self, location: LocationData) -> str:
        """장소 프롬프트 생성"""
        ...
```

#### 3.3.3 Prompt Builder

**파일:** `infrastructure/prompt/prompt_builder.py`

```python
class PromptBuilder:
    """통합 프롬프트 빌더"""
    
    def __init__(
        self,
        character_template: CharacterTemplate,
        location_db: LocationDB
    ):
        self.character_template = character_template
        self.location_db = location_db
    
    def build_scene_prompt(
        self,
        characters: list[Character],
        scene: ParsedScene,
        style: str = "cinematic"
    ) -> tuple[str, str]:
        """
        장면 전체 프롬프트 생성
        
        Returns:
            (positive_prompt, negative_prompt)
        """
        ...
```

### 3.4 IP-Adapter Module

#### 3.4.1 IP-Adapter Client

**파일:** `infrastructure/image/ip_adapter_client.py`

```python
class IPAdapterClient:
    """
    IP-Adapter 클라이언트
    
    6GB VRAM 대응:
    - CPU offload 기본 사용
    - 낮은 해상도 기본값
    """
    
    def __init__(
        self,
        sd_pipeline,
        ip_adapter_path: str = "models/ip-adapter",
        device: str = "cuda",
        cpu_offload: bool = True
    ):
        self.pipeline = sd_pipeline
        self.cpu_offload = cpu_offload
        self._load_ip_adapter(ip_adapter_path)
    
    def set_reference_image(self, image_path: str) -> None:
        """캐릭터 기준 이미지 설정"""
        ...
    
    def generate_with_identity(
        self,
        prompt: str,
        negative_prompt: str,
        strength: float = 0.8,
        **kwargs
    ) -> Image:
        """일관된 외형으로 이미지 생성"""
        ...
```

#### 3.4.2 Character Cache

**파일:** `infrastructure/image/character_cache.py`

```python
class CharacterCache:
    """캐릭터 이미지/임베딩 캐시"""
    
    def __init__(self, cache_dir: str = "data/character_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get(self, character_id: str) -> Optional[str]:
        """캐시된 기준 이미지 경로 반환"""
        ...
    
    def set(self, character_id: str, image_path: str) -> None:
        """기준 이미지 캐시 저장"""
        ...
    
    def get_embedding(self, character_id: str) -> Optional[np.ndarray]:
        """캐시된 임베딩 반환"""
        ...
```

---

## 4. 데이터 구조

### 4.1 장소 DB JSON 스키마

**cities/bangkok_night.json:**
```json
{
  "id": "bangkok_night",
  "name": "Bangkok Night",
  "elements": [
    "tuk-tuks",
    "Thai neon signs",
    "pink and green taxis",
    "street food vendors",
    "BTS skytrain",
    "wat temple silhouettes"
  ],
  "lighting": "neon lights, street lamps, car headlights",
  "atmosphere": "humid, vibrant, chaotic energy",
  "colors": ["neon pink", "green", "orange", "warm yellow"],
  "weather": ["clear", "light rain"],
  "camera_angles": ["low angle", "wide shot", "street level"],
  "negative": "chinese, hong kong, japanese, korean, red lanterns"
}
```

**place_types/rooftop.json:**
```json
{
  "id": "rooftop",
  "name": "Building Rooftop",
  "elements": [
    "concrete floor",
    "antenna equipment",
    "city skyline view",
    "rooftop edge"
  ],
  "lighting": "moonlight + city lights",
  "atmosphere": "windy, isolated, dramatic",
  "colors": ["dark blue", "city light orange"],
  "camera_angles": ["low angle looking up", "high angle looking down"]
}
```

### 4.2 캐릭터 캐시 구조

```
data/character_cache/
├── char_001/
│   ├── reference.png          # 기준 이미지
│   ├── embedding.npy          # IP-Adapter 임베딩
│   └── metadata.json          # 캐릭터 정보
└── char_002/
    └── ...
```

---

## 5. 기존 코드 통합

### 5.1 orchestrator.py 수정

```python
# 추가할 import
from infrastructure.script_parser import CharacterExtractor, SceneParser, LLMExtractor
from infrastructure.prompt import PromptBuilder, CharacterTemplate, LocationDB
from infrastructure.image.ip_adapter_client import IPAdapterClient
from infrastructure.image.character_cache import CharacterCache

class PipelineOrchestrator:
    def __init__(self, ...):
        # 기존 초기화
        ...
        
        # [신규] 캐릭터 관련 초기화
        self.character_extractor = CharacterExtractor()
        self.llm_extractor = LLMExtractor(settings.anthropic_api_key)
        self.scene_parser = SceneParser()
        self.prompt_builder = PromptBuilder(
            CharacterTemplate(),
            LocationDB()
        )
        self.character_cache = CharacterCache()
        self.ip_adapter: Optional[IPAdapterClient] = None
    
    async def generate_video(self, story: Story, ...) -> GenerationTask:
        # [신규] Step 0: 캐릭터 추출
        characters = await self._extract_characters(story)
        scenes = self._parse_scenes(story.content)
        
        # [신규] IP-Adapter 초기화 (캐릭터 있을 때만)
        if characters:
            self.ip_adapter = IPAdapterClient(self.sd_pipeline)
            await self._prepare_character_references(characters)
        
        # 기존 파이프라인 계속...
    
    async def _extract_characters(self, story: Story) -> list[Character]:
        """캐릭터 추출 (로컬 → LLM 백업)"""
        characters = self.character_extractor.extract(
            story.content, 
            story.language
        )
        
        if not characters and len(story.content) > 500:
            # 복잡한 스크립트는 LLM 사용
            characters = await self.llm_extractor.extract(story.content)
        
        return characters
    
    async def _prepare_character_references(self, characters: list[Character]):
        """캐릭터 기준 이미지 준비"""
        for char in characters:
            cached = self.character_cache.get(char.id)
            if cached:
                char.reference_image_path = cached
            else:
                # 기준 이미지 생성
                ref_image = await self._generate_reference_image(char)
                self.character_cache.set(char.id, ref_image)
                char.reference_image_path = ref_image
```

### 5.2 sd35_generator.py 수정

```python
class SD35Generator:
    def __init__(self, ...):
        # 기존 초기화
        ...
        
        # [신규] IP-Adapter 옵션
        self.ip_adapter: Optional[IPAdapterClient] = None
    
    def enable_ip_adapter(self, path: str = "models/ip-adapter"):
        """IP-Adapter 활성화"""
        self.ip_adapter = IPAdapterClient(
            self.pipeline,
            ip_adapter_path=path,
            cpu_offload=self.vram < 12
        )
    
    async def generate(
        self,
        prompt: str,
        negative_prompt: str,
        character_reference: Optional[str] = None,
        **kwargs
    ) -> Image:
        """이미지 생성 (IP-Adapter 선택적 사용)"""
        
        if character_reference and self.ip_adapter:
            return self.ip_adapter.generate_with_identity(
                prompt=prompt,
                negative_prompt=negative_prompt,
                reference_image=character_reference,
                **kwargs
            )
        else:
            # 기존 로직
            return self.pipeline(...)
```

### 5.3 settings.py 수정

```python
class Settings(BaseSettings):
    # 기존 설정
    ...
    
    # [신규] IP-Adapter 설정
    ip_adapter_enabled: bool = True
    ip_adapter_model_path: str = "models/ip-adapter"
    ip_adapter_strength: float = 0.8
    
    # [신규] 캐릭터 캐시 설정
    character_cache_dir: str = "data/character_cache"
    character_cache_max_size_mb: int = 500
```

---

## 6. 구현 순서

### Phase 1: 기반 구조 (1일)

| 순서 | 작업 | 파일 |
|------|------|------|
| 1.1 | Character 엔티티 생성 | `core/domain/entities/character.py` |
| 1.2 | 장소 DB JSON 생성 | `data/locations/*.json` |
| 1.3 | settings.py 설정 추가 | `config/settings.py` |

### Phase 2: 캐릭터 추출 (1일)

| 순서 | 작업 | 파일 |
|------|------|------|
| 2.1 | character_extractor.py | `infrastructure/script_parser/` |
| 2.2 | scene_parser.py | `infrastructure/script_parser/` |
| 2.3 | llm_extractor.py | `infrastructure/script_parser/` |

### Phase 3: 프롬프트 모듈 (1일)

| 순서 | 작업 | 파일 |
|------|------|------|
| 3.1 | character_template.py | `infrastructure/prompt/` |
| 3.2 | location_db.py | `infrastructure/prompt/` |
| 3.3 | prompt_builder.py | `infrastructure/prompt/` |

### Phase 4: IP-Adapter (1일)

| 순서 | 작업 | 파일 |
|------|------|------|
| 4.1 | ip_adapter_client.py | `infrastructure/image/` |
| 4.2 | character_cache.py | `infrastructure/image/` |
| 4.3 | sd35_generator.py 수정 | `infrastructure/image/` |
| 4.4 | orchestrator.py 수정 | `core/application/` |

---

## 7. API 인터페이스

### 7.1 CharacterExtractor

```python
class CharacterExtractor:
    def extract(self, script: str, language: str) -> list[Character]:
        """스크립트에서 캐릭터 목록 추출"""
        
    def extract_single(self, line: str, language: str) -> Optional[Character]:
        """단일 라인에서 캐릭터 추출"""
```

### 7.2 PromptBuilder

```python
class PromptBuilder:
    def build_scene_prompt(
        self,
        characters: list[Character],
        scene: ParsedScene,
        style: str = "cinematic"
    ) -> tuple[str, str]:
        """(positive, negative) 프롬프트 반환"""
        
    def build_character_prompt(
        self,
        character: Character,
        pose: str = "standing",
        action: Optional[str] = None
    ) -> str:
        """캐릭터 프롬프트 반환"""
```

### 7.3 IPAdapterClient

```python
class IPAdapterClient:
    def set_reference_image(self, image_path: str) -> None:
        """기준 이미지 설정"""
        
    def generate_with_identity(
        self,
        prompt: str,
        negative_prompt: str,
        strength: float = 0.8,
        **kwargs
    ) -> Image:
        """일관된 외형으로 생성"""
```

---

## 8. 에러 처리

### 8.1 예외 클래스

```python
# infrastructure/script_parser/exceptions.py
class ScriptParseError(Exception):
    """스크립트 파싱 오류"""
    pass

class CharacterExtractionError(ScriptParseError):
    """캐릭터 추출 실패"""
    pass

class LLMExtractionError(ScriptParseError):
    """LLM 추출 실패"""
    pass

# infrastructure/image/exceptions.py
class IPAdapterError(Exception):
    """IP-Adapter 오류"""
    pass

class CharacterCacheError(Exception):
    """캐릭터 캐시 오류"""
    pass
```

### 8.2 폴백 전략

| 상황 | 폴백 |
|------|------|
| LLM API 실패 | 로컬 규칙만 사용 |
| IP-Adapter 로드 실패 | 일반 SD 3.5 사용 |
| 캐릭터 추출 실패 | 장면 설명만으로 프롬프트 생성 |
| 장소 DB 미스 | 기본 "urban street" 사용 |

---

## 9. 테스트 전략

### 9.1 단위 테스트

```python
# tests/test_character_extractor.py
def test_extract_thai_character():
    script = "ฮีโรโน (Hearono): เด็กหนุ่มที่มีพลังพิเศษ"
    extractor = CharacterExtractor()
    characters = extractor.extract(script, "th")
    
    assert len(characters) == 1
    assert characters[0].name == "Hearono"
    assert characters[0].name_local == "ฮีโรโน"

# tests/test_prompt_builder.py
def test_build_scene_prompt():
    builder = PromptBuilder(CharacterTemplate(), LocationDB())
    positive, negative = builder.build_scene_prompt(
        characters=[mock_character],
        scene=mock_scene,
        style="cinematic"
    )
    
    assert "Hearono" in positive
    assert "blurry" in negative
```

### 9.2 통합 테스트

```python
# tests/test_pipeline_integration.py
@pytest.mark.asyncio
async def test_full_pipeline():
    orchestrator = PipelineOrchestrator(...)
    
    story = Story(
        title="테스트 스토리",
        content="ฮีโรโน (Hearono): เด็กหนุ่ม...",
        language="th"
    )
    
    task = await orchestrator.generate_video(story)
    
    assert task.status == TaskStatus.COMPLETED
    assert len(task.output_paths) > 0
```

---

## 10. 성능 고려사항

### 10.1 VRAM 최적화

```python
# IP-Adapter 로드 시 CPU offload 필수
ip_adapter = IPAdapterClient(
    sd_pipeline,
    cpu_offload=True  # 6GB VRAM 필수
)

# 캐릭터 기준 이미지는 낮은 해상도로 생성
REFERENCE_SIZE = (512, 512)  # 기준 이미지

# 장면 이미지는 필요시에만 고해상도
SCENE_SIZE = (576, 1024)  # 현재 설정 유지
```

### 10.2 캐싱 전략

| 항목 | 캐시 위치 | TTL |
|------|----------|-----|
| 캐릭터 기준 이미지 | `data/character_cache/` | 영구 |
| IP-Adapter 임베딩 | 메모리 + 파일 | 영구 |
| 장소 DB | 메모리 | 프로세스 수명 |

---

## 11. 구현 가이드

### 11.1 새 파일 생성 목록

| 파일 | 라인 예상 | 설명 |
|------|----------|------|
| `core/domain/entities/character.py` | ~80 | 캐릭터 엔티티 |
| `infrastructure/script_parser/__init__.py` | ~10 | 모듈 초기화 |
| `infrastructure/script_parser/character_extractor.py` | ~150 | 로컬 추출 |
| `infrastructure/script_parser/scene_parser.py` | ~100 | 장면 파싱 |
| `infrastructure/script_parser/llm_extractor.py` | ~80 | LLM 추출 |
| `infrastructure/prompt/__init__.py` | ~10 | 모듈 초기화 |
| `infrastructure/prompt/character_template.py` | ~120 | 프롬프트 템플릿 |
| `infrastructure/prompt/location_db.py` | ~150 | 장소 DB |
| `infrastructure/prompt/prompt_builder.py` | ~100 | 프롬프트 빌더 |
| `infrastructure/image/ip_adapter_client.py` | ~200 | IP-Adapter |
| `infrastructure/image/character_cache.py` | ~80 | 캐시 |
| `data/locations/cities/bangkok_night.json` | ~30 | 장소 데이터 |
| `data/locations/cities/seoul_night.json` | ~30 | 장소 데이터 |
| `data/locations/cities/tokyo_night.json` | ~30 | 장소 데이터 |
| `data/locations/place_types/rooftop.json` | ~20 | 장소 데이터 |
| `data/locations/place_types/police_station.json` | ~20 | 장소 데이터 |
| `data/locations/place_types/street.json` | ~20 | 장소 데이터 |
| `data/locations/time_of_day/night.json` | ~15 | 시간대 데이터 |

**총 신규 라인:** ~1,200줄

### 11.2 수정 파일 목록

| 파일 | 수정 내용 | 라인 변경 |
|------|----------|----------|
| `core/application/orchestrator.py` | 캐릭터 추출 단계 추가 | +80 |
| `infrastructure/image/sd35_generator.py` | IP-Adapter 통합 | +40 |
| `config/settings.py` | 설정 추가 | +10 |

**총 수정 라인:** ~130줄

---

## 12. Session Guide

### 12.1 Module Map

| Module | 파일 | 의존성 | 예상 시간 |
|--------|------|--------|----------|
| module-1 | `character.py` + 장소 JSON | 없음 | 1시간 |
| module-2 | `character_extractor.py` | module-1 | 2시간 |
| module-3 | `scene_parser.py` + `llm_extractor.py` | module-1 | 2시간 |
| module-4 | `character_template.py` + `location_db.py` | module-1 | 2시간 |
| module-5 | `prompt_builder.py` | module-4 | 1시간 |
| module-6 | `ip_adapter_client.py` + `character_cache.py` | module-1 | 3시간 |
| module-7 | 통합 (`orchestrator.py`, `sd35_generator.py`) | module-2~6 | 2시간 |

### 12.2 Recommended Session Plan

```
Session 1: module-1 (기반 구조)
├── character.py 엔티티
└── 장소 DB JSON 5개

Session 2: module-2, module-3 (캐릭터 추출)
├── character_extractor.py
├── scene_parser.py
└── llm_extractor.py

Session 3: module-4, module-5 (프롬프트)
├── character_template.py
├── location_db.py
└── prompt_builder.py

Session 4: module-6 (IP-Adapter)
├── ip_adapter_client.py
└── character_cache.py

Session 5: module-7 (통합)
├── orchestrator.py 수정
├── sd35_generator.py 수정
└── E2E 테스트
```

---

## 13. 참조

- Plan 문서: `docs/01-plan/features/story-to-video-pipeline.plan.md`
- IP-Adapter: https://github.com/tencent-ailab/IP-Adapter
- InsightFace: https://github.com/deepinsight/insightface
