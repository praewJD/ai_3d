# Autonomous Creator - 워크플로우 가이드

## 개요

이 문서는 Autonomous Creator 시스템의 전체 워크플로우를 단계별로 설명합니다.

---

## 전체 파이프라인

    INPUT STORY --> PARSE SCENES --> PROMPT GEN --> IMAGE GEN --> VIDEO GEN --> COMPOSE FINAL
         |              |               |              |              |
         v              v               v              v              v
    story.json     scenes[]       prompts[]      images[]       final.mp4

---

## Step 1: 스토리 입력 및 파싱

목적: 자연어 스토리를 구조화된 장면 데이터로 변환

입력: 텍스트 스토리
처리: LLM(Claude)이 장면 분할
출력: Scene 객체 배열 (description, characters, location, mood, narration)

---

## Step 2: AI 프롬프트 생성

목적: 각 장면을 AI 프롬프트로 변환

처리 과정:
1. 시리즈 스타일 로드 (Disney 3D animation style, Pixar quality)
2. 캐릭터 프롬프트 조합 (외형 + 표정 + 포즈 + 의상)
3. 장소 프롬프트 추가
4. 분위기/시간 태그
5. 품질 태그 (masterpiece, best quality)

---

## Step 3: 이미지 생성

목적: 프롬프트로부터 고품질 이미지 생성

처리 과정:
- StyleConsistencyManager 사용
- IP-Adapter로 캐릭터 일관성 유지
- SD 3.5 또는 Stability AI 사용

---

## Step 4: 영상 생성

목적: 이미지로부터 자연스러운 모션 영상 생성

API 선택 전략:
- all_api: 모든 장면 API 사용 (최고 품질, 높은 비용)
- key_scenes_api: 핵심 장면만 API (균형)
- smart_hybrid: AI가 자동 선택 (권장)
- local_first: 로컬 우선, 실패 시 API (저렴)

Luma API 워크플로우:
1. 이미지 업로드
2. POST /generations 호출
3. 폴링으로 상태 확인
4. 완료 시 영상 다운로드

---

## Step 5: TTS 내레이션

목적: 장면 설명을 자연스러운 음성으로 변환

Provider:
- Azure TTS (고품질, 유료)
- Edge TTS (좋은 품질, 무료)

---

## Step 6: 최종 합성

목적: 영상과 오디오를 완성된 비디오로 합성

처리:
1. 각 장면 비디오/오디오 로드
2. 길이 동기화
3. 장면 간 전환 효과 (fade, crossfade)
4. 최종 렌더링 (1920x1080, 30fps, H.264)

---

## 체크포인트 시스템

목적: 파이프라인 중단 시 복구 가능

PipelineStep:
- STORY_LOADED
- PROMPTS_GENERATED
- IMAGES_GENERATED
- VIDEOS_GENERATED
- AUDIO_GENERATED
- COMPLETED

복구: 저장된 체크포인트에서 실패한 단계부터 재시작

---

## 에러 처리

- API Rate Limit: Wait & Retry
- API Error: Fallback to other provider
- Network Error: Retry with exponential backoff
- Generation Fail: Regenerate with adjusted params

---

## 시리즈 관리

1. 시리즈 생성 (name, art_style, world_setting, locations)
2. 캐릭터 추가 (appearance, expressions, poses, outfits)
3. 에피소드 생성 (스토리 입력 -> 파이프라인 실행)

---

## 빠른 시작

    from autonomous_creator import VideoCreator

    creator = VideoCreator(api_key="luma_...", style="disney_3d")
    
    series = await creator.create_series(
        name="마법의 숲 모험",
        art_style="Disney 3D animation style, Pixar quality"
    )
    
    video = await creator.create(
        story="어린 소녀가 마법의 숲에서...",
        series_id=series.id
    )

---

## 관련 문서

- ARCHITECTURE.md - 시스템 아키텍처
- CONFIGURATION.md - 설정 가이드
