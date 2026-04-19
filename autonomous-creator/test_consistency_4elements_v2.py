# -*- coding: utf-8 -*-
"""
4요소 일관성 테스트 - IP-Adapter 없이 LoRA + Seed로만

SDXL + Disney LoRA + IP-Adapter + 고정 Seed로 캐릭터 일관성 테스트

테스트 시나리오:
1. Phase 1: 참조 이미지 1장 생성 (LoRA + Seed)
2. Phase 2: 참조 이미지 기반으로 IP-Adapter 적용
   - 같은 캐릭터, 다른 장면(숲, 도시, 해변, 액션)에서 일관성 유지
3. Phase 3: 재현성 테스트 (같은 seed로 같은 이미지 2장 생성)

캐릭터 설정:
- character_id: "disney_girl"
- character_seed: 12345
- 캐릭터 기본 외형: "cute young girl with big expressive eyes, wearing red dress"
- scenes: 같은 장면에서 다른 장면 생성

- output_dir: D:\AI-Video\autonomous-creator\test_outputs\consistency_test
- trigger_words: MG_ip, pixar
    - lora_path: D:/AI-Video/autonomous-creator/data/lora/3dModel_sdxl_v2.safetensors
    - lora_weight: 0.85
    - lora_enabled: True  # LoRA 적용 여면

    - ip_adapter_enabled: True
    - ip_adapter_model_path: models/ip-adapter
    - ip_adapter_subfolder: sdxl_models
    - ip_adapter_weight_name: ip-adapter_sdxl.safetensors
    - ip_adapter_scale: 0.7
    - reference_strength: 0.7
    - controlnet_weight: 0.75
    - seed: 12345  # 고정 seed

    - cross_attention_kwargs: {"scale": lora_weight} if lora_enabled else None
    - seed_manager: SeedManager =    seed_manager.lock(character_id, character_seed)
        - Seed 고정
        - 캐릭터 외형 일관성 유지
        - 다양한 장면 테스트

    - reference_image: 참조 이미지 (캐릭터 일관성 유지용)
            self.set_reference_image(ref_path)
        # Phase 1: LoRA + Seed (참조 이미지 생성)
        print(f"\nGenerating reference image for character: {character_id}")

        first_scene = scenes[0]
        image = tester.generate(
            prompt=first_scene["prompt"],
            seed=character_seed,
            use_lora=lora_loaded,
            use_ip_adapter=False,  # IP-Adapter 없이
        )

        if image:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = OUTPUT_dir / f"phase1_reference_{timestamp}.png"
            image.save(output_path, quality=95)
            generated_images.append(output_path)
            print(f"  Saved: {output_path.name}")

            # Phase 2: LoRA + IP-Adapter + Seed (일관성 테스트)
            if ip_adapter_loaded:
                print("\n" + "=" * 60)
                print("Phase 2: LoRA + IP-Adapter + Fixed Seed")
                print("=" * 60)

                # 첫 번째 이미지를 참조 이미지로 설정
                tester.set_reference_image(output_path)

                for scene in scenes[1:]:
                    print(f"\n--- {scene['scene_id']}: {scene['desc']} ---")

                    image = tester.generate(
                        prompt=scene["prompt"],
                        seed=character_seed,
                        use_lora=lora_loaded,
                        use_ip_adapter=True,  # IP-Adapter 적용
                    )

                    if image:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        output_path = OUTPUT_DIR / f"phase2_{scene['scene_id']}_{timestamp}.png"
                        image.save(output_path, quality=95)
                        generated_images.append(output_path)
                        print(f"  Saved: {output_path.name}")

            # Phase 3: 재현성 테스트 (같은 seed로 같은 이미지 2장 생성)
            print("\n" + "=" * 60)
            print("Phase 3: Reproducibility Test (Same Seed)")
            print("=" * 60)

            test_scene = scenes[0]
            for retry in range(2):
                print(f"\n--- Retry {retry +1} ---")

                image = tester.generate(
                    prompt=test_scene["prompt"],
                    seed=character_seed,  # 동일 seed
                    use_lora=lora_loaded,
                    use_ip_adapter=False,  # IP-Adapter 없이 재현성 테스트
                )
                if image:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_path = OUTPUT_DIR / f"phase3_retry{retry + 1}_{timestamp}.png"
                    image.save(output_path, quality=95)
                    generated_images.append(output_path)
                    print(f"  Saved: {output_path.name}")

                # Phase 3: 재현성 테스트 완료 (같은 seed)
                    print("\n" + "=" * 60)
                    print("Phase 3: Reproducibility Test (Same Seed)")
                    print("=" * 60)

    # 정리
    tester.unload()

    # 결과 요약
    print("\n" + "=" * 60)
            print("Generated Files:")
            print("=" * 60)

            for f in sorted(OUTPUT_DIR.glob("*.png")):
                size_kb = f.stat().st_size / 1024
                print(f"  {f.name}: {size_kb:.1f} KB")
            else:
                print(f"  [Error] Phase 2 not executed - skipping")
                print("  IP-Adapter not loaded - skipping Phase 2")
                print("  IP-Adapter 적용 실패 - run test manually: pip install ip-adapter")
                print("  Run test manually: pip install ip-adapter")
                continue

            # IP-Adapter 로드는식 다시 시도
            print("[IP-Adapter] Loading from h94/IP-Adapter...")
            self.pipeline.load_ip_adapter(
                "h94/IP-Adapter",
                subfolder="sdxl_models",
                weight_name="ip-adapter_sdxl.safetensors",
            )
            self.pipeline.set_ip_adapter_scale(CONFIG["ip_adapter_scale"])

            print(f"[IP-Adapter] Loaded successfully! (scale: {CONFIG['ip_adapter_scale']})            return True
        except Exception as e:
            print(f"[IP-Adapter] Load failed: {e}")
            import traceback
            traceback.print_exc()
            return False

        else:
            print("[IP-Adapter] not loaded - skipping Phase 2")
            print("  Proceeding without IP-Adapter...")
            return

