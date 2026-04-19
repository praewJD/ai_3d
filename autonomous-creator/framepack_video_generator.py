# -*- coding: utf-8 -*-
"""
FramePack 비디오 생성기 - demo_gradio.py에서 복사
이미지 → 비디오 자동 변환
"""
import os
import sys

# FramePack 경로 설정
FRAMEPACK_DIR = r"D:\AI-Video\FramePack\FramePack_Official\webui"
HF_HOME = r"D:\AI-Video\FramePack\hf_download"

os.environ['HF_HOME'] = HF_HOME
sys.path.insert(0, FRAMEPACK_DIR)
sys.path.insert(0, os.path.join(FRAMEPACK_DIR, "diffusers_helper"))

import torch
import numpy as np
import einops
from pathlib import Path
from datetime import datetime
from PIL import Image as PILImage

# FramePack 모듈 import
from diffusers_helper.hf_login import login
from diffusers import AutoencoderKLHunyuanVideo
from transformers import LlamaModel, CLIPTextModel, LlamaTokenizerFast, CLIPTokenizer
from transformers import SiglipImageProcessor, SiglipVisionModel
from diffusers_helper.models.hunyuan_video_packed import HunyuanVideoTransformer3DModelPacked
from diffusers_helper.hunyuan import encode_prompt_conds, vae_decode, vae_encode, vae_decode_fake
from diffusers_helper.clip_vision import hf_clip_vision_encode
from diffusers_helper.memory import cpu, gpu, get_cuda_free_memory_gb, move_model_to_device_with_memory_preservation, DynamicSwapInstaller, load_model_as_complete, unload_complete_models, fake_diffusers_current_device
from diffusers_helper.bucket_tools import find_nearest_bucket
from diffusers_helper.utils import save_bcthw_as_mp4, resize_and_center_crop, generate_timestamp
from diffusers_helper.pipelines.k_diffusion_hunyuan import sample_hunyuan

# 출력 폴더
OUTPUTS_FOLDER = Path(r"D:\AI-Video\autonomous-creator\output\story_videos\robot_adventure_20260403_232612\videos")
OUTPUTS_FOLDER.mkdir(parents=True, exist_ok=True)

# 전역 변수
high_vram = False
text_encoder = None
text_encoder_2 = None
tokenizer = None
tokenizer_2 = None
vae = None
feature_extractor = None
image_encoder = None
transformer = None


def load_models():
    """모델 로드 - demo_gradio.py와 동일한 방식"""
    global high_vram, text_encoder, text_encoder_2, tokenizer, tokenizer_2
    global vae, feature_extractor, image_encoder, transformer

    print("Loading models...")

    # VRAM 확인
    try:
        free_mem_gb = get_cuda_free_memory_gb(gpu)
    except:
        free_mem_gb = 0
    high_vram = free_mem_gb > 60
    print(f'Free VRAM {free_mem_gb:.2f} GB, High-VRAM Mode: {high_vram}')

    # 모델 로드 (demo_gradio.py와 동일)
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

    # --- Non-Transformer Model Setup (demo_gradio.py와 동일) ---
    vae.eval()
    text_encoder.eval()
    text_encoder_2.eval()
    image_encoder.eval()

    vae.to(dtype=torch.float16)
    image_encoder.to(dtype=torch.float16)
    text_encoder.to(dtype=torch.float16)
    text_encoder_2.to(dtype=torch.float16)

    vae.requires_grad_(False)
    text_encoder.requires_grad_(False)
    text_encoder_2.requires_grad_(False)
    image_encoder.requires_grad_(False)

    # Transformer setup
    transformer.eval()
    transformer.high_quality_fp32_output_for_inference = True
    transformer.to(dtype=torch.bfloat16)
    transformer.requires_grad_(False)

    # Low VRAM 모드 설정 (demo_gradio.py와 동일)
    if not high_vram:
        print("Low VRAM: Enabling VAE slicing/tiling.")
        vae.enable_slicing()
        vae.enable_tiling()
        print("Low VRAM mode: Enabling DynamicSwap for Text Encoder.")
        DynamicSwapInstaller.install_model(text_encoder, device=gpu)

    print("All models loaded!")


@torch.no_grad()
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
    resolution: int = 640,
):
    """
    FramePack으로 비디오 생성 (demo_gradio.py worker 함수 기반)
    """
    global high_vram, text_encoder, text_encoder_2, tokenizer, tokenizer_2
    global vae, feature_extractor, image_encoder, transformer

    job_id = generate_timestamp()

    print(f"\n{'='*60}")
    print(f"Generating video: {Path(input_image_path).name}")
    print(f"{'='*60}")

    # 이미지 로드
    input_image = np.array(PILImage.open(input_image_path).convert("RGB"))
    img_h, img_w, _ = input_image.shape

    # 해상도 결정
    height, width = find_nearest_bucket(img_h, img_w, resolution=resolution)
    print(f"Input: {img_w}x{img_h}, Bucket: {width}x{height}")

    # 이미지 리사이즈
    input_image_np = resize_and_center_crop(input_image, target_width=width, target_height=height)

    # 텍스트 인코딩
    print("Encoding text prompt...")
    if not high_vram:
        fake_diffusers_current_device(text_encoder, gpu)
        load_model_as_complete(text_encoder_2, target_device=gpu, unload=True)
    else:
        text_encoder.to(gpu)
        text_encoder_2.to(gpu)

    llama_vec, clip_l_pooler = encode_prompt_conds(prompt, text_encoder, text_encoder_2, tokenizer, tokenizer_2)
    if float(cfg) == 1.0:
        llama_vec_n, clip_l_pooler_n = torch.zeros_like(llama_vec), torch.zeros_like(clip_l_pooler)
    else:
        llama_vec_n, clip_l_pooler_n = encode_prompt_conds(n_prompt, text_encoder, text_encoder_2, tokenizer, tokenizer_2)

    # 패딩
    from diffusers_helper.utils import crop_or_pad_yield_mask
    llama_vec, llama_attention_mask = crop_or_pad_yield_mask(llama_vec, length=512)
    llama_vec_n, llama_attention_mask_n = crop_or_pad_yield_mask(llama_vec_n, length=512)
    print("Text encoding complete.")

    # 이미지 텐서 변환
    input_image_pt = torch.from_numpy(input_image_np).float() / 127.5 - 1.0
    input_image_pt = input_image_pt.permute(2, 0, 1).unsqueeze(0).unsqueeze(2)
    print(f"Image tensor shape: {input_image_pt.shape}")

    # VAE 인코딩
    print("VAE encoding...")
    if not high_vram:
        load_model_as_complete(vae, target_device=gpu, unload=True)
    else:
        vae.to(gpu)

    start_latent = vae_encode(input_image_pt, vae)
    print(f"Start latent shape: {start_latent.shape}")

    # CLIP Vision 인코딩
    print("CLIP Vision encoding...")
    if not high_vram:
        load_model_as_complete(image_encoder, target_device=gpu, unload=True)
    else:
        image_encoder.to(gpu)

    image_encoder_output = hf_clip_vision_encode(input_image_np, feature_extractor, image_encoder)
    image_encoder_last_hidden_state = image_encoder_output.last_hidden_state

    # dtype 변환
    target_transformer_dtype = transformer.dtype
    llama_vec = llama_vec.to(target_transformer_dtype)
    llama_vec_n = llama_vec_n.to(target_transformer_dtype)
    clip_l_pooler = clip_l_pooler.to(target_transformer_dtype)
    clip_l_pooler_n = clip_l_pooler_n.to(target_transformer_dtype)
    image_encoder_last_hidden_state = image_encoder_last_hidden_state.to(target_transformer_dtype)

    # 샘플링 준비
    rnd = torch.Generator("cpu").manual_seed(seed)
    total_latent_sections = (total_second_length * output_fps) / (latent_window_size * 4)
    total_latent_sections = int(max(round(total_latent_sections), 1))
    num_frames_in_window = latent_window_size * 4 - 3

    print(f"Total sections: {total_latent_sections}, Frames per window: {num_frames_in_window}")

    # DynamicSwap 설정
    if not high_vram:
        if not hasattr(transformer, 'forge_backup_original_class'):
            print("Applying DynamicSwap to transformer...")
            DynamicSwapInstaller.install_model(transformer, device=gpu)

    # TeaCache 설정
    if use_teacache:
        transformer.initialize_teacache(enable_teacache=True, num_steps=steps)
        print("TeaCache enabled.")

    # 샘플링 루프 (F1 모드)
    print("Starting sampling loop...")
    history_latents = start_latent.to(device=cpu, dtype=torch.float32)
    history_pixels = None
    total_generated_latent_frames = 1

    for section_index in range(total_latent_sections):
        print(f"\n--- Section {section_index + 1}/{total_latent_sections} ---")

        # Transformer 로드
        if not high_vram:
            unload_complete_models(vae, image_encoder, text_encoder, text_encoder_2)
            move_model_to_device_with_memory_preservation(transformer, target_device=gpu, preserved_memory_gb=gpu_memory_preservation)
        else:
            transformer.to(gpu)

        # 인덱스 설정
        indices = torch.arange(0, sum([1, 16, 2, 1, latent_window_size]), device=cpu).unsqueeze(0)
        clean_latent_indices_start, clean_latent_4x_indices, clean_latent_2x_indices, clean_latent_1x_indices, latent_indices = \
            indices.split([1, 16, 2, 1, latent_window_size], dim=1)
        clean_latent_indices = torch.cat([clean_latent_indices_start, clean_latent_1x_indices], dim=1)

        # Conditioning latents
        num_cond_frames = 16 + 2 + 1
        if history_latents.shape[2] >= num_cond_frames:
            conditioning_latents = history_latents[:, :, -num_cond_frames:, :, :]
            clean_latents_4x, clean_latents_2x, clean_latents_1x = conditioning_latents.split([16, 2, 1], dim=2)
        else:
            padding_needed = num_cond_frames - history_latents.shape[2]
            padding_tensor = start_latent.repeat(1, 1, padding_needed, 1, 1).to(history_latents.device, history_latents.dtype)
            conditioning_latents = torch.cat([padding_tensor, history_latents], dim=2)
            clean_latents_4x, clean_latents_2x, clean_latents_1x = conditioning_latents.split([16, 2, 1], dim=2)

        clean_latents = torch.cat([start_latent.to(device=clean_latents_1x.device, dtype=clean_latents_1x.dtype), clean_latents_1x], dim=2)

        # 샘플링
        device_kwargs = {'device': gpu, 'dtype': torch.bfloat16}
        text_kwargs = {'device': gpu, 'dtype': target_transformer_dtype}
        latent_kwargs = {'device': gpu, 'dtype': torch.bfloat16}

        generated_latents = sample_hunyuan(
            transformer=transformer,
            sampler='unipc',
            width=width,
            height=height,
            frames=num_frames_in_window,
            real_guidance_scale=float(cfg),
            distilled_guidance_scale=float(gs),
            guidance_rescale=float(rs),
            num_inference_steps=steps,
            generator=rnd,
            prompt_embeds=llama_vec.to(**text_kwargs),
            prompt_embeds_mask=llama_attention_mask.to(gpu),
            prompt_poolers=clip_l_pooler.to(**text_kwargs),
            negative_prompt_embeds=llama_vec_n.to(**text_kwargs),
            negative_prompt_embeds_mask=llama_attention_mask_n.to(gpu),
            negative_prompt_poolers=clip_l_pooler_n.to(**text_kwargs),
            image_embeddings=image_encoder_last_hidden_state.to(**text_kwargs),
            latent_indices=latent_indices.to(gpu),
            clean_latents=clean_latents.to(**latent_kwargs),
            clean_latent_indices=clean_latent_indices.to(gpu),
            clean_latents_2x=clean_latents_2x.to(**latent_kwargs),
            clean_latent_2x_indices=clean_latent_2x_indices.to(gpu),
            clean_latents_4x=clean_latents_4x.to(**latent_kwargs),
            clean_latent_4x_indices=clean_latent_4x_indices.to(gpu),
            device=gpu,
            dtype=torch.bfloat16,
        )

        generated_latents = generated_latents.to(device=cpu, dtype=torch.float32)
        history_latents = torch.cat([history_latents, generated_latents], dim=2)
        num_new_latent_frames = generated_latents.shape[2]
        total_generated_latent_frames += num_new_latent_frames
        print(f"Generated {num_new_latent_frames} latent frames. Total: {total_generated_latent_frames}")

        # VAE 디코딩
        if not high_vram:
            from diffusers_helper.memory import offload_model_from_device_for_memory_preservation
            offload_model_from_device_for_memory_preservation(transformer, target_device=gpu, preserved_memory_gb=8)
            load_model_as_complete(vae, target_device=gpu, unload=False)
        else:
            vae.to(gpu)

        real_history_latents = history_latents.to(gpu, vae.dtype)

        from diffusers_helper.utils import soft_append_bcthw
        if history_pixels is None:
            history_pixels = vae_decode(real_history_latents, vae).cpu()
        else:
            num_latents_to_decode_slice = latent_window_size * 2
            decode_start_index = max(0, real_history_latents.shape[2] - num_latents_to_decode_slice)
            latents_to_decode_slice = real_history_latents[:, :, decode_start_index:, :, :]
            current_pixels_slice = vae_decode(latents_to_decode_slice, vae).cpu()
            append_overlap_pixels = latent_window_size * 4 - 3
            history_pixels = soft_append_bcthw(history_pixels, current_pixels_slice, append_overlap_pixels)

        print(f"Pixel history shape: {history_pixels.shape}")

        if not high_vram:
            vae.to(cpu)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    # 최종 비디오 저장
    print(f"\nSaving video: {output_path}")
    save_bcthw_as_mp4(history_pixels, output_path, fps=output_fps, crf=mp4_crf)
    print(f"Video saved! Total frames: {history_pixels.shape[2]}")

    return output_path


def main():
    """메인 실행"""
    print("=" * 60)
    print("FramePack Video Generator")
    print("(Based on demo_gradio.py worker function)")
    print("=" * 60)

    # 모델 로드
    load_models()

    # 입력 이미지 찾기
    images_dir = Path(r"D:\AI-Video\autonomous-creator\output\story_videos\robot_adventure_20260403_232612\images")
    scene_images = sorted(images_dir.glob("scene_*.png"))

    if not scene_images:
        print("No scene images found!")
        return

    print(f"\nFound {len(scene_images)} scene images")

    # 각 이미지를 비디오로 변환
    results = []
    for img_path in scene_images:
        output_video = OUTPUTS_FOLDER / f"{img_path.stem}.mp4"

        try:
            # 프롬프트에 동작 추가
            motion_prompt = "camera slowly zooming in, gentle character movement, flowing hair, subtle breathing, alive atmosphere"

            result = generate_video(
                input_image_path=str(img_path),
                output_path=str(output_video),
                prompt=motion_prompt,
                seed=31337,
                total_second_length=5.0,
                steps=35,  # 스텝 증가
                cfg=1.0,
                gs=15.0,  # guidance scale 증가
                use_teacache=False,  # TeaCache 끄기
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

    print(f"\nVideos saved to: {OUTPUTS_FOLDER}")


if __name__ == "__main__":
    main()
