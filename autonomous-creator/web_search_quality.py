# -*- coding: utf-8 -*-
"""
SD 3.5 vs SDXL+LoRA 품질 비교 검색
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
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        try:
            url = f"https://duckduckgo.com/?q={query}&ia=web"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

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
                                'snippet': snippet[:200]
                            })
                except:
                    continue

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

    return results


async def main():
    print("=" * 60)
    print("SD 3.5 vs SDXL+LoRA 품질 비교 검색")
    print("=" * 60)

    queries = [
        "Stable Diffusion 3.5 vs SDXL LoRA quality comparison reddit",
        "SD 3.5 medium review anime style 2024",
        "Stable Diffusion 3.5 worth it vs SDXL reddit",
    ]

    all_results = []

    for query in queries:
        results = await search_with_playwright(query, max_results=8)

        if results:
            print(f"\n{'='*60}")
            print(f"Results for: {query}")
            print("=" * 60)
            for i, r in enumerate(results, 1):
                print(f"\n{i}. {r['title']}")
                print(f"   URL: {r['url']}")
                if r['snippet']:
                    print(f"   {r['snippet']}")
                all_results.append(r)
        else:
            print("No results found")

        await asyncio.sleep(2)

    print(f"\n{'='*60}")
    print(f"Total: {len(all_results)} results")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
