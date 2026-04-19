# Autonomous Creator - 시스템 아키텍처

## 📖 개요

Autonomous Creator는 AI를 활용한 자동 영상 생성 시스템입니다. 스토리 입력부터 최종 영상 합성까지 전체 파이프라인을 자동화합니다.

**핵심 특징:**
- Disney 3D Animation 스타일 (Pixar 품질)
- 시리즈/에피소드 기반 콘텐츠 제작
- 캐릭터 일관성 유지 (IP-Adapter)
- 비용 최적화 전략
- 클라우드 API 기반 고품질 영상 생성

---

## 🏗️ 전체 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        AUTONOMOUS CREATOR SYSTEM                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         PRESENTATION LAYER                               │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │   │
│  │  │    CLI      │  │    REST     │  │  WebSocket  │  │   Web UI    │    │   │
│  │  │  Interface  │  │    API      │  │   Events    │  │  (Future)   │    │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                       │                                         │
│                                       ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                        APPLICATION LAYER                                 │   │
│  │                                                                          │   │
│  │  ┌───────────────────────────────────────────────────────────────────┐  │   │
│  │  │                    VideoOrchestrator                               │  │   │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │  │   │
│  │  │  │  Story  │ │ Prompt  │ │  Image  │ │  Video  │ │ Compose │     │  │   │
│  │  │  │  Load   │→│  Gen    │→│  Gen    │→│  Gen    │→│  Final  │     │  │   │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘     │  │   │
│  │  └───────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                          │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐    │   │
│  │  │  Checkpoint  │ │  Validation  │ │   Caching    │ │   Logging    │    │   │
│  │  │   Manager    │ │   Service    │ │   Manager    │ │   Service    │    │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                       │                                         │
│                                       ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                          DOMAIN LAYER                                    │   │
│  │                                                                          │   │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐               │   │
│  │  │     Story     │  │   Character   │  │    Series     │               │   │
│  │  │    Entity     │  │    Entity     │  │    Entity     │               │   │
│  │  │               │  │               │  │               │               │   │
│  │  │ - scenes[]    │  │ - appearance  │  │ - episodes[]  │               │   │
│  │  │ - characters  │  │ - expressions │  │ - characters  │               │   │
│  │  │ - metadata    │  │ - outfits     │  │ - locations   │               │   │
│  │  └───────────────┘  └───────────────┘  └───────────────┘               │   │
│  │                                                                          │   │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐               │   │
│  │  │    Scene      │  │    Episode    │  │  Generation   │               │   │
│  │  │    Entity     │  │    Entity     │  │    Result     │               │   │
│  │  └───────────────┘  └───────────────┘  └───────────────┘               │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                       │                                         │
│                                       ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                       INFRASTRUCTURE LAYER                               │   │
│  │                                                                          │   │
│  │  ┌────────────────────────────────────────────────────────────────────┐ │   │
│  │  │                     API Management                                  │ │   │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │ │   │
│  │  │  │  LLM     │ │   TTS    │ │  Image   │ │  Video   │ │  Cache   │ │ │   │
│  │  │  │ Providers│ │ Providers│ │ Providers│ │ Providers│ │  Redis   │ │ │   │
│  │  │  │          │ │          │ │          │ │          │ │          │ │ │   │
│  │  │  │ - Claude │ │ - Azure  │ │ - SD3.5  │ │ - Luma   │ │ - Memory │ │ │   │
│  │  │  │ - OpenAI │ │ - Edge   │ │ - Midj.  │ │ - Runway │ │ - Disk   │ │ │   │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │ │   │
│  │  └────────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                          │   │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐       │   │
│  │  │ Character        │  │ Series           │  │ Prompt           │       │   │
│  │  │ Library          │  │ Manager          │  │ Builder          │       │   │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘       │   │
│  │                                                                          │   │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐       │   │
│  │  │ Storage          │  │ Media            │  │ Style            │       │   │
│  │  │ Manager          │  │ Processor        │  │ Consistency      │       │   │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘       │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 디렉토리 구조

```
autonomous-creator/
│
├── core/                              # 핵심 도메인
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── story/                 # 스토리 엔티티
│   │   │   │   ├── __init__.py
│   │   │   │   ├── story.py           # 스토리 메인
│   │   │   │   └── scene.py           # 장면 엔티티
│   │   │   │
│   │   │   ├── character/             # 캐릭터 엔티티
│   │   │   │   ├── __init__.py
│   │   │   │   └── character.py       # 캐릭터 정의
│   │   │   │
│   │   │   ├── series/                # 시리즈 엔티티
│   │   │   │   ├── __init__.py
│   │   │   │   └── series.py          # 시리즈 정의
│   │   │   │
│   │   │   └── generation/            # 생성 결과 엔티티
│   │   │       ├── __init__.py
│   │   │       └── generation_result.py
│   │   │
│   │   └── value_objects/             # 값 객체
│   │       ├── art_style.py
│   │       └── generation_params.py
│   │
│   └── application/                   # 애플리케이션 서비스
│       ├── orchestrator.py            # 메인 오케스트레이터
│       ├── checkpoint_manager.py      # 체크포인트 관리
│       ├── validation_service.py      # 검증 서비스
│       └── media_cache_manager.py     # 미디어 캐시
│
├── infrastructure/                    # 인프라스트럭처
│   │
│   ├── api/                           # API 관리 (중앙 집중)
│   │   ├── __init__.py
│   │   ├── api_manager.py             # API 중앙 관리자
│   │   ├── base_client.py             # 공통 클라이언트
│   │   ├── retry.py                   # 재시도 로직
│   │   ├── rate_limiter.py            # 속도 제한
│   │   │
│   │   ├── config/
│   │   │   ├── __init__.py
│   │   │   └── api_config.py          # API 설정 (비용, 스타일)
│   │   │
│   │   └── providers/
│   │       ├── llm/                   # LLM 제공자
│   │       │   ├── __init__.py
│   │       │   ├── base.py
│   │       │   ├── claude.py
│   │       │   └── openai.py
│   │       │
│   │       ├── tts/                   # TTS 제공자
│   │       │   ├── __init__.py
│   │       │   ├── base.py
│   │       │   ├── azure_tts.py
│   │       │   └── edge_tts.py
│   │       │
│   │       ├── image/                 # 이미지 생성
│   │       │   ├── __init__.py
│   │       │   ├── base.py
│   │       │   └── stability.py
│   │       │
│   │       └── video/                 # 영상 생성
│   │           ├── __init__.py
│   │           ├── base.py
│   │           └── luma.py            # Luma Dream Machine
│   │
│   ├── character/                     # 캐릭터 관리
│   │   ├── __init__.py
│   │   ├── character_library.py       # 캐릭터 라이브러리
│   │   └── character_generator.py     # 캐릭터 생성
│   │
│   ├── series/                        # 시리즈 관리
│   │   ├── __init__.py
│   │   └── series_manager.py          # 시리즈 매니저
│   │
│   ├── prompt/                        # 프롬프트 생성
│   │   ├── __init__.py
│   │   ├── prompt_generator.py        # AI 프롬프트 생성기
│   │   ├── series_prompt_builder.py   # 시리즈 프롬프트 빌더
│   │   │
│   │   ├── templates/                 # 프롬프트 템플릿
│   │   │   ├── image.json
│   │   │   └── video.json
│   │   │
│   │   └── enhancers/                 # 프롬프트 강화
│   │       ├── style_enhancer.py
│   │       └── quality_enhancer.py
│   │
│   ├── storage/                       # 저장소
│   │   ├── __init__.py
│   │   ├── file_storage.py
│   │   └── media_storage.py
│   │
│   └── media/                         # 미디어 처리
│       ├── __init__.py
│       ├── image_processor.py
│       └── video_composer.py
│
├── interfaces/                        # 인터페이스
│   ├── cli/                           # CLI 인터페이스
│   │   ├── __init__.py
│   │   └── main.py
│   │
│   └── api/                           # REST API
│       ├── __init__.py
│       └── routes.py
│
├── data/                              # 데이터 저장
│   ├── characters/                    # 캐릭터 JSON
│   ├── series/                        # 시리즈 JSON
│   ├── stories/                       # 스토리 JSON
│   └── checkpoints/                   # 체크포인트
│
├── outputs/                           # 출력물
│   ├── images/                        # 생성된 이미지
│   ├── videos/                        # 생성된 영상
│   ├── audio/                         # TTS 오디오
│   └── final/                         # 최종 합성
│
├── docs/                              # 문서
│   ├── ARCHITECTURE.md                # 이 파일
│   ├── WORKFLOW.md                    # 워크플로우
│   └── CONFIGURATION.md               # 설정 가이드
│
├── config/                            # 설정 파일
│   ├── default.yaml
│   └── api_keys.yaml
│
└── main.py                            # 진입점
```

---

## 🔄 핵심 컴포넌트 상세

### 1. VideoOrchestrator (오케스트레이터)

전체 파이프라인을 조율하는 중앙 컨트롤러입니다.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        VideoOrchestrator                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  속성:                                                                  │
│  ├── prompt_generator: PromptGenerator                                  │
│  ├── image_generator: StyleConsistencyManager                           │
│  ├── video_generator: HybridVideoManager                                │
│  ├── tts_service: TTSService                                            │
│  ├── composer: MoviePyComposer                                          │
│  └── checkpoint: CheckpointManager                                      │
│                                                                         │
│  메서드:                                                                │
│  ├── async run(story_id) → OrchestratorResult                          │
│  ├── async generate_prompts(story) → List[PromptResult]                │
│  ├── async generate_images(prompts) → List[ImagePath]                  │
│  ├── async generate_videos(images, prompts) → List[VideoPath]          │
│  ├── async generate_narration(story) → List[AudioPath]                 │
│  └── async compose_final(videos, audios) → FinalVideoPath              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2. Character Entity (캐릭터 엔티티)

시리즈 전체에서 캐릭터 일관성을 유지합니다.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Character Entity                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  속성:                                                                  │
│  ├── id: str                     # 고유 식별자                          │
│  ├── name: str                   # 이름                                 │
│  ├── character_type: CharacterType  # 주인공/조연/동물/NPC              │
│  ├── series_id: str              # 소속 시리즈                          │
│  │                                                                      │
│  ├── appearance:                 # 외형                                 │
│  │   ├── gender: str                                                   │
│  │   ├── age: str                                                      │
│  │   ├── hair_color: str                                               │
│  │   ├── hair_style: str                                               │
│  │   ├── eye_color: str                                                │
│  │   ├── skin_tone: str                                                │
│  │   └── distinctive_features: List[str]                               │
│  │                                                                      │
│  ├── expressions: Dict[str, str] # 표정 프롬프트 맵                     │
│  ├── poses: Dict[str, str]       # 포즈 프롬프트 맵                     │
│  ├── outfits: Dict[str, str]     # 의상 프롬프트 맵                     │
│  │                                                                      │
│  ├── disney_style_prefix: str    # "Disney 3D animation style..."      │
│  └── reference_images: List[str] # IP-Adapter용 참조 이미지             │
│                                                                         │
│  메서드:                                                                │
│  ├── get_full_prompt(expression, pose, outfit) → str                   │
│  ├── get_negative_prompt() → str                                       │
│  └── add_reference_image(image_path) → None                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3. Series Entity (시리즈 엔티티)

시리즈별 고유 스타일과 설정을 관리합니다.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Series Entity                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  속성:                                                                  │
│  ├── id: str                     # 시리즈 고유 ID                       │
│  ├── name: str                   # 시리즈 이름                          │
│  ├── description: str            # 설명                                 │
│  ├── status: SeriesStatus        # active/completed/paused              │
│  │                                                                      │
│  ├── style_settings:             # 스타일 설정                          │
│  │   ├── art_style: str          # "Disney 3D, Pixar quality"          │
│  │   ├── style_prefix: str       # 프롬프트 접두사                      │
│  │   ├── negative_prompt: str    # 네거티브 프롬프트                    │
│  │   └── color_palette: List[str]                                      │
│  │                                                                      │
│  ├── world_setting: str          # 세계관 설정                          │
│  ├── locations: Dict[str, str]   # 장소 프롬프트 맵                     │
│  │   ├── "forest": "enchanted forest with magical creatures..."         │
│  │   ├── "castle": "grand castle with tall spires..."                  │
│  │   └── "village": "peaceful village with cobblestone streets..."      │
│  │                                                                      │
│  ├── character_ids: List[str]    # 등장 캐릭터 ID 목록                  │
│  ├── episodes: List[str]         # 에피소드 ID 목록                      │
│  └── metadata: Dict[str, Any]    # 추가 메타데이터                      │
│                                                                         │
│  메서드:                                                                │
│  ├── to_prompt_context() → Dict[str, Any]                              │
│  ├── add_episode(episode_id) → None                                    │
│  └── add_character(character_id) → None                                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4. API Manager (API 중앙 관리)

모든 외부 API를 통합 관리합니다.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            API Manager                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  관리 대상:                                                             │
│                                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │     LLM     │  │     TTS     │  │   Image     │  │   Video     │   │
│  │  Providers  │  │  Providers  │  │  Providers  │  │  Providers  │   │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤  ├─────────────┤   │
│  │ - Claude    │  │ - Azure     │  │ - SD 3.5    │  │ - Luma      │   │
│  │ - OpenAI    │  │ - Edge TTS  │  │ - Midjourney│  │ - Runway    │   │
│  │ - Gemini    │  │ - Google    │  │ - DALL-E    │  │ - Kling     │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
│                                                                         │
│  공통 기능:                                                             │
│  ├── Rate Limiting (속도 제한)                                         │
│  ├── Retry Logic (재시도 로직)                                         │
│  ├── Cost Tracking (비용 추적)                                         │
│  └── Error Handling (에러 처리)                                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5. Prompt Generator (프롬프트 생성기)

자연어 장면 설명을 AI 프롬프트로 변환합니다.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Prompt Generator                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  입력:                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ scene_description: "해변에서 뛰노는 소녀, 해질녘, 행복한 표정"   │   │
│  │ series_id: "series_001"                                         │   │
│  │ character_ids: ["char_001"]                                     │   │
│  │ location_key: "beach"                                           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  처리 과정:                                                             │
│  1. 시리즈 컨텍스트 로드                                               │
│  2. 캐릭터 정보 로드                                                   │
│  3. 장소 프롬프트 가져오기                                             │
│  4. LLM으로 프롬프트 생성                                              │
│  5. 스타일/품질 태그 추가                                              │
│                                                                         │
│  출력:                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ image_prompt:                                                   │   │
│  │ "Disney 3D animation style, Pixar quality, smooth cel shading,  │   │
│  │  young girl with long black hair, joyful expression, running    │   │
│  │  on sandy beach, golden hour sunset lighting, wind blowing hair, │   │
│  │  waves in background, soft warm colors, masterpiece, best       │   │
│  │  quality, highly detailed"                                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔌 외부 API 통합

### Luma Dream Machine API

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Luma Dream Machine API                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  지원 모델:                                                             │
│  ├── Kling 2.6  - 고품질, 자연스러운 모션 (1 credit/sec)               │
│  ├── Ray 3.14   - 빠른 생성, 좋은 품질 (0.5 credit/sec)                │
│  ├── Veo 3      - Google 최신 모델 (1.5 credit/sec)                    │
│  └── Sora 2     - OpenAI 최신 모델 (2 credit/sec)                      │
│                                                                         │
│  워크플로우:                                                            │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐          │
│  │  이미지  │────▶│  API    │────▶│  대기   │────▶│  영상   │          │
│  │  업로드  │     │  호출   │     │  폴링   │     │  다운로드│          │
│  └─────────┘     └─────────┘     └─────────┘     └─────────┘          │
│                                                                         │
│  엔드포인트:                                                            │
│  POST /dream-machine/v1/generations                                    │
│  GET  /dream-machine/v1/generations/{id}                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 💾 데이터 흐름

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           DATA FLOW                                      │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────┐                                                             │
│  │  입력   │                                                             │
│  │ 스토리  │                                                             │
│  │ 텍스트  │                                                             │
│  └────┬────┘                                                             │
│       │                                                                  │
│       ▼                                                                  │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐           │
│  │  Story  │────▶│  Scene  │────▶│ Prompt  │────▶│  Image  │           │
│  │  JSON   │     │  JSON   │     │  JSON   │     │  PNG    │           │
│  │         │     │         │     │         │     │         │           │
│  │ data/   │     │ data/   │     │ cache/  │     │ outputs/│           │
│  │ stories │     │ scenes  │     │ prompts │     │ images  │           │
│  └─────────┘     └─────────┘     └─────────┘     └────┬────┘           │
│                                                        │                 │
│       ┌────────────────────────────────────────────────┘                │
│       │                                                                  │
│       ▼                                                                  │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐           │
│  │  Video  │────▶│  Audio  │────▶│ Compose │────▶│  Final  │           │
│  │  MP4    │     │  WAV    │     │  MP4    │     │  MP4    │           │
│  │         │     │         │     │         │     │         │           │
│  │ outputs │     │ outputs │     │ temp/   │     │ outputs │           │
│  │ /videos │     │ /audio  │     │ compose │     │ /final  │           │
│  └─────────┘     └─────────┘     └─────────┘     └─────────┘           │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 🎨 아트 스타일 시스템

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        ART STYLE SYSTEM                                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  기본 스타일: Disney 3D Animation (Pixar Quality)                        │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                      STYLE COMPONENTS                               │ │
│  ├────────────────────────────────────────────────────────────────────┤ │
│  │                                                                    │ │
│  │  Style Prefix:                                                     │ │
│  │  "Disney 3D animation style, Pixar quality, smooth cel shading,   │ │
│  │   vibrant colors, expressive eyes, soft lighting"                 │ │
│  │                                                                    │ │
│  │  Character Features:                                               │ │
│  │  ├── Large expressive eyes                                        │ │
│  │  ├── Smooth skin with subtle subsurface scattering                │ │
│  │  ├── Stylized proportions (larger heads, slim bodies)             │ │
│  │  └── Soft, flowing hair                                           │ │
│  │                                                                    │ │
│  │  Environment Features:                                             │ │
│  │  ├── Rich, saturated colors                                       │ │
│  │  ├── Soft shadows and highlights                                  │ │
│  │  ├── Detailed but stylized backgrounds                            │ │
│  │  └── Cinematic lighting                                           │ │
│  │                                                                    │ │
│  │  Negative Prompt:                                                  │ │
│  │  "realistic photo, live action, western cartoon, anime,           │ │
│  │   dark, gritty, photorealistic, low quality, blurry"              │ │
│  │                                                                    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## ⚙️ 비용 최적화 전략

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    COST OPTIMIZATION STRATEGIES                          │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  전략 1: all_api                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 모든 장면을 API로 생성                                            │  │
│  │ - 최고 품질                                                       │  │
│  │ - 가장 높은 비용                                                  │  │
│  │ - 권장: 단편 콘텐츠                                               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  전략 2: key_scenes_api                                                 │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 핵심 장면만 API, 나머지는 로컬                                    │  │
│  │ - 균형 잡힌 품질                                                  │  │
│  │ - 중간 비용                                                       │  │
│  │ - 권장: 에피소드 시리즈                                           │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  전략 3: smart_hybrid (권장)                                            │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ AI가 장면 중요도 판단하여 자동 선택                               │  │
│  │ - 최적화된 품질/비용 균형                                         │  │
│  │ - 자동 비용 절감                                                  │  │
│  │ - 권장: 장기 시리즈                                               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  전략 4: local_first                                                    │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 가능하면 로컬, 실패 시 API 폴백                                   │  │
│  │ - 가장 낮은 비용                                                  │  │
│  │ - 품질 변동 가능                                                  │  │
│  │ - 권장: 테스트/프로토타입                                         │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 🔧 확장 포인트

시스템은 다음과 같은 확장이 용이합니다:

1. **새로운 AI Provider 추가**: `infrastructure/api/providers/`에 새 모듈 추가
2. **새로운 아트 스타일**: `infrastructure/prompt/templates/`에 템플릿 추가
3. **새로운 비용 최적화 전략**: `VideoGenerationStrategy` enum 확장
4. **새로운 미디어 처리**: `infrastructure/media/`에 프로세서 추가

---

## 📚 관련 문서

- [WORKFLOW.md](./WORKFLOW.md) - 상세 워크플로우 및 단계별 설명
- [CONFIGURATION.md](./CONFIGURATION.md) - 설정 가이드 및 API 키 설정
