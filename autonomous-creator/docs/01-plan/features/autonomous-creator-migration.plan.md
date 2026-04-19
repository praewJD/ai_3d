# Plan: autonomous-creator Migration

> **Feature**: autonomous-creator-migration
> **Created**: 2026-03-31
> **Status**: Planning

---

## Executive Summary

| Perspective | Description |
|-------------|-------------|
| **Problem** | autonomous-creator 프로젝트가 AI영상자동화 폴더에 있어 AI 비디오 관련 프로젝트들이 분산되어 있음 |
| **Solution** | D:\AI-Video로 폴더 이동 후 모든 경로 참조 업데이트 |
| **Function UX Effect** | 모든 AI 비디오 프로젝트가 D:\AI-Video에 통합되어 관리 용이성 향상 |
| **Core Value** | 프로젝트 구조 정리 및 메모리/코드 일관성 유지 |

---

## Context Anchor

| Key | Value |
|-----|-------|
| **WHY** | AI 비디오 관련 프로젝트를 한 곳(D:\AI-Video)에 통합 관리 |
| **WHO** | 개발자 (JN) |
| **RISK** | 경로 누락으로 인한 스크립트 실행 실패 |
| **SUCCESS** | 모든 파일이 정상 작동, 메모리 경로 업데이트 완료 |
| **SCOPE** | 폴더 이동 + 14개 경로 참조 업데이트 + 메모리 업데이트 |

---

## 1. Current State Analysis

### 1.1 Source Location
```
D:\AI-Video\autonomous-creator\
├── .claude/              # Claude Code 설정
├── config/               # 설정 파일
├── core/                 # 핵심 모듈
├── docs/                 # 문서
├── fish-speech-*/        # TTS 관련 (3개 폴더)
├── infrastructure/       # 인프라 코드
├── interfaces/           # API/CLI 인터페이스
├── models/               # 모델 파일
├── output/               # 출력 폴더
├── outputs/              # 출력 폴더 (중복)
├── s1-mini/              # 모델
├── tests/                # 테스트
├── thai/                 # 태국어 TTS 설정
├── *.py                  # Python 스크립트 (8개)
└── *.md                  # 문서 (2개)
```

### 1.2 Target Location
```
D:\AI-Video\
└── FramePack/            # 기존 프로젝트
```

### 1.3 Path References Found (14 occurrences in 11 files)

| File | Line | Current Path |
|------|------|--------------|
| test_full_pipeline.py | 23 | `D:\AI-Video\autonomous-creator\output\full_pipeline_test` |
| test_full_pipeline.py | 148 | `D:\AI-Video\autonomous-creator\output\output.wav` |
| test_framepack.py | 84 | `D:\AI-Video\autonomous-creator\output\video_test` |
| test_voice_clone_compare.py | 19 | `D:\AI-Video\autonomous-creator\output\voice_compare` |
| test_thai_pipeline.py | 19 | `D:\AI-Video\autonomous-creator\output\thai_test` |
| thai_tts_generator.py | 22 | `D:\AI-Video\autonomous-creator\output` |
| thai_tts_f5.py | 36 | `D:\AI-Video\autonomous-creator\output` |
| thai_tts_f5_v2.py | 21 | `C:\Users\JN\AI영상자동화\thai` |
| thai_tts_f5_v2.py | 37 | `C:\Users\JN\AI영상자동화\output` |
| generate_hearono_sd35.py | 18 | `D:\AI-Video\autonomous-creator\output\hearono_sd35` |
| generate_hearono_episode.py | 127 | `D:\AI-Video\autonomous-creator\output\output.wav` |
| generate_hearono_episode.py | 148 | `D:\AI-Video\autonomous-creator\output\output.wav` |
| thai/F5TTS_Thai.yaml | 23 | `D:\AI-Video\autonomous-creator\thai\vocab.txt` |
| thai_tts_guide.md | - | 문서 내 경로 참조 |

---

## 2. Migration Plan

### 2.1 Phase 1: Folder Move
- **Action**: Move entire `autonomous-creator` folder to `D:\AI-Video\`
- **Command**: `mv "C:/Users/JN/AI영상자동화/autonomous-creator" "D:/AI-Video/autonomous-creator"`
- **Result**: `D:\AI-Video\autonomous-creator\`

### 2.2 Phase 2: Code Path Updates (11 files)

**Path Replacement Pattern:**
```
OLD: C:\Users\JN\AI영상자동화\autonomous-creator
NEW: D:\AI-Video\autonomous-creator

OLD: C:/Users/JN/AI영상자동화/autonomous-creator
NEW: D:/AI-Video/autonomous-creator

OLD: C:\Users\JN\AI영상자동화\output
NEW: D:\AI-Video\autonomous-creator\output

OLD: C:\Users\JN\AI영상자동화\thai
NEW: D:\AI-Video\autonomous-creator\thai
```

### 2.3 Phase 3: Claude Memory Updates

**Files to Update:**
1. `~/.claude/projects/C--Users-JN/memory/MEMORY.md`
   - 모든 `autonomous-creator` 경로 참조 업데이트

2. Project memory folder rename (optional):
   - `C--Users-JN-AI------autonomous-creator` → 새 경로용 폴더 생성됨

### 2.4 Phase 4: Verification
- Python 스크립트 import 테스트
- 주요 스크립트 실행 테스트
- 경로 참조 누락 검색

---

## 3. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| 경로 누락 | Medium | High | grep로 전체 검색 후 수정 |
| Python import 실패 | Low | Medium | 상대 경로 사용 권장 |
| 메모리 불일치 | Low | Low | 메모리 파일 직접 수정 |
| 기존 데이터 손실 | Very Low | High | 이동 전 백업 |

---

## 4. Success Criteria

- [ ] 폴더가 `D:\AI-Video\autonomous-creator`로 이동 완료
- [ ] 14개 경로 참조 모두 업데이트
- [ ] MEMORY.md 내 경로 업데이트
- [ ] Python 스크립트 정상 실행
- [ ] `grep`으로 누락된 경로 없음 확인

---

## 5. Estimated Effort

| Task | Effort |
|------|--------|
| 폴더 이동 | 1 min |
| 코드 경로 업데이트 (11 files) | 5 min |
| 메모리 업데이트 | 3 min |
| 검증 | 2 min |
| **Total** | **~11 min** |

---

## 6. Next Steps

1. `/pdca design autonomous-creator-migration` - 설계 문서 작성
2. `/pdca do autonomous-creator-migration` - 실행
3. `/pdca analyze autonomous-creator-migration` - 검증
