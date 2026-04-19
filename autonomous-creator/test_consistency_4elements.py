# -*- coding: utf-8 -*-
"""
4요소 일관성 테스트 (LoRA + IP-Adapter + Seed + ControlNet)

SDXL + Disney LoRA + IP-Adapter + 고정 Seed로 캐릭터 일관성 테스트
"""

import sys
import io
from pathlib import Path
from datetime import datetime
import os
import hashlib

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 출력 디렉토리
OUTPUT_DIR = Path("D:/AI-Video/autonomous-creator/test_outputs/consistency_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 설정
CONFIG = {
    # 베이스 모델
    "base_model": "stabilityai/stable-diffusion-xl-base-1.0",

    # LoRA 설정
    "lora_path": "D:/AI-Video/autonomous-creator/data/lora/3dModel_sdxl_v2.safetensors",
    "lora_weight": 0.85,
    "trigger_words": "MG_ip, pixar",

    # IP-Adapter 설정 (SDXL용)
    "ip_adapter_model": "h94/IP-Adapter",
    "ip_adapter_subfolder": "sdxl_models",
    "ip_adapter_weight": "ip-adapter_sdxl.safetensors",
    "ip_adapter_scale": 0.7,

    # ControlNet 설정 (OpenPose - SDXL용)
    "controlnet_model": "thibaud/controlnet-openpose-sdxl-1.0",
    "controlnet_scale": 0.7,  # 포즈 고정 강화

    # Seed 설정
    "character_seed": 12345,  # 고정 seed

    # 생성 설정
    "width": 768,
    "height": 1024,
    "steps": 35,
    "guidance_scale": 7.5,

    # Negative Prompt (배경 요소 제거)
    "negative_prompt": (
        "blurry, low quality, distorted, watermark, text, bad anatomy, "
        "butterflies, animals, creatures, extra objects, insects, birds, "
        "flying objects, multiple characters, crowd, background clutter"
    ),
}


class SeedManager:
    """간단한 Seed 관리자"""

    def __init__(self):
        self.seeds = {}

    def get_or_create(self, char_id: str) -> int:
        if char_id not in self.seeds:
            hash_val = hash(char_id)
            self.seeds[char_id] = abs(hash_val) % 2147483647
        return self.seeds[char_id]

    def lock(self, char_id: str, seed: int):
        self.seeds[char_id] = seed


class ConsistencyTester:
    """4요소 일관성 테스터"""

    def __init__(self):
        self.pipeline = None
        self.ip_adapter = None
        self.controlnet = None
        self.seed_manager = SeedManager()
        self.reference_image = None
        self.reference_pose = None  # ControlNet용 OpenPose 이미지
        self.openpose_detector = None  # OpenPose 디텍터

    def load_controlnet(self) -> bool:
        """ControlNet (OpenPose) 로드"""
        import torch
        from diffusers import ControlNetModel

        try:
            print(f"[ControlNet] Loading {CONFIG['controlnet_model']}...")

            self.controlnet = ControlNetModel.from_pretrained(
                CONFIG["controlnet_model"],
                torch_dtype=torch.float16,
            )
            print(f"[ControlNet] Loaded successfully!")
            return True
        except Exception as e:
            print(f"[ControlNet] Load failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def load_openpose_detector(self) -> bool:
        """OpenPose 디텍터 로드 (controlnet_aux)"""
        try:
            from controlnet_aux import OpenposeDetector

            print(f"[OpenPose] Loading detector...")
            self.openpose_detector = OpenposeDetector.from_pretrained("lllyasviel/ControlNet")
            print(f"[OpenPose] Detector loaded successfully!")
            return True
        except Exception as e:
            print(f"[OpenPose] Load failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def load_model(self):
        """SDXL 모델 로드 (ControlNet 포함)"""
        import torch
        from diffusers import StableDiffusionXLControlNetPipeline

        print(f"\n[SDXL] Loading {CONFIG['base_model']}...")

        # ControlNet이 로드된 경우 ControlNet용 파이프라인 사용
        if self.controlnet:
            self.pipeline = StableDiffusionXLControlNetPipeline.from_pretrained(
                CONFIG["base_model"],
                controlnet=self.controlnet,
                torch_dtype=torch.float16,
                variant="fp16",
                use_safetensors=True,
            )
            print(f"[SDXL] Loaded with ControlNet")
        else:
            from diffusers import StableDiffusionXLPipeline
            self.pipeline = StableDiffusionXLPipeline.from_pretrained(
                CONFIG["base_model"],
                torch_dtype=torch.float16,
                variant="fp16",
                use_safetensors=True,
            )
            print(f"[SDXL] Loaded without ControlNet")

        # RTX 3060 (6GB) 최적화
        self.pipeline.enable_model_cpu_offload()

        print(f"[SDXL] Model loaded (CPU offload mode)")

    def load_lora(self) -> bool:
        """LoRA 로드"""
        from pathlib import Path

        local_path = Path(CONFIG["lora_path"])

        if not local_path.exists():
            print(f"[LoRA] File not found: {local_path}")
            return False

        try:
            print(f"[LoRA] Loading into pipeline...")
            self.pipeline.load_lora_weights(
                str(local_path.parent),
                weight_name=local_path.name,
            )
            print(f"[LoRA] Loaded successfully!")
            return True
        except Exception as e:
            print(f"[LoRA] Load failed: {e}")
            return False

    def load_ip_adapter(self) -> bool:
        """IP-Adapter 로드 (diffusers 내장 방식)"""
        try:
            print(f"[IP-Adapter] Loading from {CONFIG['ip_adapter_model']}...")

            # diffusers 내장 IP-Adapter 로드
            self.pipeline.load_ip_adapter(
                CONFIG["ip_adapter_model"],
                subfolder=CONFIG["ip_adapter_subfolder"],
                weight_name=CONFIG["ip_adapter_weight"],
            )
            self.pipeline.set_ip_adapter_scale(CONFIG["ip_adapter_scale"])

            self.ip_adapter = True  # 로드됨 표시

            print(f"[IP-Adapter] Loaded successfully! (scale: {CONFIG['ip_adapter_scale']})")
            return True

        except Exception as e:
            print(f"[IP-Adapter] Load failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def set_reference_image(self, image):
        """참조 이미지 설정 (IP-Adapter + ControlNet용)"""
        from PIL import Image

        if isinstance(image, (str, Path)):
            self.reference_image = Image.open(image).convert("RGB")
        else:
            self.reference_image = image.convert("RGB")

        print(f"[Reference] Set: {self.reference_image.size}")

        # ControlNet용 OpenPose 이미지 생성
        if self.controlnet and self.openpose_detector:
            # OpenPose로 포즈 추출
            print(f"[ControlNet] Extracting pose with OpenPose...")
            self.reference_pose = self.openpose_detector(self.reference_image)
            # 생성할 이미지 크기로 리사이즈
            self.reference_pose = self.reference_pose.resize((CONFIG["width"], CONFIG["height"]))
            print(f"[ControlNet] OpenPose image prepared: {self.reference_pose.size}")

    def prepare_image_embeds(self, image):
        """IP-Adapter용 이미지 임베딩 준비 (디바이스 호환성 처리)

        Returns:
            3D tensor [2, 1, embed_dim] for CFG (negative, positive)
        """
        import torch
        from PIL import Image
        import numpy as np

        # image_encoder의 디바이스 확인
        if hasattr(self.pipeline, 'image_encoder') and self.pipeline.image_encoder is not None:
            encoder_device = next(self.pipeline.image_encoder.parameters()).device
            encoder_dtype = next(self.pipeline.image_encoder.parameters()).dtype
        else:
            encoder_device = "cpu"
            encoder_dtype = torch.float32

        # 이미지 전처리
        from transformers import CLIPImageProcessor
        image_processor = CLIPImageProcessor()

        if image is None:
            image = Image.fromarray(np.zeros((224, 224, 3), dtype=np.uint8))

        # 이미지를 텐서로 변환
        pixel_values = image_processor(images=image, return_tensors="pt").pixel_values
        pixel_values = pixel_values.to(device=encoder_device, dtype=encoder_dtype)

        # 이미지 인코딩
        with torch.no_grad():
            image_embeds = self.pipeline.image_encoder(pixel_values).image_embeds

        # negative 임베딩 생성 (zero)
        negative_image_embeds = torch.zeros_like(image_embeds)

        # CFG를 위한 배치 구성
        # image_embeds shape: [1, embed_dim] -> unsqueeze -> [1, 1, embed_dim]
        # negative shape: [1, embed_dim] -> unsqueeze -> [1, 1, embed_dim]
        # concat on dim=0 -> [2, 1, embed_dim]
        image_embeds = image_embeds.unsqueeze(0)  # [1, 1, embed_dim]
        negative_image_embeds = negative_image_embeds.unsqueeze(0)  # [1, 1, embed_dim]
        image_embeds = torch.cat([negative_image_embeds, image_embeds], dim=0)  # [2, 1, embed_dim]

        return image_embeds

    def generate(
        self,
        prompt: str,
        seed: int,
        use_lora: bool = True,
        use_ip_adapter: bool = False,
        use_controlnet: bool = False,
        width: int = None,
        height: int = None,
    ):
        """이미지 생성"""
        import torch
        from PIL import Image
        import numpy as np

        width = width or CONFIG["width"]
        height = height or CONFIG["height"]

        # 프롬프트 구성
        full_prompt = prompt
        if use_lora:
            full_prompt = f"{CONFIG['trigger_words']}, {prompt}"

        print(f"\n[Generate]")
        print(f"  Prompt: {full_prompt[:80]}...")
        print(f"  Seed: {seed}")
        print(f"  LoRA: {'ON' if use_lora else 'OFF'}")
        print(f"  IP-Adapter: {'ON' if use_ip_adapter else 'OFF'}")
        print(f"  ControlNet: {'ON' if use_controlnet else 'OFF'}")

        # Generator
        generator = torch.Generator(device="cpu").manual_seed(seed)

        # IP-Adapter 설정 - ip_adapter_image_embeds를 직접 전달해야 함
        # (added_cond_kwargs로 전달하면 파이프라인 내부에서 덮어씌워짐)
        ip_adapter_image_embeds = None

        if self.ip_adapter:
            # IP-Adapter가 로드된 경우 항상 image_embeds 필요
            if use_ip_adapter and self.reference_image:
                # IP-Adapter 사용 - scale 복원
                self.pipeline.set_ip_adapter_scale(CONFIG["ip_adapter_scale"])
                print(f"  Preparing IP-Adapter embeds from reference image...")
                image_embeds = self.prepare_image_embeds(self.reference_image)
            else:
                # IP-Adapter 사용 안 함 - scale 0으로 설정
                self.pipeline.set_ip_adapter_scale(0.0)
                print(f"  IP-Adapter scale set to 0 (disabled)")
                # 빈 이미지 임베딩 전달 (필수)
                print(f"  Preparing empty IP-Adapter embeds...")
                image_embeds = self.prepare_image_embeds(None)

            # ip_adapter_image_embeds must be a list of tensors
            ip_adapter_image_embeds = [image_embeds]
            print(f"  ip_adapter_image_embeds prepared with shape: {image_embeds.shape}")

        # ControlNet 이미지 준비
        # ControlNet 파이프라인은 항상 image가 필요함
        controlnet_image = None
        if self.controlnet:
            if use_controlnet and self.reference_pose:
                controlnet_image = self.reference_pose
                print(f"  ControlNet image: {controlnet_image.size}")
            else:
                # ControlNet 사용 안 함 - 빈 이미지로 대체
                # 빈 검은색 이미지는 포즈가 없음을 의미
                controlnet_image = Image.new("RGB", (width, height), (0, 0, 0))
                print(f"  ControlNet image: Empty (black) - disabled via scale 0")

        # 일반 생성 (LoRA + IP-Adapter + ControlNet)
        cross_attention_kwargs = {"scale": CONFIG["lora_weight"]} if use_lora else None

        # ControlNet conditioning scale - 사용 안 할 때는 0으로 설정
        controlnet_scale = CONFIG["controlnet_scale"] if use_controlnet else 0.0

        # 파이프라인 호출 - ControlNet 파이프라인 사용
        if self.controlnet:
            result = self.pipeline(
                prompt=full_prompt,
                negative_prompt=CONFIG["negative_prompt"],
                num_inference_steps=CONFIG["steps"],
                guidance_scale=CONFIG["guidance_scale"],
                width=width,
                height=height,
                generator=generator,
                cross_attention_kwargs=cross_attention_kwargs,
                ip_adapter_image_embeds=ip_adapter_image_embeds,
                image=controlnet_image,  # ControlNet 입력 (필수)
                controlnet_conditioning_scale=controlnet_scale,
            )
        else:
            # 일반 생성 (ControlNet 없음)
            result = self.pipeline(
                prompt=full_prompt,
                negative_prompt=CONFIG["negative_prompt"],
                num_inference_steps=CONFIG["steps"],
                guidance_scale=CONFIG["guidance_scale"],
                width=width,
                height=height,
                generator=generator,
                cross_attention_kwargs=cross_attention_kwargs,
                ip_adapter_image_embeds=ip_adapter_image_embeds,
            )

        return result.images[0]

    def unload(self):
        """메모리 정리"""
        if self.pipeline:
            del self.pipeline
            self.pipeline = None
        if self.ip_adapter:
            del self.ip_adapter
            self.ip_adapter = None
        if self.controlnet:
            del self.controlnet
            self.controlnet = None
        if self.openpose_detector:
            del self.openpose_detector
            self.openpose_detector = None
        import torch
        import gc
        gc.collect()
        torch.cuda.empty_cache()
        print("[Cleanup] Done")


def test_consistency():
    """일관성 테스트 실행 (4요소: LoRA + IP-Adapter + Seed + ControlNet)"""
    print("=" * 60)
    print("4-Element Consistency Test")
    print("(LoRA + IP-Adapter + Seed + ControlNet)")
    print("=" * 60)
    print(f"Output: {OUTPUT_DIR}")

    tester = ConsistencyTester()

    # ControlNet 로드 (모델 로드 전에 먼저)
    controlnet_loaded = tester.load_controlnet()

    # OpenPose 디텍터 로드
    openpose_loaded = tester.load_openpose_detector()

    # SDXL 모델 로드 (ControlNet과 함께)
    tester.load_model()

    # LoRA 로드
    lora_loaded = tester.load_lora()

    # IP-Adapter 로드 시도
    ip_adapter_loaded = tester.load_ip_adapter()

    # 테스트 캐릭터 설정
    character_id = "disney_girl"
    character_seed = CONFIG["character_seed"]
    tester.seed_manager.lock(character_id, character_seed)

    # 캐릭터 기본 외형 (배경 요소 제거된 버전)
    character_base = "cute young girl with big expressive eyes, wearing red dress"

    # 테스트 장면들 (같은 캐릭터, 다른 장면) - 배경 요소 제거
    scenes = [
        {
            "scene_id": "forest",
            "prompt": f"{character_base}, standing in magical forest, soft dappled lighting, trees in background",
            "desc": "마법의 숲속 장면"
        },
        {
            "scene_id": "city",
            "prompt": f"{character_base}, walking through futuristic city at night, neon lights reflecting in her eyes, cyberpunk atmosphere",
            "desc": "미래 도시 장면"
        },
        {
            "scene_id": "ocean",
            "prompt": f"{character_base}, standing on beach at sunset, golden hour lighting, waves gently rolling, peaceful expression",
            "desc": "해변 일몰 장면"
        },
        {
            "scene_id": "action",
            "prompt": f"{character_base}, dynamic action pose, wind blowing through hair, epic background, dramatic lighting, determined expression",
            "desc": "액션 장면"
        },
    ]

    generated_images = []

    # Phase 1: LoRA + Seed (참조 이미지 생성)
    print("\n" + "=" * 60)
    print("Phase 1: LoRA + Fixed Seed (Reference Generation)")
    print("=" * 60)

    print(f"\nGenerating reference image for character: {character_id}")

    first_scene = scenes[0]
    image = tester.generate(
        prompt=first_scene["prompt"],
        seed=character_seed,
        use_lora=lora_loaded,
        use_ip_adapter=False,
        use_controlnet=False,
    )

    if image:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUT_DIR / f"phase1_reference_{timestamp}.png"
        image.save(output_path, quality=95)
        generated_images.append(output_path)
        print(f"  Saved: {output_path.name}")

        # Phase 2: LoRA + IP-Adapter + Seed + ControlNet (4요소 일관성 테스트)
        if ip_adapter_loaded and controlnet_loaded and openpose_loaded:
            print("\n" + "=" * 60)
            print("Phase 2: LoRA + IP-Adapter + Seed + ControlNet (OpenPose)")
            print("=" * 60)

            # 첫 번째 이미지를 참조 이미지로 설정 (IP-Adapter + ControlNet용)
            tester.set_reference_image(output_path)

            # ControlNet OpenPose 이미지도 저장 (디버깅용)
            if tester.reference_pose:
                pose_path = OUTPUT_DIR / f"phase2_openpose_reference_{timestamp}.png"
                tester.reference_pose.save(pose_path, quality=95)
                print(f"  OpenPose saved: {pose_path.name}")

            for scene in scenes[1:]:
                print(f"\n--- {scene['scene_id']}: {scene['desc']} ---")

                image = tester.generate(
                    prompt=scene["prompt"],
                    seed=character_seed,
                    use_lora=lora_loaded,
                    use_ip_adapter=True,
                    use_controlnet=True,
                )

                if image:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_path = OUTPUT_DIR / f"phase2_{scene['scene_id']}_{timestamp}.png"
                    image.save(output_path, quality=95)
                    generated_images.append(output_path)
                    print(f"  Saved: {output_path.name}")

        elif ip_adapter_loaded:
            # ControlNet 없이 IP-Adapter만 사용
            print("\n" + "=" * 60)
            print("Phase 2: LoRA + IP-Adapter + Fixed Seed (No ControlNet)")
            print("=" * 60)

            tester.set_reference_image(output_path)

            for scene in scenes[1:]:
                print(f"\n--- {scene['scene_id']}: {scene['desc']} ---")

                image = tester.generate(
                    prompt=scene["prompt"],
                    seed=character_seed,
                    use_lora=lora_loaded,
                    use_ip_adapter=True,
                    use_controlnet=False,
                )

                if image:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_path = OUTPUT_DIR / f"phase2_{scene['scene_id']}_{timestamp}.png"
                    image.save(output_path, quality=95)
                    generated_images.append(output_path)
                    print(f"  Saved: {output_path.name}")

        # Phase 3: 재현성 테스트 (같은 seed로 재생성)
        print("\n" + "=" * 60)
        print("Phase 3: Reproducibility Test (Same Seed)")
        print("=" * 60)

        test_scene = scenes[0]  # 첫 번째 장면으로 재현성 테스트

        for retry in range(2):
            print(f"\n--- Retry {retry + 1} ---")

            image = tester.generate(
                prompt=test_scene["prompt"],
                seed=character_seed,  # 동일 seed
                use_lora=lora_loaded,
                use_ip_adapter=False,
                use_controlnet=False,
            )

            if image:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = OUTPUT_DIR / f"phase3_retry{retry + 1}_{timestamp}.png"
                image.save(output_path, quality=95)
                generated_images.append(output_path)
                print(f"  Saved: {output_path.name}")

    # 정리
    tester.unload()

    # 결과 요약
    print("\n" + "=" * 60)
    print("Generated Files:")
    print("=" * 60)

    for f in sorted(OUTPUT_DIR.glob("*.png")):
        size_kb = f.stat().st_size / 1024
        print(f"  {f.name}: {size_kb:.1f} KB")

    print("\n" + "=" * 60)
    print("4-Element Consistency Test Summary:")
    print("=" * 60)
    print(f"- LoRA: {'Applied' if lora_loaded else 'Not Applied'}")
    print(f"- IP-Adapter: {'Applied' if ip_adapter_loaded else 'Not Available'}")
    print(f"- ControlNet: {'Applied (OpenPose)' if controlnet_loaded else 'Not Available'}")
    print(f"- Fixed Seed: {character_seed}")
    print(f"- Total Images: {len(generated_images)}")

    print("\nComparison:")
    print("1. Phase 1 vs Phase 2: Check 4-element (LoRA+IP-Adapter+ControlNet+Seed) effect")
    print("2. Phase 2 images: Same character pose in different scenes (check face/outfit consistency)")
    print("3. Phase 3: Same seed should produce identical images")
    print("\n4-Element Parameters:")
    print(f"  - LoRA weight: {CONFIG['lora_weight']}")
    print(f"  - IP-Adapter scale: {CONFIG['ip_adapter_scale']}")
    print(f"  - ControlNet scale: {CONFIG['controlnet_scale']}")


if __name__ == "__main__":
    test_consistency()
