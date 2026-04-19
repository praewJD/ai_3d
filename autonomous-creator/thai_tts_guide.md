# F5-TTS-THAI Voice Cloning 사용 가이드

## 설치

```bash
pip install f5-tts-th
```

## 기본 사용법

```python
# -*- coding: utf-8 -*-
import sys
import io

# Windows UTF-8 설정 (필수)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from f5_tts_th.tts import TTS
import soundfile as sf

# 모델 로드 (최초 1회만)
tts = TTS(model="v1")

# Voice Cloning 실행
wav = tts.infer(
    ref_audio="참고오디오_경로.flac",  # 보이스 클론할 오디오 (2~8초 권장)
    ref_text="참고오디오의_텍스트",     # 참고 오디오의 대사
    gen_text="생성할_새_텍스트",        # 새로 말할 텍스트
    step=32,          # 품질 단계 (32 기본, 높을수록 느리지만 품질 좋음)
    cfg=2.0,          # CFG 스케일 (2.0 기본)
    speed=1.0         # 말하기 속도 (1.0 기본, 0.7~0.8 느리게)
)

# 저장
sf.write("출력파일.wav", wav, 24000)
```

## 실제 사용 예시

```python
# thai_tts_generator.py
# -*- coding: utf-8 -*-
import sys
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from f5_tts_th.tts import TTS
import soundfile as sf
from pathlib import Path

# 설정
REFERENCE_AUDIO = r"C:\Users\JN\narration_th.flac"
REFERENCE_TEXT = "สวัสดีค่ะ ยินดีที่ได้รู้จักทุกท่านนะคะ"
OUTPUT_DIR = Path(r"D:\AI-Video\autonomous-creator\output")

def generate_thai_tts(text: str, output_filename: str, speed: float = 1.0):
    """태국어 TTS 생성 (Voice Cloning)"""

    # 모델 로드
    tts = TTS(model="v1")

    # 생성
    wav = tts.infer(
        ref_audio=REFERENCE_AUDIO,
        ref_text=REFERENCE_TEXT,
        gen_text=text,
        step=32,
        cfg=2.0,
        speed=speed
    )

    # 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / output_filename
    sf.write(str(output_path), wav, 24000)

    print(f"생성 완료: {output_path}")
    print(f"길이: {len(wav)/24000:.2f}초")

    return str(output_path)

# 실행 예시
if __name__ == "__main__":
    thai_text = """สวัสดีค่ะ ยินดีที่ได้รู้จักทุกท่านนะคะ
    ดิฉันดีใจมากค่ะที่วันนี้ได้มีโอกาสมาทักทายทุกคน
    ขอบคุณมากค่ะ"""

    generate_thai_tts(thai_text, "thai_output.wav")
```

## 파라미터 설명

| 파라미터 | 설명 | 기본값 | 권장 범위 |
|---------|------|--------|----------|
| `ref_audio` | 보이스 클론할 참고 오디오 | 필수 | 2~8초 FLAC/WAV |
| `ref_text` | 참고 오디오의 정확한 대사 | 필수 | 태국어 텍스트 |
| `gen_text` | 새로 생성할 텍스트 | 필수 | 태국어 텍스트 |
| `step` | 추론 단계 (품질) | 32 | 16~64 |
| `cfg` | CFG 스케일 | 2.0 | 1.5~3.0 |
| `speed` | 말하기 속도 | 1.0 | 0.7~1.2 |

## 주의사항

1. **참고 오디오 품질이 중요**
   - 2~8초 길이
   - 배경소음 없는 깨끗한 오디오
   - 태국어 원어민 발음 권장

2. **참고 텍스트 정확성**
   - 참고 오디오의 대사와 정확히 일치해야 함
   - 태국어로 작성

3. **속도 조절**
   - 참고 오디오가 빠른 경우: `speed=0.7~0.8`
   - 정상 속도: `speed=1.0`

## 파일 위치

- **모델 캐시**: `C:\Users\JN\.cache\huggingface\hub\models--VIZINTZOR--F5-TTS-THAI\`
- **참고 오디오**: `C:\Users\JN\narration_th.flac`
- **출력 폴더**: `D:\AI-Video\autonomous-creator\output\`

## 빠른 실행 (원라이너)

```bash
cd "D:\AI-Video\autonomous-creator" && python -c "
import sys, io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from f5_tts_th.tts import TTS
import soundfile as sf

tts = TTS(model='v1')
wav = tts.infer(
    ref_audio=r'C:\Users\JN\narration_th.flac',
    ref_text='สวัสดีค่ะ ยินดีที่ได้รู้จักทุกท่านนะคะ',
    gen_text='여기에_생성할_태국어_텍스트',
    step=32, cfg=2.0, speed=1.0
)
sf.write(r'D:\AI-Video\autonomous-creator\output\output.wav', wav, 24000)
print('완료!')
"
```

## 대안: Edge-TTS (Voice Cloning 없음)

Voice Cloning이 필요 없고 원어민 발음만 필요한 경우:

```python
import edge_tts
import asyncio

async def generate_thai(text: str, output: str):
    # 여성: th-TH-PremwadeeNeural
    # 남성: th-TH-NiwatNeural
    communicate = edge_tts.Communicate(text, "th-TH-PremwadeeNeural")
    await communicate.save(output)

asyncio.run(generate_thai("태국어 텍스트", "output.wav"))
```

---

**작성일**: 2026-03-30
**모델**: VIZINTZOR/F5-TTS-THAI (1,000,000 steps)
**패키지**: f5-tts-th v1.0.9
