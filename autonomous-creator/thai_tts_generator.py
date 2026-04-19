# -*- coding: utf-8 -*-
"""
F5-TTS-THAI Voice Cloning Generator
사용법: python thai_tts_generator.py "생성할_태국어_텍스트" [출력파일명]
"""
import sys
import io

# Windows UTF-8 설정
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import argparse
from pathlib import Path
from f5_tts_th.tts import TTS
import soundfile as sf

# ============ 설정 ============
REFERENCE_AUDIO = r"C:\Users\JN\narration_th.flac"
REFERENCE_TEXT = "สวัสดีค่ะ ยินดีที่ได้รู้จักทุกท่านนะคะ"
OUTPUT_DIR = Path(r"D:\AI-Video\autonomous-creator\output")
# ==============================

# 전역 모델 (재사용)
_tts_model = None

def get_tts_model():
    """모델 싱글톤 로드"""
    global _tts_model
    if _tts_model is None:
        print("Loading F5-TTS-THAI model...")
        _tts_model = TTS(model="v1")
        print("Model loaded!")
    return _tts_model

def generate_thai_tts(
    text: str,
    output_filename: str = "thai_output.wav",
    speed: float = 1.0,
    step: int = 32,
    cfg: float = 2.0
) -> str:
    """
    태국어 TTS 생성 (Voice Cloning)

    Args:
        text: 생성할 태국어 텍스트
        output_filename: 출력 파일명
        speed: 말하기 속도 (0.7~1.2)
        step: 품질 단계 (16~64)
        cfg: CFG 스케일 (1.5~3.0)

    Returns:
        출력 파일 경로
    """
    # 모델 로드
    tts = get_tts_model()

    # 출력 디렉토리 생성
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*50}")
    print(f"Generating Thai TTS")
    print(f"{'='*50}")
    print(f"Text: {text[:50]}{'...' if len(text) > 50 else ''}")
    print(f"Speed: {speed}, Step: {step}, CFG: {cfg}")

    # TTS 생성
    wav = tts.infer(
        ref_audio=REFERENCE_AUDIO,
        ref_text=REFERENCE_TEXT,
        gen_text=text,
        step=step,
        cfg=cfg,
        speed=speed
    )

    # 저장
    output_path = OUTPUT_DIR / output_filename
    sf.write(str(output_path), wav, 24000)

    duration = len(wav) / 24000
    size = output_path.stat().st_size / 1024

    print(f"\n{'='*50}")
    print(f"DONE!")
    print(f"  File: {output_path}")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Size: {size:.2f} KB")
    print(f"{'='*50}")

    return str(output_path)


def main():
    parser = argparse.ArgumentParser(description="F5-TTS-THAI Voice Cloning")
    parser.add_argument("text", help="생성할 태국어 텍스트")
    parser.add_argument("-o", "--output", default="thai_output.wav", help="출력 파일명")
    parser.add_argument("-s", "--speed", type=float, default=1.0, help="말하기 속도 (0.7~1.2)")
    parser.add_argument("--step", type=int, default=32, help="품질 단계")
    parser.add_argument("--cfg", type=float, default=2.0, help="CFG 스케일")

    args = parser.parse_args()

    generate_thai_tts(
        text=args.text,
        output_filename=args.output,
        speed=args.speed,
        step=args.step,
        cfg=args.cfg
    )


if __name__ == "__main__":
    # 인자 없으면 기본 텍스트로 실행
    if len(sys.argv) == 1:
        default_text = "สวัสดีค่ะ ยินดีที่ได้รู้จักทุกท่านนะคะ ขอบคุณมากค่ะ"
        print(f"기본 텍스트로 실행: {default_text}")
        generate_thai_tts(default_text, "thai_default.wav")
    else:
        main()
