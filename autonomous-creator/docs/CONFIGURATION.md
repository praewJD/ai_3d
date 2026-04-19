# Autonomous Creator 설정 가이드

이 문서는 Autonomous Creator 시스템의 모든 설정 옵션에 대한 포괄적인 가이드입니다.

---

## 목차

1. [환경 변수 설정 (.env)](#1-환경-변수-settings-env)
2. [비용 최적화 전략](#2-비용-최적화-전략)
3. [비디오 생성 모델](#3-비디오-생성-모델)
4. [Disney 3D 스타일 설정](#4-disney-3d-스타일-설정)
5. [캐릭터 시스템](#5-캐릭터-시스템)
6. [예제 설정 파일](#6-예제-설정-파일)

---

## 1. 환경 변수 설정 (.env)

### 1.1 스타일 설정

| 변수명 | 설명 | 기본값 | 허용 값 |
|--------|------|--------|---------|
| `DEFAULT_ART_STYLE` | 기본 아트 스타일 | `disney_3d` | `disney_3d`, `anime`, `realistic`, `cartoon` |
| `ANIME_3D_LIGHTING` | 애니메이션 3D 조명 품질 | `standard` | `low`, `standard`, `high`, `cinematic` |
| `ANIME_3D_RENDER_QUALITY` | 렌더링 품질 | `medium` | `draft`, `medium`, `high`, `ultra` |

```env
# 스타일 설정 예시
DEFAULT_ART_STYLE=disney_3d
ANIME_3D_LIGHTING=cinematic
ANIME_3D_RENDER_QUALITY=high
```

### 1.2 비용 최적화 설정

| 변수명 | 설명 | 기본값 | 허용 값 |
|--------|------|--------|---------|
| `VIDEO_GENERATION_STRATEGY` | 비디오 생성 전략 | `key_scenes_api` | `all_api`, `key_scenes_api`, `smart_hybrid`, `local_first` |
| `KEY_SCENE_RATIO` | 핵심 장면 비율 | `0.3` | `0.1` ~ `1.0` |
| `MONTHLY_BUDGET_USD` | 월간 예산 (USD) | `100` | 양의 정수 |
| `AUTO_COST_SAVING` | 자동 비용 절감 모드 | `true` | `true`, `false` |

```env
# 비용 최적화 설정 예시
VIDEO_GENERATION_STRATEGY=key_scenes_api
KEY_SCENE_RATIO=0.3
MONTHLY_BUDGET_USD=100
AUTO_COST_SAVING=true
```

### 1.3 Luma API 설정

| 변수명 | 설명 | 기본값 | 필수 여부 |
|--------|------|--------|-----------|
| `LUMA_API_KEY` | Luma API 키 | - | 필수 |
| `LUMA_DEFAULT_MODEL` | 기본 모델 | `ray-3.14` | 선택 |
| `LUMA_DEFAULT_RESOLUTION` | 기본 해상도 | `1080p` | 선택 |

```env
# Luma API 설정 예시
LUMA_API_KEY=your_luma_api_key_here
LUMA_DEFAULT_MODEL=ray-3.14
LUMA_DEFAULT_RESOLUTION=1080p
```

### 1.4 Claude/OpenAI API 설정

| 변수명 | 설명 | 필수 여부 |
|--------|------|-----------|
| `ANTHROPIC_API_KEY` | Anthropic Claude API 키 | 권장 |
| `OPENAI_API_KEY` | OpenAI API 키 | 권장 |
| `OPENAI_ORG_ID` | OpenAI 조직 ID | 선택 |

```env
# Claude/OpenAI API 설정 예시
ANTHROPIC_API_KEY=sk-ant-your_key_here
OPENAI_API_KEY=sk-your_openai_key_here
OPENAI_ORG_ID=org-your_org_id
```

### 1.5 TTS (음성 합성) 설정

| 변수명 | 설명 | 기본값 | 필수 여부 |
|--------|------|--------|-----------|
| `AZURE_TTS_KEY` | Azure TTS 구독 키 | - | 선택 |
| `AZURE_TTS_REGION` | Azure 지역 | `koreacentral` | 선택 |
| `GPT_SOVITS_URL` | GPT-SoVITS 서버 URL | - | 선택 |
| `GPT_SOVITS_DEFAULT_SPEAKER` | 기본 화자 | `default` | 선택 |

```env
# TTS 설정 예시
AZURE_TTS_KEY=your_azure_tts_key
AZURE_TTS_REGION=koreacentral
GPT_SOVITS_URL=http://localhost:9880
GPT_SOVITS_DEFAULT_SPEAKER=female_01
```

---

## 2. 비용 최적화 전략

### 2.1 전략 개요

| 전략명 | 설명 | 비용 | 품질 | 권장 사용 사례 |
|--------|------|------|------|----------------|
| `all_api` | 모든 장면에 API 사용 | 높음 | 최상 | 프리미엄 콘텐츠 |
| `key_scenes_api` | 핵심 장면만 API 사용 | 중간 | 높음 | 일반 콘텐츠 (권장) |
| `smart_hybrid` | 자동 의사결정 | 가변 | 높음 | 자동화된 프로덕션 |
| `local_first` | 로컬 우선, API 백업 | 낮음 | 중간 | 비용 절감 우선 |

### 2.2 상세 설명

#### all_api
```python
# 모든 장면을 API로 생성
strategy = "all_api"
# 장면당 비용: 평균 $0.50 ~ $2.00
# 품질: 일관된 최고 품질
```

- **장점**: 일관된 최고 품질, 빠른 처리
- **단점**: 높은 비용
- **적합**: 상업용 프리미엄 콘텐츠, 예산 제한 없는 프로젝트

#### key_scenes_api (권장)
```python
# 핵심 장면(30%)만 API, 나머지는 로컬
strategy = "key_scenes_api"
key_scene_ratio = 0.3  # 전체의 30%만 API 사용
# 예상 비용 절감: 60-70%
```

- **장점**: 비용 대비 품질 최적화
- **단점**: 장면간 품질 차이 가능
- **적합**: 일반 유튜브/소셜 미디어 콘텐츠

#### smart_hybrid
```python
# AI가 장면별로 최적 방식 결정
strategy = "smart_hybrid"
# 복잡한 장면 → API
# 단순한 장면 → 로컬
```

- **장점**: 자동 최적화, 유연한 대응
- **단점**: 예측 어려움
- **적합**: 대량 자동화 프로덕션

#### local_first
```python
# 로컬 생성 우선, 실패 시 API 백업
strategy = "local_first"
# 최대 비용 절감
```

- **장점**: 최대 비용 절감
- **단점**: 낮은 품질, 긴 처리 시간
- **적합**: 테스트, 초안, 예산 제한 프로젝트

### 2.3 전략 선택 가이드

```
┌─────────────────────────────────────────────────────────────┐
│                    예산 →                                    │
│  낮음                  중간                  높음            │
├─────────────┬─────────────────┬─────────────────────────────┤
│ local_first │ key_scenes_api  │ all_api                     │
│             │                 │                             │
│ smart_hybrid│ smart_hybrid    │ key_scenes_api              │
│             │                 │                             │
│ (품질 낮음)  │ (균형)          │ (최고 품질)                  │
└─────────────┴─────────────────┴─────────────────────────────┘
```

---

## 3. 비디오 생성 모델

### 3.1 모델 비교표

| 모델명 | 특화 분야 | 크레딧/초 | 최대 길이 | 해상도 | 권장 용도 |
|--------|-----------|-----------|----------|--------|-----------|
| `kling-2.6` | 아시아 콘텐츠 | 29 | 10초 | 1080p | 한국/일본/중국 스타일 |
| `ray-3.14` | Luma 네이티브 | 80 | 5초 | 1080p | 고품질 일반 용도 |
| `veo-3` | Google Veo | 140 | 8초 | 4K | 시네마틱/프리미엄 |
| `sora-2` | OpenAI Sora | 35 | 15초 | 1080p | 긴 장면/스토리텔링 |

### 3.2 모델 상세 설명

#### kling-2.6
```yaml
모델: kling-2.6
제공사: Kuaishou
크레딧 소모: 29 credits/second
최대 길이: 10초
해상도: 720p, 1080p

특징:
  - 아시아 스타일 콘텐츠에 최적화
  - 애니메이션 스타일 우수
  - 인물 묘사 정확도 높음
  - 가성비 최고

권장 장면:
  - 한국/일본/중국 캐릭터
  - 애니메이션 스타일
  - 일상적인 장면
```

#### ray-3.14
```yaml
모델: ray-3.14
제공사: Luma AI
크레딧 소모: 80 credits/second
최대 길이: 5초
해상도: 720p, 1080p

특징:
  - Luma AI 네이티브 모델
  - 자연스러운 모션
  - 고품질 조명
  - 사실적 텍스처

권장 장면:
  - 자연/실외 장면
  - 복잡한 조명
  - 사실적 콘텐츠
```

#### veo-3
```yaml
모델: veo-3
제공사: Google
크레딧 소모: 140 credits/second
최대 길이: 8초
해상도: 1080p, 4K

특징:
  - 최고 품질
  - 4K 지원
  - 시네마틱 비주얼
  - 복잡한 장면 처리

권장 장면:
  - 오프닝/엔딩
  - 핵심 드라마 장면
  - 프리미엄 콘텐츠
```

#### sora-2
```yaml
모델: sora-2
제공사: OpenAI
크레딧 소모: 35 credits/second
최대 길이: 15초
해상도: 720p, 1080p

특징:
  - 긴 장면 생성 가능
  - 스토리텔링에 적합
  - 자연스러운 전환
  - 일관된 캐릭터

권장 장면:
  - 연속적인 액션
  - 대화 장면
  - 스토리 진행
```

### 3.3 모델 선택 코드 예시

```python
from autonomous_creator import VideoGenerator

# 모델 설정
generator = VideoGenerator(
    model="kling-2.6",  # 모델 선택
    resolution="1080p",
    fps=24
)

# 장면별 모델 선택
scenes = [
    {"type": "action", "model": "veo-3"},      # 액션 장면: 고품질
    {"type": "dialogue", "model": "sora-2"},   # 대화 장면: 긴 길이
    {"type": "casual", "model": "kling-2.6"},  # 일상 장면: 가성비
]

for scene in scenes:
    generator.generate(scene)
```

---

## 4. Disney 3D 스타일 설정

### 4.1 조명 프리셋

| 프리셋명 | 설명 | 적합 장면 |
|----------|------|-----------|
| `studio` | 스튜디오 조명 (기본값) | 일반적인 장면 |
| `golden_hour` | 황금시간대 | 감성적인 야외 장면 |
| `dramatic` | 드라마틱 조명 | 긴장감 있는 장면 |
| `soft` | 부드러운 조명 | 로맨틱/따뜻한 장면 |
| `backlight` | 역광 조명 | 실루엣/드라마틱 |
| `rim` | 림 라이트 | 윤곽 강조 |

```python
# 조명 설정 예시
lighting_config = {
    "preset": "golden_hour",
    "intensity": 0.8,      # 조명 강도 (0.0 ~ 1.0)
    "color_temp": 5500,    # 색온도 (Kelvin)
    "shadow_softness": 0.6 # 그림자 부드러움
}
```

### 4.2 쉐이더 옵션

```yaml
# 쉐이더 설정 구조
shader:
  type: disney_pbr  # Physical Based Rendering
  
  # 서브서피스 스캐터링 (피부 표현)
  subsurface:
    enabled: true
    radius: 0.5
    color: "#ffe4c4"
  
  # 메탈릭 효과
  metallic:
    enabled: false
    value: 0.0
  
  # 거칠기
  roughness:
    value: 0.3
  
  # 크리어코트 (눈, 유리)
  clearcoat:
    enabled: false
    intensity: 0.0
  
  # 시스 효과
  sheen:
    enabled: true
    intensity: 0.2
    color: "#ffffff"
```

### 4.3 품질 레벨

| 레벨 | 해상도 | 렌더링 시간 | 파일 크기 | 권장 용도 |
|------|--------|-------------|-----------|-----------|
| `draft` | 480p | 1x | 작음 | 테스트/미리보기 |
| `medium` | 720p | 2x | 중간 | 일반 콘텐츠 |
| `high` | 1080p | 4x | 큼 | 고품질 콘텐츠 |
| `ultra` | 4K | 8x | 매우 큼 | 시네마틱/프리미엄 |

```python
# 품질 레벨 설정
quality_settings = {
    "draft": {
        "resolution": "480p",
        "antialiasing": "fxaa",
        "texture_quality": "low",
        "shadow_quality": "low"
    },
    "medium": {
        "resolution": "720p",
        "antialiasing": "taa",
        "texture_quality": "medium",
        "shadow_quality": "medium"
    },
    "high": {
        "resolution": "1080p",
        "antialiasing": "msaa_4x",
        "texture_quality": "high",
        "shadow_quality": "high"
    },
    "ultra": {
        "resolution": "4k",
        "antialiasing": "msaa_8x",
        "texture_quality": "ultra",
        "shadow_quality": "ultra"
    }
}
```

### 4.4 Disney 3D 스타일 완전 설정 예시

```python
disney_3d_config = {
    "style": {
        "name": "disney_3d",
        "version": "2.0"
    },
    
    "lighting": {
        "preset": "golden_hour",
        "intensity": 0.85,
        "color_temp": 5500,
        "shadow_softness": 0.7,
        "ambient_occlusion": True,
        "global_illumination": True
    },
    
    "shader": {
        "type": "disney_pbr",
        "subsurface": {
            "enabled": True,
            "radius": 0.5,
            "color": "#ffe4c4"
        },
        "roughness": 0.25,
        "sheen": {
            "enabled": True,
            "intensity": 0.15
        }
    },
    
    "render": {
        "quality": "high",
        "resolution": "1080p",
        "fps": 24,
        "motion_blur": True,
        "depth_of_field": True
    },
    
    "post_processing": {
        "bloom": 0.3,
        "vignette": 0.1,
        "color_grading": "warm",
        "film_grain": 0.05
    }
}
```

---

## 5. 캐릭터 시스템

### 5.1 캐릭터 타입

| 타입 | 설명 | API 크레딧 | 일관성 |
|------|------|------------|--------|
| `protagonist` | 주인공 | 높음 | 최고 |
| `supporting` | 조연 | 중간 | 높음 |
| `animal` | 동물 캐릭터 | 중간 | 높음 |
| `npc` | 배경 캐릭터 | 낮음 | 중간 |

### 5.2 캐릭터 설정 구조

```python
character_config = {
    # 기본 정보
    "id": "char_001",
    "name": "소피아",
    "type": "protagonist",  # protagonist, supporting, animal, npc
    
    # 외형 설정
    "appearance": {
        "template": "young_female_01",  # 외형 템플릿
        "age": "20s",
        "gender": "female",
        "ethnicity": "korean",
        
        # 얼굴 특징
        "face": {
            "shape": "oval",
            "eyes": {
                "shape": "almond",
                "color": "#3d2314",
                "size": "medium"
            },
            "nose": "small",
            "lips": "medium",
            "skin_tone": "#f5deb3"
        },
        
        # 헤어스타일
        "hair": {
            "style": "long_wavy",
            "color": "#1a1a1a",
            "length": "long"
        },
        
        # 체형
        "body": {
            "height": "average",
            "build": "slim"
        }
    },
    
    # 의상 설정
    "outfit": {
        "base": "casual_summer",
        "top": "white_blouse",
        "bottom": "denim_shorts",
        "accessories": ["necklace_silver", "watch"]
    },
    
    # 표정 설정
    "expressions": {
        "default": "neutral",
        "available": ["happy", "sad", "surprised", "angry", "neutral"]
    },
    
    # 포즈 설정
    "poses": {
        "default": "standing_relaxed",
        "available": ["standing_relaxed", "sitting", "walking", "running"]
    }
}
```

### 5.3 외형 템플릿

#### 여성 캐릭터 템플릿
```yaml
female_templates:
  young_female_01:
    description: "젊은 여성 - 기본"
    age_range: "20-25"
    face_shape: "oval"
    
  young_female_02:
    description: "젊은 여성 - 둥근 얼굴"
    age_range: "20-25"
    face_shape: "round"
    
  adult_female_01:
    description: "성인 여성 - 기본"
    age_range: "30-40"
    face_shape: "oval"
    
  elderly_female_01:
    description: "노인 여성"
    age_range: "60+"
    face_shape: "oval"
```

#### 남성 캐릭터 템플릿
```yaml
male_templates:
  young_male_01:
    description: "젊은 남성 - 기본"
    age_range: "20-25"
    face_shape: "square"
    
  young_male_02:
    description: "젊은 남성 - 갸름한 얼굴"
    age_range: "20-25"
    face_shape: "oval"
    
  adult_male_01:
    description: "성인 남성 - 기본"
    age_range: "30-40"
    face_shape: "square"
    
  elderly_male_01:
    description: "노인 남성"
    age_range: "60+"
    face_shape: "oval"
```

### 5.4 의상 변형

```python
outfit_variants = {
    # 계절별 의상
    "seasonal": {
        "spring": ["light_jacket", "jeans", "sneakers"],
        "summer": ["tshirt", "shorts", "sandals"],
        "autumn": ["sweater", "pants", "boots"],
        "winter": ["coat", "jeans", "winter_boots"]
    },
    
    # 상황별 의상
    "situational": {
        "casual": ["casual_shirt", "jeans", "sneakers"],
        "formal": ["suit", "dress_shirt", "dress_shoes"],
        "sportswear": ["athletic_shirt", "joggers", "running_shoes"],
        "sleepwear": ["pajamas", "slippers"]
    },
    
    # 직업별 의상
    "occupational": {
        "student": ["school_uniform", "backpack"],
        "office_worker": ["business_casual", "laptop_bag"],
        "chef": ["chef_uniform", "apron"],
        "doctor": ["white_coat", "stethoscope"]
    }
}
```

### 5.5 표정 및 포즈 설정

#### 표정 설정
```python
expression_settings = {
    "happy": {
        "intensity_range": [0.0, 1.0],
        "blend_shapes": {
            "mouth_smile": 0.8,
            "eye_squint": 0.3,
            "cheek_raise": 0.5
        }
    },
    "sad": {
        "intensity_range": [0.0, 1.0],
        "blend_shapes": {
            "mouth_frown": 0.7,
            "eyebrow_inner_up": 0.6,
            "eye_tear": 0.4
        }
    },
    "surprised": {
        "intensity_range": [0.0, 1.0],
        "blend_shapes": {
            "eyebrow_up": 0.9,
            "eye_wide": 0.8,
            "mouth_open": 0.5
        }
    },
    "angry": {
        "intensity_range": [0.0, 1.0],
        "blend_shapes": {
            "eyebrow_furrow": 0.8,
            "eye_squint": 0.5,
            "mouth_frown": 0.6
        }
    },
    "neutral": {
        "intensity_range": [0.0, 1.0],
        "blend_shapes": {}
    }
}
```

#### 포즈 설정
```python
pose_settings = {
    "standing_relaxed": {
        "description": "편안하게 서있는 자세",
        "joints": {
            "spine_curve": 0.0,
            "shoulder_relax": 0.5,
            "arm_position": "natural",
            "leg_stance": "shoulder_width"
        }
    },
    "sitting": {
        "description": "앉아있는 자세",
        "variants": ["chair", "ground", "couch"]
    },
    "walking": {
        "description": "걷는 동작",
        "speed_range": [0.5, 2.0],  # m/s
        "style": ["casual", "hurried", "confident"]
    },
    "running": {
        "description": "달리는 동작",
        "speed_range": [2.0, 5.0],  # m/s
        "style": ["sprint", "jog", "chase"]
    }
}
```

---

## 6. 예제 설정 파일

### 6.1 완전한 .env 파일 예시

```env
# ===========================================
# Autonomous Creator 환경 설정
# ===========================================

# -------------------------------------------
# 스타일 설정
# -------------------------------------------
DEFAULT_ART_STYLE=disney_3d
ANIME_3D_LIGHTING=cinematic
ANIME_3D_RENDER_QUALITY=high

# -------------------------------------------
# 비용 최적화 설정
# -------------------------------------------
VIDEO_GENERATION_STRATEGY=key_scenes_api
KEY_SCENE_RATIO=0.3
MONTHLY_BUDGET_USD=100
AUTO_COST_SAVING=true

# -------------------------------------------
# Luma API 설정
# -------------------------------------------
LUMA_API_KEY=luma_live_xxxxxxxxxxxx
LUMA_DEFAULT_MODEL=ray-3.14
LUMA_DEFAULT_RESOLUTION=1080p

# -------------------------------------------
# Claude API 설정
# -------------------------------------------
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx

# -------------------------------------------
# OpenAI API 설정
# -------------------------------------------
OPENAI_API_KEY=sk-xxxxxxxxxxxx
OPENAI_ORG_ID=org-xxxxxxxx

# -------------------------------------------
# TTS (음성 합성) 설정
# -------------------------------------------
AZURE_TTS_KEY=xxxxxxxxxxxxxxxx
AZURE_TTS_REGION=koreacentral
GPT_SOVITS_URL=http://localhost:9880
GPT_SOVITS_DEFAULT_SPEAKER=female_01

# -------------------------------------------
# 추가 설정
# -------------------------------------------
LOG_LEVEL=INFO
OUTPUT_DIR=./output
TEMP_DIR=./temp
```

### 6.2 Python 설정 코드 예시

```python
"""
Autonomous Creator 설정 예시
"""
from autonomous_creator import (
    Creator,
    Character,
    Scene,
    VideoConfig,
    StyleConfig
)

# 1. 기본 설정
config = Creator.load_config(
    env_file=".env",
    style="disney_3d"
)

# 2. 캐릭터 정의
protagonist = Character(
    id="sophia",
    name="소피아",
    type="protagonist",
    appearance={
        "template": "young_female_01",
        "hair": {"style": "long_wavy", "color": "#1a1a1a"},
        "skin_tone": "#f5deb3"
    },
    outfit={
        "base": "casual_summer",
        "top": "white_blouse",
        "bottom": "denim_shorts"
    }
)

# 3. 장면 정의
scene = Scene(
    id="scene_001",
    description="소피아가 공원에서 산책한다",
    characters=[protagonist],
    setting={
        "location": "park",
        "time_of_day": "afternoon",
        "weather": "sunny"
    },
    style=StyleConfig(
        art_style="disney_3d",
        lighting="golden_hour",
        quality="high"
    )
)

# 4. 비디오 생성
creator = Creator(config)
video = creator.generate_video(
    scenes=[scene],
    model="kling-2.6",
    strategy="key_scenes_api"
)

# 5. 결과 저장
video.save("./output/episode_01.mp4")
```

### 6.3 YAML 설정 파일 예시

```yaml
# config.yaml - Autonomous Creator 설정

# 프로젝트 기본 설정
project:
  name: "내 AI 동화"
  version: "1.0.0"
  output_dir: "./output"

# 스타일 설정
style:
  default: disney_3d
  lighting:
    preset: golden_hour
    intensity: 0.85
  render:
    quality: high
    resolution: 1080p
    fps: 24

# 비용 최적화
cost_optimization:
  strategy: key_scenes_api
  key_scene_ratio: 0.3
  monthly_budget: 100  # USD
  auto_saving: true

# 비디오 생성 모델
models:
  default: kling-2.6
  fallback: ray-3.14
  scene_overrides:
    action: veo-3
    dialogue: sora-2

# 캐릭터 기본 설정
characters:
  default_type: protagonist
  consistency_level: high
  
# TTS 설정
tts:
  engine: azure
  default_speaker: female_01
  language: ko-KR
  
# 로깅 설정
logging:
  level: INFO
  file: ./logs/creator.log
```

---

## 부록: 빠른 참조

### 환경 변수 요약

```
# 스타일
DEFAULT_ART_STYLE=disney_3d
ANIME_3D_LIGHTING=standard
ANIME_3D_RENDER_QUALITY=medium

# 비용
VIDEO_GENERATION_STRATEGY=key_scenes_api
KEY_SCENE_RATIO=0.3
MONTHLY_BUDGET_USD=100
AUTO_COST_SAVING=true

# API 키
LUMA_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
OPENAI_API_KEY=your_key

# TTS
AZURE_TTS_KEY=your_key
GPT_SOVITS_URL=http://localhost:9880
```

### 모델 빠른 선택

```
아시아/애니메이션 → kling-2.6 (29 credits/sec)
일반/고품질     → ray-3.14 (80 credits/sec)
프리미엄/4K    → veo-3 (140 credits/sec)
긴 장면/스토리  → sora-2 (35 credits/sec)
```

---

*최종 업데이트: 2026년 4월 2일*
*버전: 1.0.0*
