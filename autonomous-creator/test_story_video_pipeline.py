# -*- coding: utf-8 -*-
"""
스토리 기반 영상 생성 파이프라인

1. 캐릭터 시트 생성 (일관성 유지용 기준 이미지)
2. 장면별 이미지 생성 (캐릭터 일관성)
3. 이미지 → 영상 변환 (SVD)

Workflow:
    Story → Character Sheet → Scene Images → Videos → Final Edit
"""
import os
import sys
import torch
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import json

# Windows UTF-8 설정
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

OUTPUT_BASE = Path(r"D:\AI-Video\autonomous-creator\output\story_videos")

# ============================================================
# 3D 애니메이션 스타일 고정 키워드
# ============================================================
STYLE_3D = (
    "Disney Pixar style, 3D animation, 3D render, Octane render, C4D, "
    "cinematic lighting, volumetric lighting, ray tracing, "
    "high quality, 8k resolution, movie scene"
)

STYLE_NEGATIVE = (
    "realistic, photorealistic, photograph, 2D, flat, "
    "low quality, blurry, distorted, deformed, "
    "ugly, bad anatomy, extra limbs, "
    "watermark, signature, text, logo"
)

# ============================================================
# 스토리 템플릿
# ============================================================
STORY_TEMPLATES = {
    "robot_adventure": {
        "title": "로봇의 모험",
        "character": "cute round robot with big glowing eyes and antenna, metallic blue body, friendly expression",
        "scenes": [
            {
                "name": "morning_start",
                "scene": "cozy workshop interior, morning sunlight through window, tools and gadgets on workbench, scattered blueprints",
                "action": "robot waking up from sleep mode, stretching arms, eyes blinking on",
                "mood": "warm golden morning light, hopeful atmosphere"
            },
            {
                "name": "forest_discovery",
                "scene": "magical forest path, giant glowing mushrooms, bioluminescent plants, floating pollen",
                "action": "robot walking curiously, looking around with wonder, antenna glowing",
                "mood": "mystical blue ambient light, enchanting atmosphere"
            },
            {
                "name": "rain_shelter",
                "scene": "under a giant leaf during rain, raindrops falling, puddles on ground",
                "action": "robot sitting under leaf, watching rain with curious expression",
                "mood": "soft diffused light, peaceful rainy atmosphere"
            },
            {
                "name": "sunset_return",
                "scene": "hilltop overlooking the workshop, sunset sky with orange and pink clouds",
                "action": "robot standing proudly, watching sunset, holding a glowing flower",
                "mood": "warm golden hour lighting, emotional satisfying atmosphere"
            }
        ]
    },
    "cat_journey": {
        "title": "고양이의 여행",
        "character": "fluffy orange cat with big green eyes wearing a red collar, cute pink nose",
        "scenes": [
            {
                "name": "window_gazing",
                "scene": "cozy living room interior, window with city view, soft curtains",
                "action": "cat sitting on windowsill, looking outside with curious eyes",
                "mood": "soft afternoon light, dreamy atmosphere"
            },
            {
                "name": "garden_explore",
                "scene": "beautiful garden with colorful flowers, butterflies flying, stone path",
                "action": "cat walking through flowers, chasing a butterfly",
                "mood": "bright sunny day, cheerful atmosphere"
            },
            {
                "name": "night_stars",
                "scene": "rooftop at night, starry sky, city lights below",
                "action": "cat lying on roof tiles, gazing at stars",
                "mood": "cold blue moonlight, peaceful night atmosphere"
            },
            {
                "name": "home_return",
                "scene": "warm home interior, fireplace glowing, comfortable blanket",
                "action": "cat curled up sleeping peacefully, smiling in sleep",
                "mood": "warm orange firelight, cozy atmosphere"
            }
        ]
    },
    "girl_forest": {
        "title": "소녀와 숲의 비밀",
        "character": "young girl with short blue hair wearing yellow raincoat, red boots, curious expression",
        "scenes": [
            {
                "name": "rainy_start",
                "scene": "village street on rainy day, cobblestones, colorful houses",
                "action": "girl walking in rain, splashing in puddles, smiling",
                "mood": "soft overcast light, playful rainy atmosphere"
            },
            {
                "name": "forest_entrance",
                "scene": "mysterious forest entrance, ancient trees, glowing fireflies",
                "action": "girl standing at entrance, holding lantern, looking amazed",
                "mood": "ethereal green glow, magical atmosphere"
            },
            {
                "name": "friendly_creature",
                "scene": "forest clearing with giant glowing tree, floating lights",
                "action": "girl meeting a friendly glowing creature, reaching out hand",
                "mood": "warm bioluminescent light, wonder atmosphere"
            },
            {
                "name": "treasure_found",
                "scene": "hidden grove with crystal pond, rainbow light refraction",
                "action": "girl discovering glowing crystal, holding it up",
                "mood": "prismatic colorful light, magical discovery atmosphere"
            }
        ]
    }
}

# 전역 파이프라인
sd_pipeline = None
svd_pipeline = None


def get_sd_pipeline():
    """SD 3.5 파이프라인 로드"""
    global sd_pipeline
    if sd_pipeline is not None:
        return sd_pipeline

    print("Loading SD 3.5 Medium...")
    from diffusers import StableDiffusion3Pipeline

    device = "cuda" if torch.cuda.is_available() else "cpu"
    vram = torch.cuda.get_device_properties(0).total_memory / (1024**3) if device == "cuda" else 0
    print(f"Device: {device}, VRAM: {vram:.1f} GB")

    sd_pipeline = StableDiffusion3Pipeline.from_pretrained(
        "stabilityai/stable-diffusion-3.5-medium",
        torch_dtype=torch.float16,
    )

    if vram < 12:
        print("Using CPU offload...")
        sd_pipeline.enable_model_cpu_offload()
    else:
        sd_pipeline = sd_pipeline.to(device)

    return sd_pipeline


def get_svd_pipeline():
    """SVD 파이프라인 로드"""
    global svd_pipeline
    if svd_pipeline is not None:
        return svd_pipeline

    print("Loading Stable Video Diffusion...")
    from diffusers import StableVideoDiffusionPipeline

    device = "cuda" if torch.cuda.is_available() else "cpu"
    vram = torch.cuda.get_device_properties(0).total_memory / (1024**3) if device == "cuda" else 0

    svd_pipeline = StableVideoDiffusionPipeline.from_pretrained(
        "stabilityai/stable-video-diffusion-img2vid-xt-1-1",
        torch_dtype=torch.float16,
    )

    if vram < 12:
        print("Using CPU offload for SVD...")
        svd_pipeline.enable_model_cpu_offload()
        svd_pipeline.unet.enable_forward_chunking(chunk_size=1, dim=1)
    else:
        svd_pipeline = svd_pipeline.to(device)

    return svd_pipeline


def generate_character_sheet(
    character_description: str,
    output_dir: Path,
    seed: int = 42
) -> Path:
    """
    캐릭터 시트 생성 (기준 이미지)

    Returns:
        캐릭터 시트 이미지 경로
    """
    print(f"\n{'='*60}")
    print("Step 1: Generating Character Sheet")
    print(f"{'='*60}")

    pipe = get_sd_pipeline()

    prompt = (
        f"{STYLE_3D}, "
        f"character sheet, turnaround view, "
        f"front view, side view, back view, "
        f"same character shown from multiple angles, "
        f"white background, clean design, "
        f"{character_description}"
    )

    print(f"Character: {character_description[:50]}...")

    generator = torch.Generator(device="cpu").manual_seed(seed)

    start = datetime.now()
    result = pipe(
        prompt=prompt,
        negative_prompt=STYLE_NEGATIVE,
        num_inference_steps=40,
        guidance_scale=4.5,
        width=1024,
        height=576,
        generator=generator,
    )
    elapsed = (datetime.now() - start).total_seconds()

    image = result.images[0]
    output_path = output_dir / "character_sheet.png"
    image.save(output_path, quality=95)

    print(f"Done! ({elapsed:.1f}s)")
    print(f"Saved: {output_path}")

    return output_path


def generate_scene_image(
    scene_config: Dict,
    character_description: str,
    output_dir: Path,
    seed: int = 42
) -> Path:
    """
    장면 이미지 생성

    Args:
        scene_config: 장면 설정 (name, scene, action, mood)
        character_description: 캐릭터 설명
        output_dir: 출력 디렉토리
        seed: 랜덤 시드

    Returns:
        생성된 이미지 경로
    """
    pipe = get_sd_pipeline()

    # 프롬프트 조합
    prompt = (
        f"{STYLE_3D}, "
        f"{scene_config['scene']}, "
        f"{character_description}, "
        f"{scene_config['action']}, "
        f"{scene_config['mood']}, "
        f"cinematic composition, rule of thirds, depth of field"
    )

    print(f"  Generating: {scene_config['name']}...")

    generator = torch.Generator(device="cpu").manual_seed(seed)

    start = datetime.now()
    result = pipe(
        prompt=prompt,
        negative_prompt=STYLE_NEGATIVE,
        num_inference_steps=40,
        guidance_scale=4.5,
        width=1024,
        height=576,  # 16:9
        generator=generator,
    )
    elapsed = (datetime.now() - start).total_seconds()

    image = result.images[0]
    output_path = output_dir / f"scene_{scene_config['name']}.png"
    image.save(output_path, quality=95)

    print(f"    Done! ({elapsed:.1f}s)")

    return output_path


def image_to_video(
    image_path: Path,
    output_path: Path,
    motion_bucket_id: int = 127,
    num_frames: int = 25,
    fps: int = 8
) -> Path:
    """
    이미지를 비디오로 변환 (SVD)

    Args:
        image_path: 입력 이미지
        output_path: 출력 비디오 경로
        motion_bucket_id: 모션 강도 (1-255)
        num_frames: 프레임 수
        fps: FPS

    Returns:
        생성된 비디오 경로
    """
    from diffusers.utils import load_image, export_to_video

    pipe = get_svd_pipeline()

    # 이미지 로드 및 리사이즈
    image = load_image(str(image_path))
    image = image.resize((576, 1024))  # SVD 기본 해상도

    print(f"  Converting to video: {image_path.name}...")

    start = datetime.now()
    frames = pipe(
        image,
        num_frames=num_frames,
        motion_bucket_id=motion_bucket_id,
        noise_aug_strength=0.02,
        min_guidance_scale=1.0,
        max_guidance_scale=3.0,
        decode_chunk_size=8,
    ).frames[0]
    elapsed = (datetime.now() - start).total_seconds()

    export_to_video(frames, str(output_path), fps=fps)

    print(f"    Done! ({elapsed:.1f}s, {num_frames} frames)")

    return output_path


def create_story_video(
    story_key: str = "robot_adventure",
    seed: int = 42,
    skip_character_sheet: bool = False
) -> Dict:
    """
    스토리 비디오 생성 메인 함수

    Args:
        story_key: 스토리 템플릿 키
        seed: 랜덤 시드
        skip_character_sheet: 캐릭터 시트 생성 스킵

    Returns:
        결과 정보 딕셔너리
    """
    # 스토리 템플릿 선택
    if story_key not in STORY_TEMPLATES:
        print(f"Unknown story: {story_key}")
        print(f"Available: {list(STORY_TEMPLATES.keys())}")
        return {}

    story = STORY_TEMPLATES[story_key]

    # 출력 디렉토리 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = OUTPUT_BASE / f"{story_key}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    images_dir = output_dir / "images"
    videos_dir = output_dir / "videos"
    images_dir.mkdir(exist_ok=True)
    videos_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print(f"Story: {story['title']}")
    print(f"Output: {output_dir}")
    print("=" * 60)

    results = {
        "story": story_key,
        "title": story["title"],
        "output_dir": str(output_dir),
        "character_sheet": None,
        "scenes": []
    }

    # 1. 캐릭터 시트 생성
    if not skip_character_sheet:
        char_sheet_path = generate_character_sheet(
            character_description=story["character"],
            output_dir=images_dir,
            seed=seed
        )
        results["character_sheet"] = str(char_sheet_path)
    else:
        print("\nSkipping character sheet generation...")

    # 2. 장면별 이미지 생성
    print(f"\n{'='*60}")
    print("Step 2: Generating Scene Images")
    print(f"{'='*60}")

    scene_images = []
    for i, scene_config in enumerate(story["scenes"]):
        # 시드 변화로 약간의 다양성
        scene_seed = seed + i * 100

        image_path = generate_scene_image(
            scene_config=scene_config,
            character_description=story["character"],
            output_dir=images_dir,
            seed=scene_seed
        )
        scene_images.append((scene_config["name"], image_path))

    # 3. 이미지 → 비디오 변환
    print(f"\n{'='*60}")
    print("Step 3: Converting Images to Videos")
    print(f"{'='*60}")

    scene_videos = []
    for name, image_path in scene_images:
        video_path = videos_dir / f"{name}.mp4"

        try:
            video_path = image_to_video(
                image_path=image_path,
                output_path=video_path,
                motion_bucket_id=127,  # medium motion
                num_frames=25,
                fps=8
            )
            scene_videos.append((name, video_path))
            results["scenes"].append({
                "name": name,
                "image": str(image_path),
                "video": str(video_path)
            })
        except Exception as e:
            print(f"  Error converting {name}: {e}")
            results["scenes"].append({
                "name": name,
                "image": str(image_path),
                "video": None,
                "error": str(e)
            })

    # 4. 결과 저장
    results_path = output_dir / "results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 결과 요약
    print(f"\n{'='*60}")
    print("Results Summary")
    print("=" * 60)
    print(f"Story: {story['title']}")
    print(f"Character Sheet: {results['character_sheet']}")
    print(f"Scenes Generated: {len(results['scenes'])}")
    for scene in results["scenes"]:
        status = "OK" if scene.get("video") else "FAILED"
        print(f"  [{status}] {scene['name']}")

    print(f"\nOutput: {output_dir}")
    print(f"Results JSON: {results_path}")

    return results


def main():
    """메인 실행"""
    print("=" * 60)
    print("Story Video Pipeline")
    print("Story → Character Sheet → Scene Images → Videos")
    print("=" * 60)

    # 테스트 실행
    # 짧은 스토리로 테스트 (robot_adventure)
    results = create_story_video(
        story_key="robot_adventure",
        seed=42,
        skip_character_sheet=False
    )

    print(f"\n{'='*60}")
    print("Pipeline Complete!")
    print("=" * 60)

    # 추가 스토리 생성하려면:
    # create_story_video(story_key="cat_journey", seed=42)
    # create_story_video(story_key="girl_forest", seed=42)


if __name__ == "__main__":
    main()
