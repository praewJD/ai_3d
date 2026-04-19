"""
F5-TTS-THAI 테스트 스크립트

보이스클론 + 내레이션 생성 테스트
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ============================================================
# 1. 의존성 체크
# ============================================================
def check_dependencies():
    """필수 의존성 확인"""
    print("\n" + "="*60)
    print("📦 의존성 체크")
    print("="*60)

    results = {}

    # PyTorch
    try:
        import torch
        results['pytorch'] = f"✅ PyTorch {torch.__version__}"
        results['cuda'] = f"✅ CUDA: {torch.cuda.is_available()}" if torch.cuda.is_available() else "⚠️ CUDA: False"
        if torch.cuda.is_available():
            results['gpu'] = f"✅ GPU: {torch.cuda.get_device_name(0)}"
    except ImportError:
        results['pytorch'] = "❌ PyTorch not installed"

    # F5-TTS
    try:
        import f5_tts
        results['f5_tts'] = f"✅ F5-TTS installed"
    except ImportError:
        results['f5_tts'] = "❌ F5-TTS not installed"

    # FFmpeg
    import subprocess
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True)
        results['ffmpeg'] = "✅ FFmpeg installed" if result.returncode == 0 else "❌ FFmpeg error"
    except:
        results['ffmpeg'] = "❌ FFmpeg not installed"

    # soundfile
    try:
        import soundfile
        results['soundfile'] = "✅ soundfile installed"
    except ImportError:
        results['soundfile'] = "⚠️ soundfile not installed (optional)"

    for key, value in results.items():
        print(f"  {value}")

    return results


# ============================================================
# 2. Reference Audio 준비
# ============================================================
def prepare_reference_audio():
    """Reference Audio 파일 확인 및 생성"""
    print("\n" + "="*60)
    print("🎙️ Reference Audio 준비")
    print("="*60)

    ref_dir = Path(__file__).parent / "reference_audio" / "thai"
    ref_dir.mkdir(parents=True, exist_ok=True)

    # 기존 파일 확인
    existing_files = list(ref_dir.glob("*.wav"))

    if existing_files:
        print(f"  ✅ 기존 Reference Audio 발견: {len(existing_files)}개")
        for f in existing_files:
            print(f"     - {f.name}")
        return str(existing_files[0])

    # 테스트용 Reference Audio 생성 안내
    print("""
  ⚠️ Reference Audio가 없습니다.

  다음 중 하나를 준비해주세요:

  1. 직접 녹음 (권장)
     - 5~10초 Thai 음성
     - 조용한 환경에서 녹음
     - 저장 경로: tests/reference_audio/thai/my_voice.wav

  2. 기존 오디오 파일 사용
     - Thai 음성이 포함된 WAV 파일
     - 배경 노이즈 없는 깨끗한 오디오

  3. 자동 생성 (테스트용)
     - 아래 옵션으로 Edge-TTS로 Thai 음성 생성 가능
""")

    return None


async def generate_test_reference():
    """테스트용 Reference Audio 생성 (Edge-TTS)"""
    print("\n" + "="*60)
    print("🔊 테스트용 Reference Audio 생성 (Edge-TTS)")
    print("="*60)

    try:
        import edge_tts

        ref_dir = Path(__file__).parent / "reference_audio" / "thai"
        ref_dir.mkdir(parents=True, exist_ok=True)
        output_path = ref_dir / "thai_female_test.wav"

        # Thai 텍스트 (짧은 인사말)
        text = "สวัสดีครับ ยินดีต้อนรับสู่ช่องของเรา"

        communicate = edge_tts.Communicate(
            text=text,
            voice="th-TH-PremwadeeNeural"
        )
        await communicate.save(str(output_path))

        print(f"  ✅ 생성 완료: {output_path}")
        return str(output_path)

    except ImportError:
        print("  ❌ edge-tts not installed. Run: pip install edge-tts")
        return None
    except Exception as e:
        print(f"  ❌ Edge-TTS 실패: {e}")
        print("  💡 대체 방법을 시도합니다...")

        # 대체 방법 1: Azure TTS 사용
        try:
            from infrastructure.tts.azure_tts import AzureTTSEngine
            from core.domain.entities.audio import VoiceSettings

            print("  🔄 Azure TTS로 대체 생성 중...")

            ref_dir = Path(__file__).parent / "reference_audio" / "thai"
            ref_dir.mkdir(parents=True, exist_ok=True)
            output_path = ref_dir / "thai_female_test.wav"

            engine = AzureTTSEngine()
            voice = VoiceSettings(language="th")

            await engine.generate(
                text="สวัสดีครับ ยินดีต้อนรับสู่ช่องของเรา",
                voice=voice,
                output_path=str(output_path)
            )

            print(f"  ✅ Azure TTS로 생성 완료: {output_path}")
            return str(output_path)

        except Exception as az_e:
            print(f"  ❌ Azure TTS도 실패: {az_e}")
            print("\n  📁 직접 Reference Audio를 준비해주세요:")
            print("     1. 5~10초 Thai 음성 녹음")
            print("     2. tests/reference_audio/thai/ 폴더에 저장")
            print("     3. 다시 테스트 실행")
            return None


# ============================================================
# 3. F5-TTS Voice Cloning 테스트
# ============================================================
async def test_voice_cloning(reference_audio: str = None):
    """F5-TTS Voice Cloning 테스트"""
    print("\n" + "="*60)
    print("🎯 F5-TTS Voice Cloning 테스트")
    print("="*60)

    if not reference_audio:
        print("  ❌ Reference Audio가 없습니다.")
        return None

    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "thai_cloned_output.wav"

    try:
        from f5_tts.api import F5TTS

        print(f"  📂 Reference: {reference_audio}")
        print(f"  📂 Output: {output_path}")

        # Thai 테스트 텍스트
        test_text = "สวัสดีค่ะ วันนี้เราจะมาพูดคุยเกี่ยวกับเรื่องน่าสนใจกันค่ะ"

        print(f"  📝 Text: {test_text}")
        print("  ⏳ Generating...")

        # F5-TTS 모델 로드
        f5tts = F5TTS(
            model="F5TTS_v1_Base",
            device="cuda"
        )

        # Voice Cloning (ref_text 필요 - reference audio의 텍스트)
        # Thai reference audio는 Edge-TTS로 생성된 것이므로 텍스트를 제공
        ref_text_thai = "สวัสดีครับ ยินดีต้อนรับสู่ช่องของเรา"

        f5tts.infer(
            ref_file=reference_audio,
            ref_text=ref_text_thai,
            gen_text=test_text,
            file_wave=str(output_path),
            speed=1.0
        )

        print(f"  ✅ 생성 완료: {output_path}")

        # 파일 크기 확인
        if output_path.exists():
            size_kb = output_path.stat().st_size / 1024
            print(f"  📊 파일 크기: {size_kb:.1f} KB")
            return str(output_path)
        else:
            print("  ❌ 파일이 생성되지 않았습니다.")
            return None

    except Exception as e:
        print(f"  ❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return None


# ============================================================
# 4. 포렌식 방지 처리 테스트
# ============================================================
async def test_antiforensics(audio_path: str):
    """오디오 포렌식 방지 처리 테스트"""
    print("\n" + "="*60)
    print("🔒 Anti-Forensics 처리 테스트")
    print("="*60)

    if not audio_path or not Path(audio_path).exists():
        print("  ❌ 입력 오디오가 없습니다.")
        return

    try:
        from infrastructure.tts.audio_antiforensics import StealthAudioProcessor

        output_dir = Path(__file__).parent / "output"

        # Light, Medium, Heavy 테스트
        presets = ["light", "medium", "heavy"]

        for preset in presets:
            print(f"\n  🎚️ Preset: {preset}")

            processor = StealthAudioProcessor(preset=preset)
            output_path = output_dir / f"thai_antiforensics_{preset}.wav"

            result = processor.process(audio_path, str(output_path))

            if Path(result).exists():
                size_kb = Path(result).stat().st_size / 1024
                print(f"     ✅ 완료: {result}")
                print(f"     📊 크기: {size_kb:.1f} KB")
            else:
                print(f"     ❌ 실패")

    except ImportError as e:
        print(f"  ⚠️ 모듈 import 실패: {e}")
        print("  기본 FFmpeg 처리로 대체...")

        # FFmpeg 직접 사용
        import subprocess

        output_path = output_dir / "thai_antiforensics_basic.wav"

        cmd = [
            'ffmpeg', '-y', '-i', audio_path,
            '-ar', '44100',
            '-acodec', 'pcm_s16le',
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0:
            print(f"  ✅ 기본 처리 완료: {output_path}")
        else:
            print(f"  ❌ FFmpeg 실패")

    except Exception as e:
        print(f"  ❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# 5. 전체 파이프라인 테스트
# ============================================================
async def run_full_test():
    """전체 파이프라인 테스트"""
    print("\n" + "="*60)
    print("🚀 F5-TTS-THAI 전체 파이프라인 테스트")
    print("="*60)

    # 1. 의존성 체크
    check_dependencies()

    # 2. Reference Audio 준비
    ref_audio = prepare_reference_audio()

    if not ref_audio:
        print("\n  테스트용 Reference Audio를 자동 생성합니다...")
        ref_audio = await generate_test_reference()

    if not ref_audio:
        print("\n  ❌ Reference Audio가 없어 테스트를 종료합니다.")
        return

    # 3. Voice Cloning 테스트
    cloned_audio = await test_voice_cloning(ref_audio)

    # 4. Anti-Forensics 테스트
    if cloned_audio:
        await test_antiforensics(cloned_audio)

    print("\n" + "="*60)
    print("✅ 테스트 완료!")
    print("="*60)
    print(f"\n  출력 폴더: {Path(__file__).parent / 'output'}")


# ============================================================
# 6. 빠른 테스트 (Reference Audio 없이)
# ============================================================
async def quick_test():
    """빠른 테스트 - Reference Audio 자동 생성"""
    print("\n" + "="*60)
    print("⚡ 빠른 테스트 모드")
    print("="*60)

    # 의존성 체크
    check_dependencies()

    # Reference 자동 생성 (async)
    ref_audio = await generate_test_reference()

    if ref_audio:
        # Voice Cloning
        cloned = await test_voice_cloning(ref_audio)

        # Anti-Forensics
        if cloned:
            await test_antiforensics(cloned)


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="F5-TTS-THAI 테스트")
    parser.add_argument("--quick", action="store_true", help="빠른 테스트 (자동 Reference 생성)")
    parser.add_argument("--check", action="store_true", help="의존성 체크만")
    parser.add_argument("--ref", type=str, help="Reference Audio 경로 지정")

    args = parser.parse_args()

    if args.check:
        check_dependencies()
    elif args.quick:
        asyncio.run(quick_test())
    elif args.ref:
        asyncio.run(test_voice_cloning(args.ref))
    else:
        asyncio.run(run_full_test())
