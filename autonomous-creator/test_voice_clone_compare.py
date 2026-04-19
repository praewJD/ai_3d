# -*- coding: utf-8 -*-
"""
Voice Clone 비교 테스트

1. 보이스 클론 사용 (F5-TTS-THAI)
2. 보이스 클론 미사용 (edge-tts 기본 목소리)
"""
import sys
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import asyncio
from pathlib import Path
import os

OUTPUT_DIR = Path(r"D:\AI-Video\autonomous-creator\output\voice_compare")
TEST_TEXT = "สวัสดีค่ะ ยินดีต้อนรับสู่โลกของปัญญาประดิษฐ์ วันนี้เราจะมาเรียนรู้เกี่ยวกับเทคโนโลยีใหม่ๆ กันนะคะ"


async def test_with_voice_clone():
    """
    Test 1: F5-TTS-THAI (보이스 클론 사용)

    - Reference audio의 목소리를 복제
    - 동일한 화자의 목소리로 생성
    """
    print("\n" + "=" * 60)
    print("Test 1: F5-TTS-THAI (Voice Clone 사용)")
    print("=" * 60)

    try:
        from infrastructure.tts.f5_tts_thai import F5TTSThaiEngine
        from core.domain.entities.audio import VoiceSettings

        # Reference audio 확인
        ref_audio = Path(r"C:\Users\JN\narration_th.flac")
        if not ref_audio.exists():
            print(f"❌ Reference audio 없음: {ref_audio}")
            return None

        print(f"✅ Reference audio: {ref_audio}")

        # 엔진 생성
        engine = F5TTSThaiEngine(
            reference_audio_path=str(ref_audio),
            reference_text="สวัสดีค่ะ ยินดีที่ได้รู้จักทุกท่านนะคะ"
        )

        # 의존성 체크
        deps = engine.check_dependencies()
        print("\n의존성 체크:")
        for k, v in deps.items():
            status = "✅" if v else "❌"
            print(f"  {status} {k}: {v}")

        if not all(deps.values()):
            print("\n❌ 의존성 미충족")
            return None

        # 오디오 생성
        voice = VoiceSettings(
            language="th",
            speed=1.0,
            reference_audio=str(ref_audio),
            reference_text="สวัสดีค่ะ ยินดีที่ได้รู้จักทุกท่านนะคะ"
        )

        output_path = str(OUTPUT_DIR / "1_voice_clone.wav")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        print(f"\n생성 중...")
        print(f"  텍스트: {TEST_TEXT[:40]}...")

        result = await engine.generate(TEST_TEXT, voice, output_path)

        size = os.path.getsize(result) / 1024
        print(f"\n✅ 완료!")
        print(f"  파일: {result}")
        print(f"  크기: {size:.1f} KB")

        return result

    except Exception as e:
        print(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_default_voice():
    """
    Test 2: F5-TTS-THAI 기본 보이스 (모델 내장 샘플)

    - 모델에 포함된 기본 reference audio 사용
    - 별도 reference 없이 사용 가능
    """
    print("\n" + "=" * 60)
    print("Test 2: F5-TTS-THAI 기본 보이스 (모델 내장)")
    print("=" * 60)

    try:
        from f5_tts_th.tts import TTS
        import soundfile as sf

        # 모델 내장 기본 reference audio
        model_path = Path.home() / ".cache" / "huggingface" / "hub" / "models--VIZINTZOR--F5-TTS-THAI" / "snapshots"
        snapshot_dirs = list(model_path.glob("*"))
        if not snapshot_dirs:
            print("❌ 모델 캐시 없음")
            return None

        ref_audio_path = snapshot_dirs[0] / "sample" / "ref_audio.wav"
        ref_text = "ฉันเดินทางไปเที่ยวที่จังหวัดเชียงใหม่ในช่วงฤดูหนาวเพื่อสัมผัสอากาศเย็นสบาย"

        if not ref_audio_path.exists():
            print(f"❌ 기본 reference 없음: {ref_audio_path}")
            return None

        print(f"✅ 기본 Reference: {ref_audio_path}")
        print(f"   텍스트: {ref_text[:40]}...")

        # TTS 생성
        tts = TTS(model="v1")

        output_path = str(OUTPUT_DIR / "2_default_voice.wav")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        print(f"\n생성 중...")
        print(f"  텍스트: {TEST_TEXT[:40]}...")

        loop = asyncio.get_event_loop()
        wav = await loop.run_in_executor(
            None,
            lambda: tts.infer(
                ref_audio=str(ref_audio_path),
                ref_text=ref_text,
                gen_text=TEST_TEXT,
                step=32,
                cfg=2.0,
                speed=1.0
            )
        )

        sf.write(output_path, wav, 24000)

        size = os.path.getsize(output_path) / 1024
        print(f"\n✅ 완료!")
        print(f"  파일: {output_path}")
        print(f"  크기: {size:.1f} KB")

        return output_path

    except Exception as e:
        print(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_edge_tts():
    """
    Test 3: edge-tts (Microsoft 기본 목소리)

    - Microsoft Edge TTS 기본 목소리
    - 미리 녹음된 화자의 목소리
    - 클로닝 없음
    """
    print("\n" + "=" * 60)
    print("Test 3: edge-tts (Microsoft 기본 목소리)")
    print("=" * 60)

    try:
        import edge_tts

        # 태국어 여성 목소리
        VOICE = "th-TH-PremwadeeNeural"  # Microsoft 기본 태국어 여성 목소리

        print(f"사용 목소리: {VOICE}")
        print(f"텍스트: {TEST_TEXT[:40]}...")

        output_path = str(OUTPUT_DIR / "3_edge_tts.mp3")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # edge-tts 생성
        communicate = edge_tts.Communicate(TEST_TEXT, VOICE)
        await communicate.save(output_path)

        size = os.path.getsize(output_path) / 1024
        print(f"\n✅ 완료!")
        print(f"  파일: {output_path}")
        print(f"  크기: {size:.1f} KB")

        # mp3 → wav 변환 (선택사항)
        try:
            from pydub import AudioSegment
            wav_path = str(OUTPUT_DIR / "3_edge_tts.wav")
            audio = AudioSegment.from_mp3(output_path)
            audio.export(wav_path, format="wav")
            wav_size = os.path.getsize(wav_path) / 1024
            print(f"  WAV 변환: {wav_size:.1f} KB")
        except:
            pass

        return output_path

    except ImportError:
        print("\n❌ edge-tts 미설치")
        print("  설치: pip install edge-tts")
        return None
    except Exception as e:
        print(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        return None


async def compare_results(file1, file2, file3):
    """결과 비교"""
    print("\n" + "=" * 60)
    print("📊 비교 결과")
    print("=" * 60)

    print("\n┌─────────────────────────────────────────────────────────────────────────────┐")
    print("│                          TTS 방식 비교                                      │")
    print("├─────────────────────┬─────────────────────┬─────────────────────────────────┤")
    print("│ F5-TTS-THAI         │ F5-TTS-THAI         │ edge-tts                        │")
    print("│ (내 목소리 클론)    │ (기본 보이스)       │ (Microsoft 기본)                │")
    print("├─────────────────────┼─────────────────────┼─────────────────────────────────┤")
    print("│ ✅ 내 목소리 복제   │ ✅ 기본 목소리 제공 │ ❌ 고정된 목소리                │")
    print("│ ✅ 커스텀 가능      │ ⚠️ 고정 화자        │ ❌ 변경 불가                    │")
    print("│ ⚠️ Reference 필요   │ ✅ Reference 불필요 │ ✅ Reference 불필요             │")
    print("│ ⚠️ GPU 권장         │ ⚠️ GPU 권장         │ ✅ CPU만 충분                   │")
    print("│ ⚠️ 처리 시간 김     │ ⚠️ 처리 시간 김     │ ✅ 처리 시간 짧음               │")
    print("└─────────────────────┴─────────────────────┴─────────────────────────────────┘")

    print(f"\n📁 파일 크기:")
    if file1:
        size1 = os.path.getsize(file1) / 1024
        print(f"  1. 내 목소리 클론: {size1:.1f} KB")
    if file2:
        size2 = os.path.getsize(file2) / 1024
        print(f"  2. 기본 보이스:    {size2:.1f} KB")
    if file3:
        size3 = os.path.getsize(file3) / 1024
        print(f"  3. Microsoft 기본: {size3:.1f} KB")

    print(f"\n📂 출력 위치: {OUTPUT_DIR}")
    print("\n💡 직접 들어보세요:")
    if file1:
        print(f"   1. {OUTPUT_DIR / '1_voice_clone.wav'}")
    if file2:
        print(f"   2. {OUTPUT_DIR / '2_default_voice.wav'}")
    if file3:
        print(f"   3. {OUTPUT_DIR / '3_edge_tts.mp3'}")


async def main():
    print("=" * 60)
    print("🎙️ TTS 방식 비교 테스트")
    print("   1. F5-TTS-THAI (내 목소리 클론)")
    print("   2. F5-TTS-THAI (기본 보이스)")
    print("   3. edge-tts (Microsoft 기본)")
    print("=" * 60)
    print(f"출력: {OUTPUT_DIR}")

    # Test 1: Voice Clone (내 목소리)
    file1 = await test_with_voice_clone()

    # Test 2: F5-TTS 기본 보이스
    file2 = await test_default_voice()

    # Test 3: edge-tts
    file3 = await test_edge_tts()

    # 비교
    await compare_results(file1, file2, file3)

    print("\n🎉 테스트 완료!")


if __name__ == "__main__":
    asyncio.run(main())
