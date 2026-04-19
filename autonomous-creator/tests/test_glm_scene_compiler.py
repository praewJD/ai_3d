# -*- coding: utf-8 -*-
"""
GLM Provider + SceneCompiler 테스트

GLM API를 사용하여 SceneGraph 생성 테스트
"""
import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_glm_provider():
    """GLM Provider 기본 테스트"""
    print("=" * 50)
    print("Test 1: GLM Provider Basic")
    print("=" * 50)

    from infrastructure.api.providers.llm import create_glm_provider

    try:
        llm = create_glm_provider()
        print(f"[OK] GLM Provider created: {llm.model_name}")
        print(f"[OK] Provider name: {llm.provider_name}")
        print(f"[OK] Supported models: {llm.get_supported_models()}")
        return llm
    except ValueError as e:
        print(f"[SKIP] GLM API key not configured: {e}")
        print("[INFO] Set GLM_API_KEY environment variable to run this test")
        return None
    except Exception as e:
        print(f"[ERROR] {e}")
        return None


async def test_glm_generate(llm):
    """GLM 텍스트 생성 테스트"""
    print("\n" + "=" * 50)
    print("Test 2: GLM Text Generation")
    print("=" * 50)

    if not llm:
        print("[SKIP] No LLM provider")
        return False

    try:
        response = await llm.generate(
            prompt="Say 'Hello, World!' in JSON format with a greeting field.",
            system_prompt="You are a helpful assistant. Return only JSON.",
            max_tokens=100
        )
        print(f"[OK] Response: {response[:200]}...")
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


async def test_scene_compiler_with_glm():
    """SceneCompiler + GLM 통합 테스트"""
    print("\n" + "=" * 50)
    print("Test 3: SceneCompiler + GLM Integration")
    print("=" * 50)

    from infrastructure.scene.scene_compiler import SceneCompiler
    from infrastructure.api.providers.llm import create_glm_provider

    try:
        llm = create_glm_provider()
    except ValueError as e:
        print(f"[SKIP] GLM API key not configured: {e}")
        return True  # API 키 없으면 스킵

    compiler = SceneCompiler(llm_provider=llm)

    story = """
    숲속에서 길을 잃은 소녀 이야기

    어둠이 내리는 숲속, 한 소녀가 나무 사이를 헤매고 있다.
    두려움에 떨며 앞을 보는데, 멀리 희미한 빛이 보인다.
    소녀는 빛을 따라 걷기 시작하고, 마침내 숲을 빠져나온다.
    밝은 곳에는 아름다운 정원이 펼쳐져 있었다.
    """

    try:
        print("[*] Compiling story with GLM...")
        result = await compiler.compile(story)

        if result.success:
            print(f"[OK] Compilation successful!")
            print(f"[OK] Scenes: {len(result.scene_graph.scenes)}")
            print(f"[OK] Title: {result.scene_graph.title}")
            print(f"[OK] Fixes applied: {result.fixes_applied}")

            for i, scene in enumerate(result.scene_graph.scenes):
                print(f"\n  Scene {i+1}: {scene.description[:50]}...")
                print(f"    Camera: {scene.camera_angle.value}")
                print(f"    Mood: {scene.mood.value}")
                print(f"    Duration: {scene.duration_seconds}s")

            return True
        else:
            print(f"[FAIL] Compilation failed: {result.errors}")
            return False

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_api_config():
    """API 설정 테스트"""
    print("\n" + "=" * 50)
    print("Test 4: API Config Check")
    print("=" * 50)

    from infrastructure.api.config.api_config import get_api_config

    config = get_api_config()

    print(f"[OK] Available LLM providers: {config.get_available_llm_providers()}")
    print(f"[OK] Recommended provider: {config.get_recommended_llm_provider()}")
    print(f"[OK] Has GLM: {config.has_glm}")
    print(f"[OK] Has Claude: {config.has_claude}")
    print(f"[OK] Has OpenAI: {config.has_openai}")

    if config.has_glm:
        print(f"[OK] GLM Model: {config.glm_model}")
        print(f"[OK] GLM API URL: {config.glm_api_url}")

    return True


async def main():
    """메인 테스트"""
    print("\n" + "=" * 60)
    print("  GLM Provider + SceneCompiler Test Suite")
    print("=" * 60)

    results = []

    # 1. API 설정 확인
    results.append(await test_api_config())

    # 2. GLM Provider 생성
    llm = await test_glm_provider()

    # 3. 텍스트 생성 테스트
    if llm:
        results.append(await test_glm_generate(llm))

    # 4. SceneCompiler 통합 테스트
    results.append(await test_scene_compiler_with_glm())

    # 결과
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"  Results: {passed}/{total} passed")
    print("=" * 60)

    if passed == total:
        print("\n[SUCCESS] All tests passed!")
    else:
        print(f"\n[PARTIAL] {total - passed} tests failed")

    print("\n[*] To use GLM API:")
    print("    1. Get API key from https://open.bigmodel.cn/")
    print("    2. Set GLM_API_KEY in .env file")
    print("    3. Run this test again")


if __name__ == "__main__":
    asyncio.run(main())
