# -*- coding: utf-8 -*-
"""Thai TTS using F5-TTS-THAI"""

import os
import sys
import json

# Set UTF-8 encoding for stdout
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import torch
import soundfile as sf
from pathlib import Path
from hydra.utils import get_class
from omegaconf import OmegaConf

# F5-TTS-THAI model path
MODEL_DIR = Path(r"D:\AI-Video\autonomous-creator\thai")
CKPT_PATH = MODEL_DIR / "model_1000000.pt"
VOCAB_PATH = MODEL_DIR / "vocab.txt"
MODEL_CFG_PATH = MODEL_DIR / "F5TTS_Thai.yaml"

# Reference audio
REF_AUDIO = Path(r"C:\Users\JN\narration_th.flac")
REF_TEXT = "สวัสดีค่ะ ยินดีที่ได้รู้จักทุกท่านนะคะ"  # Transcript of reference audio

# Text to generate
GEN_TEXT = """สวัสดีค่ะ ยินดีที่ได้รู้จักทุกท่านนะคะ ดิฉันดีใจมากค่ะที่วันนี้ได้มีโอกาสมาทักทายทุกคนด้วยเสียงของตัวเองเป็นภาษาไทย ถึงแม้ว่าดิฉันจะกำลังเรียนรู้ภาษาไทยอยู่
แต่ก็หวังว่าทุกคนจะเข้าใจและสัมผัสได้ถึงความจริงใจของดิฉันนะคะ ขอให้วันนี้เป็นวันที่ดีและมีความสุขสำหรับทุกท่านค่ะ แล้วพบกันใหม่ในโอกาสหน้านะคะ
ขอบคุณมากค่ะ"""

# Output
OUTPUT_DIR = Path(r"D:\AI-Video\autonomous-creator\output")
OUTPUT_FILE = "thai_tts_output.wav"


def main():
    print("=" * 60)
    print("F5-TTS-THAI Thai TTS Generation")
    print("=" * 60)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Import F5-TTS modules
    print("\n[1/5] Loading F5-TTS modules...")
    from f5_tts.infer.utils_infer import (
        load_vocoder,
        load_model,
        preprocess_ref_audio_text,
        infer_process,
    )

    # Load vocoder
    print("\n[2/5] Loading vocoder...")
    vocoder = load_vocoder(vocoder_name="vocos", is_local=False, device=device)

    # Load model config
    print(f"\n[3/5] Loading model config...")
    print(f"  - Config: {MODEL_CFG_PATH}")
    print(f"  - Checkpoint: {CKPT_PATH}")
    print(f"  - Vocab: {VOCAB_PATH}")

    model_cfg = OmegaConf.load(str(MODEL_CFG_PATH))
    model_cls = get_class(f"f5_tts.model.{model_cfg.model.backbone}")
    model_arc = model_cfg.model.arch

    # Load model
    print("\n[4/5] Loading F5-TTS-THAI model...")
    ema_model = load_model(
        model_cls,
        model_arc,
        str(CKPT_PATH),
        mel_spec_type="vocos",
        vocab_file=str(VOCAB_PATH),
        device=device
    )

    # Preprocess reference audio
    print(f"\n[5/5] Processing reference audio...")
    print(f"  - Reference Audio: {REF_AUDIO}")
    print(f"  - Reference Text: {REF_TEXT}")

    ref_audio_processed, ref_text_processed = preprocess_ref_audio_text(
        str(REF_AUDIO),
        REF_TEXT
    )

    # Generate speech
    output_path = OUTPUT_DIR / OUTPUT_FILE
    print(f"\n[6/6] Generating speech...")
    print(f"  - Output: {output_path}")
    print(f"  - Text length: {len(GEN_TEXT)} chars")

    audio_segments = []
    final_wave, final_sample_rate, spectrogram = infer_process(
        ref_audio_processed,
        ref_text_processed,
        GEN_TEXT,
        ema_model,
        vocoder,
        cross_fade_duration=0.15,
        nfe_step=32,
        speed=1.0,
    )

    # Save output
    import soundfile as sf
    sf.write(str(output_path), final_wave, final_sample_rate)

    # Check result
    if output_path.exists():
        file_size = output_path.stat().st_size / 1024
        duration = len(final_wave) / final_sample_rate
        print(f"\n{'='*60}")
        print(f"SUCCESS! Output saved to: {output_path}")
        print(f"File size: {file_size:.2f} KB")
        print(f"Duration: {duration:.2f} seconds")
        print("=" * 60)
    else:
        print(f"\nERROR: Output file not created")

    return str(output_path)


if __name__ == "__main__":
    main()
