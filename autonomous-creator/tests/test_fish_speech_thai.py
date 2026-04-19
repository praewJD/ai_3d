"""
Fish Speech Thai TTS 테스트 스크립트

- Zero-shot voice cloning 지원
- 80+ 언어 (Thai 포함)
- Cross-lingual 보이스 클론
"""
import asyncio
import os
import sys
from pathlib import Path

# Windows UTF-8 설정
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import subprocess

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def check_fish_speech():
    """Fish Speech 의존성 확인"""
    print("\n" + "="*60)
    print("📦 Fish Speech 의존성 체크")
    print("="*60)

    results = {}

    # Fish Speech
    try:
        import fish_speech
        results['fish_speech'] = f"✅ Fish Speech installed"
    except ImportError:
        results['fish_speech'] = "❌ Fish Speech not installed"

    # PyTorch
    try:
        import torch
        results['pytorch'] = f"✅ PyTorch {torch.__version__}"
        results['cuda'] = f"✅ CUDA: {torch.cuda.is_available()}" if torch.cuda.is_available() else "⚠️ CUDA: False"
        if torch.cuda.is_available():
            results['gpu'] = f"✅ GPU: {torch.cuda.get_device_name(0)}"
    except ImportError:
        results['pytorch'] = "❌ PyTorch not installed"

    # Transformers
    try:
        import transformers
        results['transformers'] = f"✅ Transformers {transformers.__version__}"
    except ImportError:
        results['transformers'] = "❌ Transformers not installed"

    for key, value in results.items():
        print(f"  {value}")

    return results


async def test_fish_speech_thai(
    reference_audio: str = r"C:\Users\JN\narration.wav",
    output_path: str = None
):
    """
    Fish Speech로 Thai TTS 테스트

    Args:
        reference_audio: Reference audio (Korean voice)
        output_path: 출력 파일 경로
    """
    print("\n" + "="*60)
    print("🐟 Fish Speech Thai TTS 테스트")
    print("="*60)

    if output_path is None:
        output_dir = Path(__file__).parent / "output"
        output_dir.mkdir(exist_ok=True)
        output_path = str(output_dir / "thai_fish_speech_output.wav")

    # Thai 텍스트
    thai_text = "สวัสดีค่ะ วันนี้เราจะมาพูดคุยเกี่ยวกับเรื่องน่าสนใจกันค่ะ"

    print(f"  📂 Reference: {reference_audio}")
    print(f"  📂 Output: {output_path}")
    print(f"  📝 Thai Text: {thai_text}")
    print("  ⏳ Generating...")

    try:
        # Fish Speech CLI 사용 (가장 안정적인 방법)
        # 방법 1: fish-speech CLI
        cmd = [
            'python', '-m', 'fish_speech.text_to_speech',
            '--text', thai_text,
            '--reference', reference_audio,
            '--output', output_path,
            '--language', 'th'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

        if result.returncode == 0:
            print(f"  ✅ CLI 생성 완료: {output_path}")
            if Path(output_path).exists():
                size_kb = Path(output_path).stat().st_size / 1024
                print(f"  📊 파일 크기: {size_kb:.1f} KB")
                return output_path

        # CLI 실패 시 Python API 시도
        print("  🔄 CLI 실패, Python API 시도...")
        return await test_with_python_api(thai_text, reference_audio, output_path)

    except Exception as e:
        print(f"  ❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

        # Python API로 재시도
        print("  🔄 Python API로 재시도...")
        return await test_with_python_api(thai_text, reference_audio, output_path)


async def test_with_python_api(text: str, ref_audio: str, output_path: str):
    """Fish Speech Python API 테스트"""
    print("\n  🔧 Fish Speech Python API 테스트")
    print("-" * 40)

    try:
        # Fish Speech 모델 로드 시도
        from fish_speech.models import load_model, synthesize

        # 모델 로드
        print("  ⏳ 모델 로딩...")
        model = load_model(
            model_name="fishaudio/fish-speech-1.5",
            device="cuda"
        )

        # TTS 생성
        print("  ⏳ TTS 생성 중...")
        audio = synthesize(
            model=model,
            text=text,
            reference_audio=ref_audio,
            language="th"
        )

        # 저장
        import torchaudio
        torchaudio.save(output_path, audio.cpu(), 44100)

        print(f"  ✅ Python API 생성 완료: {output_path}")
        return output_path

    except ImportError as e:
        print(f"  ⚠️ Python API import 실패: {e}")
        print("  🔄 대체 방법 시도...")
        return await test_with_huggingface(text, ref_audio, output_path)

    except Exception as e:
        print(f"  ❌ Python API 실패: {e}")
        import traceback
        traceback.print_exc()
        return await test_with_huggingface(text, ref_audio, output_path)


async def test_with_huggingface(text: str, ref_audio: str, output_path: str):
    """Hugging Face Transformers로 Fish Speech 사용"""
    print("\n  🔧 Hugging Face 방식 테스트")
    print("-" * 40)

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        print("  ⏳ Fish Speech 모델 로딩 (Hugging Face)...")
        print("  💡 모델: fishaudio/fish-speech-1.5")

        # Fish Speech는 현재 CLI 도구 방식을 권장
        # 대신 직접 모델 다운로드 후 CLI 실행

        # fish-speech 모델 경로 확인
        model_path = Path.home() / ".cache" / "huggingface" / "hub" / "models--fishaudio--fish-speech-1.5"

        if not model_path.exists():
            print("  ⚠️ Fish Speech 모델이 다운로드되지 않았습니다.")
            print("  📥 모델 다운로드 명령어:")
            print("     huggingface-cli download fishaudio/fish-speech-1.5 --local-dir ./fish-speech-1.5")

            # 대안: Bark 모델 사용
            return await test_with_bark(text, ref_audio, output_path)

        return None

    except Exception as e:
        print(f"  ❌ Hugging Face 방식 실패: {e}")
        return await test_with_bark(text, ref_audio, output_path)


async def test_with_bark(text: str, ref_audio: str, output_path: str):
    """Bark 모델로 대체 (다국어 지원)"""
    print("\n  🔧 Bark 모델로 대체 테스트")
    print("-" * 40)

    try:
        # Bark 설치 확인
        import subprocess
        result = subprocess.run(['pip', 'show', 'suno-bark'], capture_output=True)

        if result.returncode != 0:
            print("  ⚠️ Bark가 설치되지 않음. 설치 중...")
            subprocess.run(['pip', 'install', 'suno-bark', '-q'], capture_output=True)

        from bark import SAMPLE_RATE, generate_audio, preload_models

        print("  ⏳ Bark 모델 로딩...")
        preload_models()

        print("  ⏳ Thai 음성 생성 중...")
        # Bark는 Thai를 직접 지원하지 않음 - 영어로 테스트
        audio_array = generate_audio(text, speaker_prompt=ref_audio)

        # 저장
        import scipy.io.wavfile as wavfile
        wavfile.write(output_path, SAMPLE_RATE, audio_array)

        print(f"  ✅ Bark 생성 완료: {output_path}")
        return output_path

    except Exception as e:
        print(f"  ❌ Bark 테스트 실패: {e}")
        return None


async def test_fish_speech_cli():
    """Fish Speech CLI로 직접 테스트"""
    print("\n" + "="*60)
    print("🐟 Fish Speech CLI 직접 테스트")
    print("="*60)

    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    output_path = str(output_dir / "thai_fish_speech_cli.wav")

    ref_audio = r"C:\Users\JN\narration.wav"
    thai_text = "สวัสดีค่ะ วันนี้เราจะมาพูดคุยเกี่ยวกับเรื่องน่าสนใจกันค่ะ"

    # fish-speech CLI 명령어 옵션들 확인
    print("  📋 Fish Speech CLI 옵션 확인 중...")

    help_result = subprocess.run(
        ['python', '-m', 'fish_speech', '--help'],
        capture_output=True,
        text=True,
        encoding='utf-8'
    )

    print(help_result.stdout[:2000] if help_result.stdout else "No help available")

    # 모델 다운로드 시도
    print("\n  📥 Fish Speech 모델 다운로드 시도...")

    try:
        from huggingface_hub import snapshot_download

        model_dir = Path(__file__).parent.parent / "fish-speech-model"
        print(f"  📂 다운로드 경로: {model_dir}")

        snapshot_download(
            repo_id="fishaudio/fish-speech-1.5",
            local_dir=str(model_dir),
            local_dir_use_symlinks=False
        )

        print(f"  ✅ 모델 다운로드 완료: {model_dir}")

        # CLI 실행
        print("\n  ⏳ TTS 생성 중...")

        cmd = [
            'python', '-m', 'fish_speech',
            'synthesize',
            '--text', thai_text,
            '--reference', ref_audio,
            '--output', output_path,
            '--device', 'cuda'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

        print(f"  Return code: {result.returncode}")
        if result.stdout:
            print(f"  STDOUT: {result.stdout[:500]}")
        if result.stderr:
            print(f"  STDERR: {result.stderr[:500]}")

        if Path(output_path).exists():
            size_kb = Path(output_path).stat().st_size / 1024
            print(f"  ✅ 생성 완료: {output_path}")
            print(f"  📊 파일 크기: {size_kb:.1f} KB")
            return output_path

        return None

    except Exception as e:
        print(f"  ❌ CLI 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """메인 테스트"""
    print("\n" + "="*60)
    print("🚀 Fish Speech Thai TTS 전체 테스트")
    print("="*60)

    # 1. 의존성 체크
    check_fish_speech()

    # 2. Fish Speech CLI 테스트
    result = await test_fish_speech_cli()

    if result:
        print(f"\n✅ 테스트 성공: {result}")
    else:
        print("\n❌ Fish Speech 테스트 실패")
        print("💡 대안: F5-TTS-THAI, Azure TTS, 또는 Edge-TTS 사용")


if __name__ == "__main__":
    asyncio.run(main())
