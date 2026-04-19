# -*- coding: utf-8 -*-
"""
Playwright 웹 검색 - 실제 브라우저 사용으로 봇 탐지 우회
"""
import sys
import io
import asyncio

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


async def search_with_playwright(query: str, max_results: int = 10):
    """Playwright로 DuckDuckGo 검색"""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Installing playwright...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "-q"])
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
        from playwright.async_api import async_playwright

    print(f"\nSearching: {query}")

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # headless=False로 봇 탐지 우회
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        try:
            # DuckDuckGo 검색
            url = f"https://duckduckgo.com/?q={query}&ia=web"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)  # 추가 대기

            # 결과 추출
            articles = await page.query_selector_all("article[data-testid='result']")
            print(f"Found {len(articles)} results")

            for article in articles[:max_results]:
                try:
                    title_el = await article.query_selector("h2 a")
                    if title_el:
                        title = await title_el.inner_text()
                        link = await title_el.get_attribute("href")

                        snippet_el = await article.query_selector("span[data-testid='result-snippet']")
                        snippet = await snippet_el.inner_text() if snippet_el else ""

                        if link and title:
                            results.append({
                                'title': title,
                                'url': link,
                                'snippet': snippet[:150]
                            })
                except Exception as e:
                    continue

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

    return results


async def main():
    print("=" * 60)
    print("Playwright 웹 검색")
    print("=" * 60)

    queries = [
        "Stable Diffusion 3.5 LoRA anime style site:civitai.com OR site:huggingface.co",
    ]

    for query in queries:
        results = await search_with_playwright(query, max_results=10)

        if results:
            print(f"\n{'='*60}")
            print(f"Results for: {query}")
            print("=" * 60)
            for i, r in enumerate(results, 1):
                print(f"\n{i}. {r['title']}")
                print(f"   URL: {r['url']}")
                if r['snippet']:
                    print(f"   {r['snippet']}")
        else:
            print("No results found")

        await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())
