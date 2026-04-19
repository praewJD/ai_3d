# -*- coding: utf-8 -*-
"""
Thai Storyboard Video Generator

입력: 태국어 스토리보드
출력: 90초 태국어 더빙 영상
"""
import sys
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import asyncio
from pathlib import Path
import os

# 출력 디렉토리
OUTPUT_DIR = Path(r"D:\AI-Video\autonomous-creator\output\hearono_episode")

# 스토리보드 데이터
STORYBOARD = {
    "title": "Hearono: เพลงสุดท้าย",
    "language": "th",
    "characters": {
        "hearono": "ฮีโรโน - เด็กหนุ่มพลังคลื่นเสียง",
        "raven": "เรเวน - วายร้ายควบคุมเสียง"
    },
    "episodes": [
        {
            "id": 1,
            "title": "เมืองที่เงียบงัน",
            "duration": 10,  # 테스트용으로 단축
            "narration": "กรุงเทพฯ ยามค่ำคืน เงียบผิดปกติ เรเวน วายร้ายที่ควบคุมคลื่นเสียง กำลังจะเริ่มแผนการชั่วร้าย",
            "image_prompt": "futuristic Bangkok cityscape at night, empty streets, dark atmosphere, neon lights, cinematic, dramatic lighting, 4k",
            "dialogue": "โลกนี้... มันดังเกินไป... มันถึงเวลาของความเงียบที่แท้จริง"
        },
        {
            "id": 2,
            "title": "ความเงียบชั่วคราว",
            "duration": 10,
            "narration": "ฮีโรโน ผู้มีพลังได้ยินและควบคุมคลื่นเสียง ตัดสินใจออกมาช่วยเหลือผู้คน",
            "image_prompt": "young hero with large headphones standing on rooftop, blue sound wave energy surrounding him, determined expression, anime style, cinematic",
            "dialogue": "ผมไม่ได้ยิน... แต่ผมสัมผัสได้ถึงเสียงของพวกคุณ... เสียงที่อยากจะมีชีวิต"
        },
        {
            "id": 3,
            "title": "เพลงสุดท้าย",
            "duration": 10,
            "narration": "การต่อสู้ครั้งสุดท้าย ฮีโรโนใช้พลังทั้งหมดทำลายเครื่องส่งสัญญาณของเรเวน ช่วยเมืองไว้ได้",
            "image_prompt": "epic battle scene, sound wave explosion, blue energy waves spreading across city, defeated villain, heroic moment, dramatic lighting, 4k",
            "dialogue": "นี่คือเพลงสุดท้ายของฉัน"
        }
    ]
}


async def generate_audio():
    """Step 1: 태국어 오디오 생성"""
    print("\n" + "=" * 60)
    print("Step 1: Thai Audio Generation")
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
        print(f"    Narration: {ep['narration'][:40]}...")
        await tts.generate(ep['narration'], voice, narr_path)

        # 대사
        dial_path = str(audio_dir / f"ep{ep['id']}_dialogue.wav")
        print(f"    Dialogue: {ep['dialogue'][:40]}...")
        await tts.generate(ep['dialogue'], voice, dial_path)

        audio_data.append({
            "episode": ep['id'],
            "narration": narr_path,
            "dialogue": dial_path
        })

    print(f"\n✅ Audio Complete: {len(audio_data) * 2} files")
    return audio_data


async def create_scene_images():
    """Step 2: 장면 이미지 생성 (플레이스홀더)"""
    print("\n" + "=" * 60)
    print("Step 2: Scene Image Generation")
    print("=" * 60)

    from PIL import Image, ImageDraw

    image_dir = OUTPUT_DIR / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    colors = [
        (20, 30, 50),   # Dark blue night
        (40, 50, 80),   # Blue hero
        (60, 40, 70),   # Purple battle
    ]

    image_paths = []

    for i, ep in enumerate(STORYBOARD["episodes"]):
        img = Image.new('RGB', (576, 1024), colors[i % len(colors)])
        draw = ImageDraw.Draw(img)

        # 그라데이션 효과
        for y in range(0, 1024, 20):
            alpha = int(30 * (y / 1024))
            draw.line([(0, y), (576, y)], fill=(alpha, alpha, alpha + 20), width=1)

        # 에피소드 텍스트
        text = f"Episode {ep['id']}"
        draw.ellipse([238, 462, 338, 562], fill=(100, 100, 150))
        draw.text((288, 512), text, fill=(255, 255, 255), anchor="mm")

        # 제목
        draw.text((288, 600), ep['title'][:20], fill=(200, 200, 200), anchor="mm")

        output_path = str(image_dir / f"ep{ep['id']}_scene.png")
        img.save(output_path, quality=95)

        size = os.path.getsize(output_path) / 1024
        print(f"  Episode {ep['id']}: {size:.1f} KB - {ep['image_prompt'][:50]}...")

        image_paths.append(output_path)

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

    video_dir = OUTPUT_DIR / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)

    clips = []
    total_duration = 0

    for i, (audio, img_path) in enumerate(zip(audio_data, image_paths)):
        ep = STORYBOARD["episodes"][i]
        print(f"\n  Episode {ep['id']}: {ep['title']}")

        # 오디오 길이 확인
        narr_audio = AudioFileClip(audio['narration'])
        dial_audio = AudioFileClip(audio['dialogue'])

        duration = narr_audio.duration + dial_audio.duration + 0.5
        print(f"    Duration: {duration:.2f}s")

        # 이미지 클립
        clip = ImageClip(img_path, duration=duration)
        clip = clip.resized((1080, 1920))

        # Ken Burns 효과 (MoviePy 2.x)
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

        # MoviePy 2.x uses transform instead of fl
        clip = clip.transform(make_zoom)

        # 오디오 합성 (MoviePy 2.x API)
        from moviepy.audio.AudioClip import CompositeAudioClip
        combined_audio = CompositeAudioClip([
            narr_audio.with_start(0),
            dial_audio.with_start(narr_audio.duration + 0.3)
        ])
        clip = clip.with_audio(combined_audio)

        # MoviePy 2.x: fade methods
        from moviepy.video.fx.FadeIn import FadeIn
        from moviepy.video.fx.FadeOut import FadeOut
        clip = clip.with_effects([FadeIn(0.3), FadeOut(0.3)])
        clips.append(clip)
        total_duration += duration

    # 최종 합성
    print(f"\n  Composing {len(clips)} episodes...")
    print(f"  Total duration: {total_duration:.2f}s")

    final = concatenate_videoclips(clips, method="compose")
    final = final.with_effects([FadeIn(0.5), FadeOut(0.5)])

    output_path = str(video_dir / "hearono_episode_1.mp4")

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
    print("🎬 Hearono Episode Generator")
    print("   Story: เพลงสุดท้าย (The Last Song)")
    print("=" * 60)
    print(f"Output: {OUTPUT_DIR}")

    # Step 1: Audio
    audio_data = await generate_audio()

    # Step 2: Images
    image_paths = await create_scene_images()

    # Step 3: Video
    video_path = await compose_video(audio_data, image_paths)

    # Summary
    print("\n" + "=" * 60)
    print("📊 Generation Complete!")
    print("=" * 60)
    print(f"  Title: {STORYBOARD['title']}")
    print(f"  Episodes: {len(STORYBOARD['episodes'])}")
    print(f"  Language: Thai")
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
