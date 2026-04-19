# -*- coding: utf-8 -*-
"""
FramePack 직접 실행 스크립트
이미지 → 비디오 변환
"""
import os
import sys

# FramePack 환경 설정
FRAMEPACK_DIR = r"D:\AI-Video\FramePack\FramePack_Official\webui"
HF_HOME = r"D:\AI-Video\FramePack\hf_download"

os.environ['HF_HOME'] = HF_HOME
sys.path.insert(0, FRAMEPACK_DIR)
sys.path.insert(0, os.path.join(FRAMEPACK_DIR, "diffusers_helper"))

import torch
import time
from pathlib import Path
from PIL import Image as PILImage
from datetime import datetime

print("=" * 60)
print("FramePack Video Generator")
print("=" * 60)

# VRAM 확인
if torch.cuda.is_available():
    free_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    print(f"GPU VRAM: {free_mem:.1f} GB")
else:
    print("No CUDA GPU available!")
    sys.exit(1)

# 모델 로드
print("\nLoading models... (this may take a few minutes)")

from diffusers import AutoencoderKLHunyuanVideo
from transformers import LlamaModel, CLIPTextModel, LlamaTokenizerFast, CLIPTokenizer
from transformers import SiglipImageProcessor, SiglipVisionModel
from diffusers_helper.models.hunyuan_video_packed import HunyuanVideoTransformer3DModelPacked
from diffusers_helper.hunyuan import encode_prompt_conds, vae_decode, vae_encode, vae_decode_fake
from diffusers_helper.clip_vision import hf_clip_vision_encode
from diffusers_helper.memory import cpu, gpu, get_cuda_free_memory_gb, move_model_to_device_with_memory_preservation, DynamicSwapInstaller
from diffusers_helper.bucket_tools import find_nearest_bucket
from diffusers_helper.utils import save_bcthw_as_mp4, resize_and_center_crop, generate_timestamp
import einops
import numpy as np

# 모델들 로드
print("  Loading text encoders...")
text_encoder = LlamaModel.from_pretrained(
    "hunyuanvideo-community/HunyuanVideo",
    subfolder='text_encoder',
    torch_dtype=torch.float16
).cpu()

text_encoder_2 = CLIPTextModel.from_pretrained(
    "hunyuanvideo-community/HunyuanVideo",
    subfolder='text_encoder_2',
    torch_dtype=torch.float16
).cpu()

tokenizer = LlamaTokenizerFast.from_pretrained(
    "hunyuanvideo-community/HunyuanVideo",
    subfolder='tokenizer'
)

tokenizer_2 = CLIPTokenizer.from_pretrained(
    "hunyuanvideo-community/HunyuanVideo",
    subfolder='tokenizer_2'
)

print("  Loading VAE...")
vae = AutoencoderKLHunyuanVideo.from_pretrained(
    "hunyuanvideo-community/HunyuanVideo",
    subfolder='vae',
    torch_dtype=torch.float16
).cpu()

print("  Loading image encoder...")
feature_extractor = SiglipImageProcessor.from_pretrained(
    "lllyasviel/flux_redux_bfl",
    subfolder='feature_extractor'
)

image_encoder = SiglipVisionModel.from_pretrained(
    "lllyasviel/flux_redux_bfl",
    subfolder='image_encoder',
    torch_dtype=torch.float16
).cpu()

print("  Loading transformer...")
transformer = HunyuanVideoTransformer3DModelPacked.from_pretrained(
    'lllyasviel/FramePackI2V_HY',
    torch_dtype=torch.bfloat16
).cpu()

transformer.eval()
transformer.high_quality_fp32_output_for_inference = True
transformer.to(dtype=torch.bfloat16)
transformer.requires_grad_(False)

print("All models loaded!\n")


def generate_video(
    input_image_path: str,
    output_path: str,
    prompt: str = "",
    n_prompt: str = "",
    seed: int = 31337,
    total_second_length: float = 5.0,
    latent_window_size: int = 9,
    steps: int = 25,
    cfg: float = 1.0,
    gs: float = 10.0,
    rs: float = 0.0,
    gpu_memory_preservation: float = 6.0,
    use_teacache: bool = True,
    mp4_crf: int = 16,
    output_fps: int = 24,
):
    """
    FramePack으로 비디오 생성
    """
    print(f"\n{'='*60}")
    print(f"Generating video: {Path(input_image_path).name}")
    print(f"{'='*60}")

    # VRAM 모드 결정
    free_mem_gb = get_cuda_free_memory_gb(gpu)
    high_vram = free_mem_gb > 60
    print(f"Free VRAM: {free_mem_gb:.2f} GB, High VRAM mode: {high_vram}")

    # 이미지 로드
    input_image = PILImage.open(input_image_path).convert("RGB")
    input_image = np.array(input_image)

    # 해상도 설정 (16:9)
    resolution = 640
    width = 640
    height = 360  # 16:9 비율

    # 이미지 리사이즈
    input_image = resize_and_center_crop(input_image, width, height)

    # 모델을 GPU로 이동
    if not high_vram:
        print("Moving models to GPU with memory preservation...")
        move_model_to_device_with_memory_preservation(transformer, gpu, gpu_memory_preservation)
        move_model_to_device_with_memory_preservation(text_encoder, gpu, gpu_memory_preservation)
        move_model_to_device_with_memory_preservation(text_encoder_2, gpu, gpu_memory_preservation)
        move_model_to_device_with_memory_preservation(image_encoder, gpu, gpu_memory_preservation)
        move_model_to_device_with_memory_preservation(vae, gpu, gpu_memory_preservation)

    # 이미지 인코딩
    print("Encoding image...")
    image_encoder_output = hf_clip_vision_encode(input_image, feature_extractor, image_encoder)
    image_encoder_last_hidden_state = image_encoder_output.last_hidden_state

    # 프롬프트 인코딩
    print("Encoding prompt...")
    llama_vec, clip_l_pooler = encode_prompt_conds(prompt, text_encoder, text_encoder_2, tokenizer, tokenizer_2)

    if cfg == 1:
        llama_vec_n, clip_l_pooler_n = torch.zeros_like(llama_vec), torch.zeros_like(clip_l_pooler)
    else:
        llama_vec_n, clip_l_pooler_n = encode_prompt_conds(n_prompt, text_encoder, text_encoder_2, tokenizer, tokenizer_2)

    # VAE 인코딩
    print("Encoding with VAE...")
    # numpy 배열을 torch tensor로 변환 (float32 필요 - replication_pad3d가 half를 지원하지 않음)
    input_tensor = torch.from_numpy(input_image).float() / 127.5 - 1.0  # normalize to [-1, 1]
    input_tensor = input_tensor.permute(2, 0, 1).unsqueeze(0).unsqueeze(0)  # HWC -> 11CHW (5D for video VAE)
    input_tensor = input_tensor.to(device=gpu, dtype=torch.float32)
    start_latent = vae_encode(input_tensor, vae)

    # Bucket 찾기
    bucket_id = find_nearest_bucket(height, width)
    print(f"Using bucket: {bucket_id}")

    # 샘플링 파라미터
    total_latent_sections = (total_second_length * 30) / (latent_window_size * 4)
    total_latent_sections = int(max(round(total_latent_sections), 1))

    # 생성기 설정
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)

    # TeaCache 설정
    if use_teacache:
        transformer.initialize_teacache(enable=True)

    # 샘플링
    print(f"Sampling {total_second_length}s video ({steps} steps)...")

    from diffusers_helper.pipelines.k_diffusion_hunyuan import sample_hunyuan

    try:
        sampled_latents = sample_hunyuan(
            transformer,
            sampler='unipc',
            width=width,
            height=height,
            frames=total_second_length * 30,
            real_guidance_scale=gs,
            distilled_guidance_scale=cfg,
            guidance_rescale=rs,
            num_inference_steps=steps,
            generator=generator,
            prompt_embeds=llama_vec,
            prompt_pooler=clip_l_pooler,
            negative_prompt_embeds=llama_vec_n,
            negative_prompt_pooler=clip_l_pooler_n,
            device=gpu,
            dtype=torch.bfloat16,
            image_embeddings=image_encoder_last_hidden_state,
            latent_indices=None,
            start_latent=start_latent,
        )
    except Exception as e:
        print(f"Sampling error: {e}")
        # CPU로 폴백
        print("Trying CPU fallback...")
        import traceback
        traceback.print_exc()
        return None

    # VAE 디코딩
    print("Decoding video...")

    if not high_vram:
        move_model_to_device_with_memory_preservation(vae, gpu, gpu_memory_preservation)

    # 비디오 저장
    print(f"Saving to {output_path}...")

    # sampled_latents를 비디오로 변환
    if sampled_latents is not None:
        save_bcthw_as_mp4(sampled_latents, output_path, fps=output_fps, crf=mp4_crf)
        print(f"Video saved: {output_path}")
    else:
        print("No latents generated!")
        return None

    # 메모리 정리
    if not high_vram:
        move_model_to_device_with_memory_preservation(transformer, cpu, gpu_memory_preservation)
        move_model_to_device_with_memory_preservation(text_encoder, cpu, gpu_memory_preservation)
        move_model_to_device_with_memory_preservation(text_encoder_2, cpu, gpu_memory_preservation)
        move_model_to_device_with_memory_preservation(image_encoder, cpu, gpu_memory_preservation)
        move_model_to_device_with_memory_preservation(vae, cpu, gpu_memory_preservation)

    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return output_path


def main():
    """메인 실행"""
    # 입력 이미지 디렉토리
    story_output = Path(r"D:\AI-Video\autonomous-creator\output\story_videos\robot_adventure_20260403_232612")
    images_dir = story_output / "images"
    videos_dir = story_output / "videos"
    videos_dir.mkdir(exist_ok=True)

    # 장면 이미지 찾기
    scene_images = sorted(images_dir.glob("scene_*.png"))

    if not scene_images:
        print("No scene images found!")
        return

    print(f"Found {len(scene_images)} scene images")

    # 각 이미지를 비디오로 변환
    results = []
    for img_path in scene_images:
        output_video = videos_dir / f"{img_path.stem}.mp4"

        try:
            result = generate_video(
                input_image_path=str(img_path),
                output_path=str(output_video),
                prompt="smooth motion, natural movement",
                n_prompt="",
                seed=31337,
                total_second_length=5.0,
                steps=25,
                cfg=1.0,
                gs=10.0,
                use_teacache=True,
                gpu_memory_preservation=6.0,
            )
            if result:
                results.append((img_path.name, result))
        except Exception as e:
            print(f"Error processing {img_path.name}: {e}")
            import traceback
            traceback.print_exc()

    # 결과 요약
    print(f"\n{'='*60}")
    print("Results Summary")
    print("=" * 60)
    for name, video in results:
        print(f"  {name} -> {video}")

    print(f"\nVideos saved to: {videos_dir}")


if __name__ == "__main__":
    main()
