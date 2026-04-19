# Autonomous Creator - Claude Code 가이드

## 프로젝트 개요

AI 기반 자동 영상 생성 시스템. 스토리 텍스트 입력 → 고품질 영상 출력.

## 핵심 철학

> **"스토리를 생성하지 말고, 스토리를 컴파일하고, 제약(Budget) 안에서 렌더링하며, 일관성을 유지하고, 측정하고 개선하라"**

## 아키텍처

```
[Raw Story (자유 형식 입력)]
    ↓
[UnifiedStoryCompiler]  ⭐ LLM 1회 호출로 전체 컴파일
    │                      장르/톤/캐릭터/배경 자동 추출
    │                      4-Act 구조 + Scene 생성 + Hook 스코어링
    │                      빈약한 입력 → LLM이 보강
    │                      language 파라미터로 다국어 지원 (ko/th/vi/en/ja/zh)
    ↓
[StoryValidator]         → 제약 검증 (duration/scene 수/hook/arc)
    ↓ 실패 시 최대 2회 재시도 (LLM 피드백 + 자동 수정)
[StorySpec (완전한 JSON)]
    ↓
[Character Identity Engine]  ⭐ 캐릭터 일관성
    ↓
[Prompt Compiler (청킹)]     ⭐ A1111 방식 75토큰 청킹 (77토큰 제한 극복)
    │                      2인 이상 씬: appearance 분리 (action에만 의존)
    ↓
[Image Factory]              ⭐ .env 설정에 따라 자동 모델 선택
    ├─ local/sdxl  (SDXLGenerator)  ⭐ 프롬프트 청킹 + Face Authority
    ├─ local/sd35  (SD35Generator)
    └─ api/stability (StabilitySD35Client)
    ↓
[Render Engine (4요소)]       ⭐ LoRA + IP-Adapter + Seed + ControlNet
    ↓
[Consistency Validator (85점)] ⭐ 일관성 검증
    ↓
[Image Sequence]
    ↓
[TTS Factory Bridge]  ⭐ 언어별 오디오 생성 (필요시)
    ↓
[Video Factory]       ⭐ 오디오 참조 립싱크 (옵션)
```

> 기존 6개 모듈(Normalizer, TopicGenerator, ArcBuilder, BudgetPlanner, HookEnhancer, SceneGenerator)은
> `UnifiedStoryCompiler`가 LLM 1회 호출로 대체. 폴백용으로 기존 모듈 유지.

## ⭐ 2026-04-11 결정: 상용 API 전환

**이미지/비디오 생성을 상용 API로 전환합니다.** 로컬 모델(SDXL)은 다인물 캐릭터 일관성 확보 불가.

```env
# 현재 설정 (상용 API)
IMAGE_PROVIDER=api
IMAGE_API_MODEL=stability
STABILITY_API_KEY=<발급 필요>

VIDEO_PROVIDER=api
VIDEO_API_MODEL=luma
LUMA_API_KEY=<발급 필요>
```

**구현된 API 클라이언트:**
- Stability SD 3.5: `infrastructure/api/providers/image/stability_sd35.py` (text-to-image + reference image)
- Luma (Ray/Kling/Veo/Sora): `infrastructure/api/providers/video/luma.py` (멀티모델)

**로컬 모델은 PC 업그레이드 후 재검토.** SDXL 로컬 테스트 결과는 memory 참조.

## 다국어 지원

`.env`의 `STORY_LANGUAGES`로 타겟 언어 설정 (쉼표 구분):
```env
STORY_LANGUAGES=ko        # 한국어만
STORY_LANGUAGES=ko,th     # 한국어 + 태국어 배치 생성
STORY_LANGUAGES=ko,th,vi  # 한국어 + 태국어 + 베트남어
```

컴파일러 `language` 파라미터로 언어 지정 시 해당 언어로 대본 생성:
```python
result = await compiler.compile(raw_story="...", language="th")
```

TTS는 언어별로 다른 모델 자동 로딩:
- ko → F5-TTS, th → F5-TTS-THAI, vi → (TODO), en → F5-TTS

## Provider/Model 스위칭

각 모듈(이미지/영상/TTS)은 `.env` 설정으로 로컬↔상용 API 전환:

```env
# 이미지
IMAGE_PROVIDER=local    # local | api
IMAGE_LOCAL_MODEL=sdxl  # sdxl | sd35
IMAGE_API_MODEL=stability  # stability | dalle

# 영상
VIDEO_PROVIDER=hybrid   # local | api | hybrid
VIDEO_LOCAL_MODEL=svd   # svd | framepack
VIDEO_API_MODEL=luma    # luma | runway | kling

# TTS
TTS_PROVIDER=local      # local | api | auto
TTS_LOCAL_MODEL=gpt_sovits  # gpt_sovits | f5tts | f5tts_thai
TTS_API_MODEL=azure     # azure | edge
```

Factory 패턴으로 설정에 따라 자동 선택:
```python
from infrastructure.image import create_image_generator
from infrastructure.video import create_video_generator
from infrastructure.tts import create_tts_engine

gen = create_image_generator()  # .env IMAGE_PROVIDER/MODEL 사용
```

## 주요 파일

### Story Compiler (통합)
```
infrastructure/story/
├── unified_compiler.py    # ⭐ LLM 1회 호출 통합 컴파일러 (메인)
├── short_drama_compiler.py # ⭐ 5축 조합 숏드라마 컴파일러 (Mode B)
├── story_spec.py          # StorySpec 엔티티
├── story_validator.py     # 검증 + Retry
├── format_render.py       # Shorts/Longform 변환
├── normalizer.py          # (폴백) 입력 정제
├── topic_generator.py     # (폴백) 주제 생성
├── arc_builder.py         # (폴백) 4-Act 구조
├── budget_planner.py      # (폴백) 예산 계획
├── hook_enhancer.py       # (폴백) Hook 강화 + 스코어링
└── scene_generator.py     # (폴백) Scene 생성
```

### API Config + Providers
```
config/
└── api_config.py          # ⭐ 모든 API 키/Provider/Model 중앙 관리

infrastructure/ai/
├── story_llm_provider.py  # ⭐ 통합 LLM Provider (.env 자동 사용)
├── claude_provider.py     # ClaudeProvider
└── openai_provider.py     # OpenAIProvider
```

### Factory 패턴 (이미지/영상/TTS)
```
infrastructure/
├── image/
│   ├── image_factory.py   # ⭐ create_image_generator(provider, model)
│   └── sdxl_generator.py  # SDXLGenerator + Face Authority + 프롬프트 청킹
├── video/
│   ├── video_factory.py   # ⭐ create_video_generator(provider, model)
│   └── ...
└── tts/
    ├── tts_config.py      # ⭐ 언어별 TTS 모델 설정
    ├── tts_factory_bridge.py # ⭐ create_tts_engine(language, provider, model)
    └── tts_factory.py     # 기존 TTSFactory
```

### Character Identity System
```
infrastructure/
├── consistency/
│   └── character_identity_engine.py  # 4요소 통합 관리
├── prompt/
│   └── prompt_compiler.py            # 프롬프트 컴파일 (청킹 허용)
├── render/
│   └── render_engine.py              # 4요소 동시 렌더링
└── validation/
    └── consistency_validator.py      # 85점 기준 검증
```

## 사용법

### 1. Story Compiler (통합) + 다국어

```python
from infrastructure.story import UnifiedStoryCompiler, TargetFormat

# StoryLLMProvider는 .env STORY_API_KEY 자동 사용
compiler = UnifiedStoryCompiler()  # llm_provider 자동 생성
result = await compiler.compile(
    raw_story="옛날 옛날에 호랑이 한 마리가 살았어요",  # 자유 형식
    target_format=TargetFormat.SHORTS,
    max_retries=2,
    language="ko",  # ko/th/vi/en/ja/zh
)

if result.success:
    spec = result.story_spec  # 완전한 StorySpec
    print(spec.title)          # LLM이 보강한 제목
    print(len(spec.scenes))    # 6~10개 Scene
    print(spec.duration)       # 20~35초
    print(result.hook_score)   # ≥6.0
```

### 1-1. Factory 패턴 (이미지/영상/TTS)

```python
from infrastructure.image import create_image_generator
from infrastructure.video import create_video_generator
from infrastructure.tts import create_tts_engine

# .env 설정에 따라 자동으로 모델 선택
image_gen = create_image_generator()         # local/sdxl
video_gen = create_video_generator()          # hybrid/svd+luma
tts_engine = create_tts_engine(language="th") # th → F5-TTS-THAI

# 명시적 지정도 가능
image_gen = create_image_generator(provider="api", model="stability")
```

### 1-2. Pipeline 실행

```python
from config.api_config import get_pipeline_config

config = get_pipeline_config()
# config["steps"] → ["image", "tts", "video"] or ["image", "video"]
# config["video_needs_audio"] → True/False
```

### 1-1. Story Compiler (기존 모듈 직접 사용, 폴백용)

```python
from infrastructure.story import (
    StoryNormalizer, TopicGenerator, ArcBuilder,
    BudgetPlanner, HookEnhancer, SceneGenerator,
    StoryValidator, StorySpec, TargetFormat
)

normalizer = StoryNormalizer()
normalized = normalizer.normalize("hero fights villain at night")

topic_gen = TopicGenerator()
topic = topic_gen.generate(normalized)

arc_builder = ArcBuilder()
arc = arc_builder.build(topic, normalized)

budget_planner = BudgetPlanner()
budget = budget_planner.plan("shorts")

hook_enhancer = HookEnhancer()
enhanced_hook, hook_score = hook_enhancer.enhance_and_score(arc.hook)

scene_gen = SceneGenerator()
scene_result = scene_gen.generate(arc, budget, topic, normalized)

story_spec = StorySpec(
    title="Story Title",
    genre="action",
    target=TargetFormat.SHORTS,
    duration=scene_result.total_duration,
    scenes=scene_result.scenes
)
```

### 2. Character Identity

```python
from infrastructure.consistency import CharacterIdentityEngine
from infrastructure.prompt import PromptCompiler
from infrastructure.render import RenderEngine
from infrastructure.validation import ConsistencyValidator

# 캐릭터 등록
identity = CharacterIdentityEngine()
identity.register(
    character_id="char_hero",
    lora_path="lora/character_v1.safetensors",
    reference_image="assets/ref/character.png",
    core_tokens="hooded hero, blue aura, pale face",
    seed=12345
)

# 프롬프트 컴파일 (77토큰 제한)
compiler = PromptCompiler()
prompt = compiler.compile(
    scene_description="hero stands on rooftop at night",
    character_tokens=identity.get("char_hero").core_tokens,
    style="disney_3d",
    emotion="tension",
    camera="close-up"
)

# 렌더링 (4요소 동시)
engine = RenderEngine(generator)
result = await engine.render_scene(
    scene, "char_hero", identity, compiler
)

# 일관성 검증 (85점 기준)
validator = ConsistencyValidator(threshold=85)
result = validator.validate_and_raise(images)
```

## 제약 조건

### Shorts
- 길이: 20~35초
- Scene 수: 6~10개
- Scene당 길이: 2~4초
- Hook: 3초 이내

### Longform
- 길이: 2~8분
- Scene 수: 20~60개

### Hook Score
- 기준: ≥ 6.0/10
- 항목: curiosity(2.5) + shock(2.5) + visual(2.5) + conflict(2.5)

### Consistency Score
- 기준: ≥ 85점
- 항목: face(40) + outfit(30) + color(30)

## Face Authority 렌더링 파라미터

> **핵심 원칙: 얼굴 = IP-Adapter 단일 소스, LoRA = 스타일만**

| 요소 | 역할 | 파라미터 | 권장 범위 |
|------|------|----------|-----------|
| IP-Adapter | **얼굴 고정 (Face Authority)** | scale | 0.7 ~ 0.9 |
| LoRA | 스타일만 (얼굴 관여 금지) | weight | 0.3 ~ 0.6 |
| ControlNet | 포즈 고정 | weight | 0.7 ~ 0.8 |
| Seed | 재현성 | seed | 고정값 |

### 금지 규칙
- 프롬프트에 얼굴 묘사 금지 ("beautiful face", "big eyes" 등)
- LoRA scale 0.7 이상 금지 (얼굴에 관여하므로)
- Video 단계에서 Face Anchor 재주입 필수
- Negative prompt에 "multiple characters", "crowd", "creatures" 금지 (인물 생성 억제)

## 프롬프트 청킹 (Prompt Chunking)

> **CLIP 77토큰 제한을 A1111 방식으로 우회**

### 동작 방식
1. 프롬프트를 75토큰(77-BOS-EOS) 단위로 분할
2. 각 청크 개별 인코딩 → 중복 BOS/EOS 제거 → 결합
3. SDXL 이중 인코더(CLIP-L + OpenCLIP-ViT) 각각 처리
4. **pos/neg 임베딩을 반드시 개별 텐서로 분리**하여 pipeline에 전달

### 주의사항 (버그 방지)
- ❌ `torch.cat([neg, pos])`로 사전 결합 금지 (나비 버그)
- ✅ `prompt_embeds`, `negative_prompt_embeds`를 별도 kwargs로 전달
- Pooled 임베딩도 pos/neg 분리 필수

### 다중 인물 프롬프트 전략
- **1인물**: appearance 토큰 포함 (디테일 보존)
- **2인물 이상**: appearance 토큰 제거, action에만 의존 (토큰 뒤섞임 방지)
- **SDXL 한계**: 3인 이상은 2명까지만 렌더링 (Regional Prompter 필요)

## 실패 조건 (자동 차단)

- ❌ Hook Score < 6.0
- ❌ Duration 제약 벗어남
- ❌ Scene 수 제약 벗어남
- ❌ Consistency Score < 85

## 환경 설정

```env
# .env
# 대본 생성 API (컴파일러 공통)
STORY_API_KEY=your_key
STORY_API_URL=https://api.z.ai/api/anthropic/v1/messages
STORY_MODEL=glm-5
STORY_MAX_TOKENS=4096

# 비디오 생성 API (별도)
VIDEO_API_KEY=
VIDEO_API_URL=
VIDEO_MODEL=

# 다국어 설정 (쉼표 구분)
STORY_LANGUAGES=ko

# 이미지 생성 (로컬 SDXL)
SD_MODEL=stabilityai/stable-diffusion-xl-base-1.0
SD_DEVICE=cuda
SD_LOW_VRAM=true

IP_ADAPTER_ENABLED=true
CHARACTER_CACHE_DIR=data/character_cache

# Provider/Model 스위칭
IMAGE_PROVIDER=local     # local | api
IMAGE_LOCAL_MODEL=sdxl   # sdxl | sd35
IMAGE_API_MODEL=stability # stability | dalle

VIDEO_PROVIDER=hybrid    # local | api | hybrid
VIDEO_LOCAL_MODEL=svd    # svd | framepack
VIDEO_API_MODEL=luma     # luma | runway | kling

TTS_PROVIDER=local       # local | api | auto
TTS_LOCAL_MODEL=gpt_sovits  # gpt_sovits | f5tts | f5tts_thai
TTS_API_MODEL=azure      # azure | edge

# Pipeline 설정
TTS_ENABLED=true           # TTS 생성 여부
LIPSYNC_ENABLED=true       # 립싱크 사용 여부
LIPSYNC_MODE=auto          # auto | forced | disabled
```

## 테스트

```bash
# 통합 컴파일러 테스트
python -c "
from infrastructure.story import UnifiedStoryCompiler, CompileResult
from infrastructure.story.story_spec import StorySpec, TargetFormat
print('UnifiedStoryCompiler import OK')
"

# 기존 Story Pipeline 테스트
python tests/test_story_pipeline.py

# 통합 테스트
python -c "
from infrastructure.story import UnifiedStoryCompiler
from infrastructure.consistency import CharacterIdentityEngine
print('All imports OK')
"
```

## 메모리 파일

- `~/.claude/projects/D--AI-Video/memory/implementation_status.md` - 구현 상태
- `~/.claude/projects/D--AI-Video/memory/technical_decisions.md` - 기술 결정
- `~/.claude/projects/D--AI-Video/memory/project_goals.md` - 프로젝트 목표
