# Design: autonomous-creator Migration

> **Feature**: autonomous-creator-migration
> **Created**: 2026-03-31
> **Based on**: autonomous-creator-migration.plan.md

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

## 1. Architecture Options

### Option A: Direct Move (Recommended)
- 폴더 통째로 이동 후 경로만 수정
- 빠르고 단순함
- **선택 이유**: 파일 구조 변경 없음, 롤백 용이

### Option B: Reorganize Structure
- 폴더 이동하면서 구조 정리
- 더 깔끔하지만 시간 소요

### Option C: Symlink
- 심볼릭 링크로 연결
- Windows 호환성 문제 가능성

---

## 2. Implementation Steps

### Step 1: Folder Move
```bash
mv "C:/Users/JN/AI영상자동화/autonomous-creator" "D:/AI-Video/autonomous-creator"
```

### Step 2: Code Path Updates (11 files)

| File | Changes |
|------|---------|
| test_full_pipeline.py | OUTPUT_DIR 경로 |
| test_framepack.py | output_dir 경로 |
| test_voice_clone_compare.py | OUTPUT_DIR 경로 |
| test_thai_pipeline.py | OUTPUT_DIR 경로 |
| thai_tts_generator.py | OUTPUT_DIR 경로 |
| thai_tts_f5.py | OUTPUT_DIR, MODEL_DIR 경로 |
| thai_tts_f5_v2.py | OUTPUT_DIR, MODEL_DIR 경로 |
| generate_hearono_sd35.py | OUTPUT_DIR 경로 |
| generate_hearono_episode.py | OUTPUT_DIR 경로 |
| thai/F5TTS_Thai.yaml | tokenizer_path 경로 |
| thai_tts_guide.md | 문서 내 경로 |

### Step 3: Memory Update
- `~/.claude/projects/C--Users-JN/memory/MEMORY.md` 수정

### Step 4: Verification
```bash
# 누락된 경로 확인
grep -r "AI영상자동화\\autonomous-creator" "D:/AI-Video/autonomous-creator/"
```

---

## 3. File Changes Summary

| Action | Count |
|--------|-------|
| Move folder | 1 |
| Edit Python files | 9 |
| Edit YAML file | 1 |
| Edit Markdown files | 2 |
| **Total edits** | 12 |

---

## 4. Rollback Plan
```bash
mv "D:/AI-Video/autonomous-creator" "C:/Users/JN/AI영상자동화/autonomous-creator"
# 경로 원복
```
