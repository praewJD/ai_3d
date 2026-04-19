# -*- coding: utf-8 -*-
"""
FramePack 배치 비디오 변환

생성된 이미지들을 FramePack으로 비디오로 변환
FramePack은 별도 Python 환경에서 실행됨
"""
import os
import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime

# FramePack 경로
FRAMEPACK_DIR = Path(r"D:\AI-Video\FramePack\FramePack_Official\webui")
FRAMEPACK_PYTHON = Path(r"D:\AI-Video\FramePack\FramePack_Official\system\python\python.exe")

# FramePack 실행 스크립트 생성
FRAMEPACK_WORKER_SCRIPT = '''
# FramePack Worker Script
import sys
import os

# FramePack 경로 설정
sys.path.insert(0, r"{framepack_dir}")
os.environ['HF_HOME'] = r"{hf_home}"

import torch
from PIL import Image as PILImage
from diffusers_helper.utils import save_bcthw_as_mp4, resize_and_center_crop, generate_timestamp
from diffusers_helper.hf_login import login

# 모델 로드
print("Loading models...")
from diffusers import AutoencoderKLHunyuanVideo
from transformers import LlamaModel, CLIPTextModel, LlamaTokenizerFast, CLIPTokenizer
from transformers import SiglipImageProcessor, SiglipVisionModel
from diffusers_helper.models.hunyuan_video_packed import HunyuanVideoTransformer3DModelPacked
from diffusers_helper.hunyuan import encode_prompt_conds, vae_decode, vae_encode, vae_decode_fake
from diffusers_helper.clip_vision import hf_clip_vision_encode
from diffusers_helper.memory import cpu, gpu, get_cuda_free_memory_gb, move_model_to_device_with_memory_preservation
from diffusers_helper.bucket_tools import find_nearest_bucket
from diffusers_helper.pipelines.k_diffusion_hunyuan import sample_hunyuan

# 모델 로드
text_encoder = LlamaModel.from_pretrained("hunyuanvideo-community/HunyuanVideo", subfolder='text_encoder', torch_dtype=torch.float16).cpu()
text_encoder_2 = CLIPTextModel.from_pretrained("hunyuanvideo-community/HunyuanVideo", subfolder='text_encoder_2', torch_dtype=torch.float16).cpu()
tokenizer = LlamaTokenizerFast.from_pretrained("hunyuanvideo-community/HunyuanVideo", subfolder='tokenizer')
tokenizer_2 = CLIPTokenizer.from_pretrained("hunyuanvideo-community/HunyuanVideo", subfolder='tokenizer_2')
vae = AutoencoderKLHunyuanVideo.from_pretrained("hunyuanvideo-community/HunyuanVideo", subfolder='vae', torch_dtype=torch.float16).cpu()
feature_extractor = SiglipImageProcessor.from_pretrained("lllyasviel/flux_redux_bfl", subfolder='feature_extractor')
image_encoder = SiglipVisionModel.from_pretrained("lllyasviel/flux_redux_bfl", subfolder='image_encoder', torch_dtype=torch.float16).cpu()

# Transformer 로드
transformer = HunyuanVideoTransformer3DModelPacked.from_pretrained(
    'lllyasviel/FramePackI2V_HY',
    torch_dtype=torch.bfloat16
).cpu()
transformer.eval()
transformer.high_quality_fp32_output_for_inference = True
transformer.requires_grad_(False)

print("Models loaded!")

def generate_video(
    input_image_path: str,
    output_path: str,
    prompt: str = "",
    n_prompt: str = "",
    seed: int = 31337,
    total_second_length: float = 5.0,
    steps: int = 25,
    cfg: float = 1.0,
    gs: float = 10.0,
    gpu_memory_preservation: float = 6.0,
):
    """FramePack으로 비디오 생성"""

    # VRAM 확인
    free_mem_gb = get_cuda_free_memory_gb(gpu)
    high_vram = free_mem_gb > 60
    print(f"Free VRAM: {free_mem_gb:.2f} GB")

    # 이미지 로드
    input_image = PILImage.open(input_image_path).convert("RGB")

    # 해상도 조정
    resolution = 640
    width, height = resolution * 16 // 9, resolution  # 16:9
    input_image = resize_and_center_crop(input_image, (width, height))

    # 모델을 GPU로 이동
    if not high_vram:
        move_model_to_device_with_memory_preservation(transformer, gpu, gpu_memory_preservation)
        move_model_to_device_with_memory_preservation(text_encoder, gpu, gpu_memory_preservation)
        move_model_to_device_with_memory_preservation(text_encoder_2, gpu, gpu_memory_preservation)
        move_model_to_device_with_memory_preservation(image_encoder, gpu, gpu_memory_preservation)
        move_model_to_device_with_memory_preservation(vae, gpu, gpu_memory_preservation)

    # 이미지 인코딩
    print("Encoding image...")
    image_encoder_output = hf_clip_vision_encode(feature_extractor, image_encoder, input_image)
    image_encoder_last_hidden_state = image_encoder_output.last_hidden_state

    # 프롬프트 인코딩
    print("Encoding prompt...")
    llama_vec, clip_l_pooler = encode_prompt_conds(
        prompt, text_encoder, text_encoder_2, tokenizer, tokenizer_2
    )
    if cfg == 1:
        llama_vec_n, clip_l_pooler_n = torch.zeros_like(llama_vec), torch.zeros_like(clip_l_pooler)
    else:
        llama_vec_n, clip_l_pooler_n = encode_prompt_conds(
            n_prompt, text_encoder, text_encoder_2, tokenizer, tokenizer_2
        )

    # VAE 인코딩
    print("Encoding with VAE...")
    start_latent = vae_encode(vae, input_image)

    # Bucket 찾기
    latent_window_size = 9
    bucket_id = find_nearest_bucket(input_image.height, input_image.width)

    # 샘플링
    print("Sampling...")
    generator = torch.Generator(device="cpu").manual_seed(seed)

    # ... (나머지 샘플링 로직은 FramePack demo_gradio.py 참조)

    print(f"Video saved to: {output_path}")
    return output_path

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input image path")
    parser.add_argument("--output", required=True, help="Output video path")
    parser.add_argument("--prompt", default="", help="Prompt")
    parser.add_argument("--n_prompt", default="", help="Negative prompt")
    parser.add_argument("--seed", type=int, default=31337)
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--steps", type=int, default=25)
    args = parser.parse_args()

    generate_video(
        input_image_path=args.input,
        output_path=args.output,
        prompt=args.prompt,
        n_prompt=args.n_prompt,
        seed=args.seed,
        total_second_length=args.seconds,
        steps=args.steps,
    )
'''


def create_framepack_batch_file(output_dir: Path, image_paths: list):
    """
    FramePack 배치 실행 파일 생성

    FramePack WebUI를 실행하고 수동으로 이미지를 로드해야 합니다.
    이 스크립트는 이미지 목록과 설정을 안내합니다.
    """

    instructions = f"""
# FramePack 비디오 변환 안내

## 생성된 이미지 위치
{output_dir}

## 이미지 목록
"""
    for i, path in enumerate(image_paths, 1):
        instructions += f"{i}. {path}\n"

    instructions += f"""
## FramePack 실행 방법

1. FramePack WebUI 실행:
   cd {FRAMEPACK_DIR}
   {FRAMEPACK_PYTHON} demo_gradio.py

2. 브라우저에서 Gradio UI 열기 (보통 http://localhost:7860)

3. 각 이미지를 업로드하고 비디오 생성:
   - Input Image: 위의 이미지 중 하나 선택
   - Prompt: 비워두거나 간단한 모션 설명
   - Total Second Length: 5 (5초 비디오)
   - Steps: 25
   - Seed: 31337

4. 생성된 비디오는 {FRAMEPACK_DIR / "outputs"}에 저장됨

## 권장 설정
- Resolution: 640 (16:9)
- Total Second Length: 5.0
- Steps: 25
- Guidance Scale (gs): 10.0
- Use TeaCache: 체크
- GPU Memory Preservation: 6.0 (6GB VRAM용)
"""

    # 안내 파일 저장
    guide_path = output_dir / "FRAMEPACK_GUIDE.txt"
    with open(guide_path, "w", encoding="utf-8") as f:
        f.write(instructions)

    print(f"\nGuide saved: {guide_path}")
    print("\n" + instructions)

    return guide_path


def find_scene_images(story_output_dir: Path) -> list:
    """스토리 출력 디렉토리에서 장면 이미지 찾기"""
    images_dir = story_output_dir / "images"
    if not images_dir.exists():
        return []

    images = []
    for ext in ["*.png", "*.jpg", "*.jpeg"]:
        for img in images_dir.glob(ext):
            if "scene_" in img.name:
                images.append(img)

    return sorted(images)


def main():
    """메인 실행"""
    print("=" * 60)
    print("FramePack Batch Video Converter")
    print("=" * 60)

    # 최신 스토리 출력 디렉토리 찾기
    story_base = Path(r"D:\AI-Video\autonomous-creator\output\story_videos")

    # 가장 최신 디렉토리 찾기
    story_dirs = sorted(story_base.glob("robot_adventure_*"), reverse=True)
    if not story_dirs:
        print("No story output found. Run test_story_video_pipeline.py first.")
        return

    latest_dir = story_dirs[0]
    print(f"Latest story output: {latest_dir}")

    # 장면 이미지 찾기
    scene_images = find_scene_images(latest_dir)
    if not scene_images:
        print("No scene images found.")
        return

    print(f"Found {len(scene_images)} scene images:")
    for img in scene_images:
        print(f"  - {img.name}")

    # FramePack 안내 파일 생성
    create_framepack_batch_file(latest_dir, scene_images)

    # 결과 JSON 읽기
    results_file = latest_dir / "results.json"
    if results_file.exists():
        with open(results_file, "r", encoding="utf-8") as f:
            results = json.load(f)
        print(f"\nStory: {results.get('title', 'Unknown')}")
        print(f"Character Sheet: {results.get('character_sheet', 'None')}")

    print("\n" + "=" * 60)
    print("Next Steps:")
    print("1. Open FramePack WebUI")
    print("2. Load each scene image")
    print("3. Generate videos")
    print("=" * 60)


if __name__ == "__main__":
    main()
