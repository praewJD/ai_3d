# -*- coding: utf-8 -*-
"""
MiniMax API로 StoryLLMProvider + UnifiedStoryCompiler 테스트
"""
import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def test_story_llm_provider():
    """StoryLLMProvider 기본 연결 테스트"""
    print("=" * 60)
    print("Test 1: StoryLLMProvider 연결 테스트")
    print("=" * 60)

    try:
        from infrastructure.ai import StoryLLMProvider

        provider = StoryLLMProvider()
        print(f"[OK] Provider 생성됨")
        print(f"    - Model: {provider.model}")
        print(f"    - URL: {provider.api_url}")
        return provider
    except ValueError as e:
        print(f"[FAIL] API Key 미설정: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_simple_generation(provider):
    """간단한 텍스트 생성 테스트"""
    print("\n" + "=" * 60)
    print("Test 2: 간단한 텍스트 생성 테스트")
    print("=" * 60)

    if not provider:
        print("[SKIP] Provider 없음")
        return False

    try:
        response = await provider.generate(
            system_prompt="You are a helpful assistant.",
            user_message="Say hello in Korean. Just say '안녕하세요'.",
            max_tokens=100
        )
        print(f"[OK] Response: {response[:200]}")
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_unified_compiler(provider):
    """UnifiedStoryCompiler로 대본 생성 테스트"""
    print("\n" + "=" * 60)
    print("Test 3: UnifiedStoryCompiler 대본 생성")
    print("=" * 60)

    if not provider:
        print("[SKIP] Provider 없음")
        return False

    from infrastructure.story import UnifiedStoryCompiler, TargetFormat

    compiler = UnifiedStoryCompiler(llm_provider=provider)

    test_story = "옛날 옛날에 호랑이 한 마리가 살았습니다. 호랑이는 숲의 왕이었고, 모든 동물들이 두려워했습니다. 어느 날, 작은 토끼가 호랑이에게 용기를 보여줍니다."

    try:
        print(f"[*] 입력 스토리: {test_story[:50]}...")
        print("[*] 대본 생성 중...")

        result = await compiler.compile(
            raw_story=test_story,
            target_format=TargetFormat.SHORTS,
            language="ko"
        )

        if result.success:
            print(f"\n[OK] 대본 생성 성공!")
            print(f"     - Title: {result.story_spec.title}")
            print(f"     - Genre: {result.story_spec.genre}")
            print(f"     - Scenes: {len(result.story_spec.scenes)}")
            print(f"     - Duration: {result.story_spec.duration:.1f}초")
            print(f"     - Hook Score: {result.hook_score:.1f}")

            print("\n[Scene 목록]")
            for i, scene in enumerate(result.story_spec.scenes):
                print(f"  {i+1}. [{scene.purpose.value}] {scene.action[:50]}...")

            return True
        else:
            print(f"\n[FAIL] 대본 생성 실패: {result.error}")
            return False

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("\n" + "=" * 60)
    print("  MiniMax API + StoryLLMProvider 테스트")
    print("=" * 60)

    # .env 로드
    from dotenv import load_dotenv
    load_dotenv()

    print(f"\n[설정 확인]")
    print(f"  STORY_API_KEY: {'설정됨' if os.getenv('STORY_API_KEY') else '미설정'}")
    print(f"  STORY_API_URL: {os.getenv('STORY_API_URL', '기본값 사용')}")
    print(f"  STORY_MODEL: {os.getenv('STORY_MODEL', '기본값 사용')}")

    results = []

    # Test 1
    provider = await test_story_llm_provider()
    results.append(provider is not None)

    # Test 2
    if provider:
        results.append(await test_simple_generation(provider))

    # Test 3
    results.append(await test_unified_compiler(provider))

    # 결과
    print("\n" + "=" * 60)
    print("  테스트 결과")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"  {passed}/{total} 테스트 통과")

    if passed == total:
        print("\n[SUCCESS] 모든 테스트 통과!")
    else:
        print(f"\n[FAIL] {total - passed} 테스트 실패")


if __name__ == "__main__":
    asyncio.run(main())