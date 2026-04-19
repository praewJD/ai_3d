# Autonomous Creator 프로젝트 백업 가이드

## 개요

이 문서는 Autonomous Creator 프로젝트의 파일을 Git으로 백업할 때의 가이드입니다. 모델 파일은 용량太大而 excluded되어 있으며, 코드와 설정만 백업 대상입니다.

---

## 백업 대상

### 1. 코드 및 스크립트

| 디렉토리/파일 | 설명 |
|-------------|------|
| `autonomous-creator/` | 메인 프로젝트 코드 |
| `FramePack/` | FramePack 관련 코드 |
| `autonomous-creator/docs/` | 아키텍처 문서 |

### 2. 설정 파일

| 파일 | 설명 |
|-----|------|
| `.gitignore` | Git 무시 규칙 |
| `autonomous-creator/config/` | 설정 모듈 |
| `autonomous-creator/CLAUDE.md` | Claude 프로젝트 가이드 |

### 3. 데이터 파일

| 디렉토리 | 설명 |
|---------|------|
| `autonomous-creator/data/` | 캐릭터, 장소, 스타일 assets |
| `autonomous-creator/config/prompts/` | 프롬프트 템플릿 |

### 4. 문서

| 파일 | 설명 |
|-----|------|
| `autonomous-creator/README.md` | 프로젝트 개요 |
| `autonomous-creator/docs/*.md` | 아키텍처, 설정, 워크플로우 문서 |

---

## 백업 제외 대상 (`.gitignore`)

### 1. AI 모델 파일

모든 `.pth`, `.pt`, `.bin`, `.onnx` 파일과 다음 디렉토리:
- `*/models/`
- `*/checkpoints/`
- `*/weights/`
- `*/pretrained/`
- `*/hf_cache/`
- `*/huggingface/`
- `weights/`

### 2. 생성 결과물

| 확장자 | 설명 |
|-------|------|
| `*.mp4`, `*.wav`, `*.mp3`, `*.avi`, `*.mov` | 비디오/오디오 |
| `*.png`, `*.jpg` | 이미지 (assets 제외) |

### 3. Python 캐시

```
__pycache__/
*.pyc
*.pyo
*.pyc/
```

### 4. IDE 및 OS 파일

```
.vscode/
.idea/
.DS_Store
Thumbs.db
```

### 5. 가상환경

```
venv/
env/
.env
```

---

## 백업 방법

### 1. Git 초기화 (처음 백업 시)

```bash
cd D:\AI-Video

# Git 저장소 초기화
git init

# 원격 저장소 연결 (선택사항)
git remote add origin <your-repo-url>

# .gitignore 추가 확인
cat .gitignore
```

### 2. 파일 추가 및 커밋

```bash
# 모든 코드 파일 추가 (모델 제외됨)
git add .

# 커밋
git commit -m "Project backup - code and configs only"

# 원격에 푸시 (선택사항)
git push -u origin main
```

### 3. 이후 백업 시

```bash
# 변경사항 확인
git status

# 변경된 파일만 추가
git add -u

# 커밋
git commit -m "Update: <description>"

# 푸시
git push
```

---

## 모델 파일 분리 백업 (선택)

모델 파일은容量太大으로 Git LFS 사용 권장:

```bash
# Git LFS 초기화
git lfs install

# 모델 파일追踪
git lfs track "*.pth"
git lfs track "*.pt"
git lfs track "*.bin"

# .gitattributes 추가 후 커밋
git add .gitattributes
git commit -m "Add LFS tracking for model files"
```

> **참고**: Git LFS는 무료 용량 제한이 있으므로 외부 스토리지 활용도 고려하세요.

---

## 복원 방법

다른 시스템에서 복원 시:

```bash
# Clone 후
git clone <repo-url>

# 모델 다운로드 (별도 스토리지에서)
# - FramePack 모델
# - fish-speech 모델
# - S1 모델

# Python 의존성 설치
pip install -r requirements.txt  # 또는
pip install -r autonomous-creator/requirements.txt

# 실행
python autonomous-creator/<script>.py
```

---

## 파일 구조

```
D:\AI-Video/
├── .gitignore           # Git 무시 규칙
├── CLAUDE.md            # 이 문서
├── test.md
├── FramePack/           # FramePack 코드
│   └── (코드 파일들)
└── autonomous-creator/  # 메인 프로젝트
    ├── config/          # 설정
    ├── core/             # 도메인 로직
    ├── data/             # assets
    ├── docs/             # 문서
    ├── tests/            # 테스트 파일
    ├── backup_20260408/  # 이전 백업
    ├── fish-speech-repo/ # Fish Speech 관련
    ├── fish-speech-model/# 모델 (제외)
    ├── s1-mini/          # S1 모델 (제외)
    └── *.py              # 스크립트들
```

---

## 참고사항

1. **API 키**: `config/api_config.py` 등에 포함된 API 키는 복원 시再設定 필요
2. **외부 의존성**: 일부 스크립트는 외부 서비스 (Face Authority 등) 의존
3. **모델 경로**: 설정 파일의 모델 경로는 실제 환경에 맞게調整 필요

---

*마지막 업데이트: 2026-04-19*