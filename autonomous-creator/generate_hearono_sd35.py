# -*- coding: utf-8 -*-
"""
Thai Storyboard Video Generator - SD 3.5 Image Generation

스토리보드 → SD 3.5 이미지 → TTS → 영상
"""
import sys
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import asyncio
from pathlib import Path
import os

OUTPUT_DIR = Path(r"D:\AI-Video\autonomous-creator\output\hearono_sd35")

# 스토리보드
STORYBOARD = {
    "title": "Hearono: The Last Song",
    "language": "th",
    "episodes": [
        {
            "id": 1,
            "title": "เมืองที่เงียบงัน",
            "duration": 10,
            "narration": "กรุงเทพฯ ยามค่ำคืน เงียบผิดปกติ เรเวน วายร้ายที่ควบคุมคลื่นเสียง กำลังจะเริ่มแผนการชั่วร้าย",
            "image_prompt": "futuristic Bangkok cityscape at night, empty streets, neon lights reflecting on wet pavement, dark ominous atmosphere, cinematic, 4k, dramatic lighting",
            "dialogue": "โลกนี้ มันดังเกินไป มันถึงเวลาของความเงียบที่แท้จริง"
        },
        {
            "id": 2,
            "title": "ความเงียบชั่วคราว",
            "duration": 10,
            "narration": "ฮีโรโน ผู้มีพลังได้ยินและควบคุมคลื่นเสียง ตัดสินใจออกมาช่วยเหลือผู้คน",
            "image_prompt": "anime style young hero with large noise-canceling headphones standing on rooftop, blue sound wave energy surrounding him, determined expression, city lights background, dynamic pose, cinematic, 4k",
            "dialogue": "ผมไม่ได้ยิน แต่ผมสัมผัสได้ถึงเสียงของพวกคุณ เสียงที่อยากจะมีชีวิต"
        },
        {
            "id": 3,
            "title": "เพลงสุดท้าย",
            "duration": 10,
            "narration": "การต่อสู้ครั้งสุดท้าย ฮีโรโนใช้พลังทั้งหมดทำลายเครื่องส่งสัญญาณของเรเวน ช่วยเมืองไว้ได้",
            "image_prompt": "epic anime battle scene, hero punching with blue sound wave explosion, defeated villain in black armor, destroyed signal machine, dramatic lighting, cinematic action, 4k",
            "dialogue": "นี่คือเพลงสุดท้ายของฉัน"
        }
    ]
}


class SD35ImageGenerator:
    """SD 3.5 Medium 이미지 생성기"""

    def __init__(self):
        self.pipeline = None
        self.device = "cuda"

    def load_model(self):
        """모델 로드"""
        if self.pipeline is not None:
            return

        import torch
        from diffusers import StableDiffusion3Pipeline

        print("\n[SD 3.5] Loading model...")

        self.pipeline = StableDiffusion3Pipeline.from_pretrained(
            "stabilityai/stable-diffusion-3.5-medium",
            torch_dtype=torch.float16,
        )

        # 6GB VRAM용 CPU offload
        self.pipeline.enable_model_cpu_offload()
        print("[SD 3.5] Model loaded (CPU offload mode)")

    def unload_model(self):
        """모델 언로드"""
        if self.pipeline:
            del self.pipeline
            self.pipeline = None
            import torch
            import gc
            gc.collect()
            torch.cuda.empty_cache()
            print("[SD 3.5] Model unloaded")

    def generate(self, prompt: str, output_path: str, seed: int = 42):
        """이미지 생성"""
        import torch

        self.load_model()

        print(f"[SD 3.5] Generating...")
        print(f"  Prompt: {prompt[:60]}...")

        generator = torch.Generator(device="cpu").manual_seed(seed)

        # 9:16 세로 비율
        result = self.pipeline(
            prompt=prompt,
            negative_prompt="blurry, low quality, distorted, watermark, text, signature",
            num_inference_steps=28,
            guidance_scale=7.0,
            width=576,
            height=1024,
            generator=generator,
        )

        image = result.images[0]
        image.save(output_path, quality=95)

        size = os.path.getsize(output_path) / 1024
        print(f"[SD 3.5] Saved: {size:.1f} KB")

        return output_path


async def generate_audio():
    """Step 1: 태국어 오디오 생성"""
    print("\n" + "=" * 60)
    print("Step 1: Thai TTS Generation")
    print("=" * 60)

    from infrastructure.tts.factory import TTSFactory
    from core.domain.entities.audio import VoiceSettings

    tts = TTSFactory.create("th")
    voice = VoiceSettings(language="th", speed=1.0)

    audio_dir = OUTPUT_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    audio_data = []

    for ep in STORYBOARD["episodes"]:
        print(f"\n  Episode {ep['id']}: {ep['title']}")

        # 내레이션
        narr_path = str(audio_dir / f"ep{ep['id']}_narration.wav")
        print(f"    Narration...")
        await tts.generate(ep['narration'], voice, narr_path)

        # 대사
        dial_path = str(audio_dir / f"ep{ep['id']}_dialogue.wav")
        print(f"    Dialogue...")
        await tts.generate(ep['dialogue'], voice, dial_path)

        audio_data.append({
            "episode": ep['id'],
            "narration": narr_path,
            "dialogue": dial_path
        })

    print(f"\n✅ Audio Complete: {len(audio_data) * 2} files")
    return audio_data


async def generate_images():
    """Step 2: SD 3.5 이미지 생성"""
    print("\n" + "=" * 60)
    print("Step 2: SD 3.5 Image Generation")
    print("=" * 60)

    image_dir = OUTPUT_DIR / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    generator = SD35ImageGenerator()
    image_paths = []

    for ep in STORYBOARD["episodes"]:
        print(f"\n  Episode {ep['id']}: {ep['title']}")

        output_path = str(image_dir / f"ep{ep['id']}_scene.png")

        generator.generate(
            prompt=ep['image_prompt'],
            output_path=output_path,
            seed=42 + ep['id']  # 에피소드별 다른 시드
        )

        image_paths.append(output_path)

    # 메모리 정리
    generator.unload_model()

    print(f"\n✅ Images Complete: {len(image_paths)} files")
    return image_paths


async def compose_video(audio_data, image_paths):
    """Step 3: 비디오 합성"""
    print("\n" + "=" * 60)
    print("Step 3: Video Composition")
    print("=" * 60)

    from moviepy.video.VideoClip import ImageClip
    from moviepy.video.compositing.CompositeVideoClip import concatenate_videoclips
    from moviepy.audio.io.AudioFileClip import AudioFileClip
    from moviepy.audio.AudioClip import CompositeAudioClip
    from moviepy.video.fx.FadeIn import FadeIn
    from moviepy.video.fx.FadeOut import FadeOut

    video_dir = OUTPUT_DIR / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)

    clips = []
    total_duration = 0

    for i, (audio, img_path) in enumerate(zip(audio_data, image_paths)):
        ep = STORYBOARD["episodes"][i]
        print(f"\n  Episode {ep['id']}: {ep['title']}")

        # 오디오 길이
        narr_audio = AudioFileClip(audio['narration'])
        dial_audio = AudioFileClip(audio['dialogue'])
        duration = narr_audio.duration + dial_audio.duration + 0.5
        print(f"    Duration: {duration:.2f}s")

        # 이미지 클립
        clip = ImageClip(img_path, duration=duration)
        clip = clip.resized((1080, 1920))

        # Ken Burns 줌 효과
        def make_zoom(get_frame, t):
            frame = get_frame(t)
            progress = t / duration
            scale = 1.0 + 0.08 * progress
            fh, fw = frame.shape[:2]
            new_h = int(fh / scale)
            new_w = int(fw / scale)
            y = (fh - new_h) // 2
            x = (fw - new_w) // 2
            return frame[y:y+new_h, x:x+new_w]

        clip = clip.transform(make_zoom)

        # 오디오 합성
        combined_audio = CompositeAudioClip([
            narr_audio.with_start(0),
            dial_audio.with_start(narr_audio.duration + 0.3)
        ])
        clip = clip.with_audio(combined_audio)

        clip = clip.with_effects([FadeIn(0.3), FadeOut(0.3)])
        clips.append(clip)
        total_duration += duration

    # 최종 합성
    print(f"\n  Composing {len(clips)} episodes...")
    print(f"  Total duration: {total_duration:.2f}s")

    final = concatenate_videoclips(clips, method="compose")
    final = final.with_effects([FadeIn(0.5), FadeOut(0.5)])

    output_path = str(video_dir / "hearono_sd35.mp4")

    final.write_videofile(
        output_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="medium",
        bitrate="5000k",
        logger=None
    )

    final.close()
    for clip in clips:
        clip.close()

    size = os.path.getsize(output_path) / 1024 / 1024
    print(f"\n✅ Video Complete!")
    print(f"  File: {output_path}")
    print(f"  Size: {size:.2f} MB")
    print(f"  Duration: {total_duration:.2f}s")

    return output_path


async def main():
    print("=" * 60)
    print("🎬 Hearono Episode Generator (SD 3.5)")
    print("   Story: The Last Song")
    print("=" * 60)
    print(f"Output: {OUTPUT_DIR}")

    # Step 1: Audio
    audio_data = await generate_audio()

    # Step 2: SD 3.5 Images
    image_paths = await generate_images()

    # Step 3: Video
    video_path = await compose_video(audio_data, image_paths)

    # Summary
    print("\n" + "=" * 60)
    print("📊 Generation Complete!")
    print("=" * 60)
    print(f"  Title: {STORYBOARD['title']}")
    print(f"  Episodes: {len(STORYBOARD['episodes'])}")
    print(f"  Language: Thai")
    print(f"  Images: SD 3.5 Medium (AI Generated)")
    print(f"\n🎬 Final Video: {video_path}")

    print("\n📁 All Files:")
    for f in sorted(OUTPUT_DIR.rglob("*")):
        if f.is_file():
            size = f.stat().st_size / 1024
            if size > 1024:
                print(f"  {f.relative_to(OUTPUT_DIR)}: {size/1024:.2f} MB")
            else:
                print(f"  {f.relative_to(OUTPUT_DIR)}: {size:.2f} KB")

    print("\n🎉 Done!")


if __name__ == "__main__":
    asyncio.run(main())
