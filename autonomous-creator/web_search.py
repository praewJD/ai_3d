# -*- coding: utf-8 -*-
"""
웹 검색 스크립트 - 봇 탐지 우회
"""
import sys
import io
import time
import random

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import requests
from urllib.parse import quote_plus


def get_random_user_agent():
    """랜덤 User-Agent 반환"""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    ]
    return random.choice(user_agents)


def search_duckduckgo(query: str, max_results: int = 10) -> list:
    """DuckDuckGo 검색 (봇 탐지 덜 엄격)"""
    print(f"Searching: {query}")

    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    session = requests.Session()
    session.headers.update(headers)

    # DuckDuckGo HTML 버전 사용
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

    try:
        time.sleep(random.uniform(1, 2))  # 랜덤 지연
        response = session.get(url, timeout=15)
        response.raise_for_status()

        # 결과 파싱
        results = []
        lines = response.text.split('\n')

        for line in lines:
            if 'result__a' in line and 'href=' in line:
                # 링크 추출
                start = line.find('href="') + 6
                end = line.find('"', start)
                if start > 5 and end > start:
                    link = line[start:end]
                    if link.startswith('http') and 'duckduckgo' not in link:
                        # 제목 추출
                        title_start = line.find('>') + 1
                        title_end = line.find('<', title_start)
                        title = line[title_start:title_end] if title_end > title_start else "No title"
                        results.append({
                            'title': title.strip(),
                            'url': link
                        })
                        if len(results) >= max_results:
                            break

        return results

    except Exception as e:
        print(f"DuckDuckGo error: {e}")
        return []


def search_searx(query: str, max_results: int = 10) -> list:
    """SearX 검색 엔진 (오픈소스, 봇 탐지 없음)"""
    print(f"Searching SearX: {query}")

    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "application/json",
    }

    # 공개 SearX 인스턴스들
    instances = [
        "https://searx.be",
        "https://search.bus-hit.me",
        "https://search.rowie.at",
    ]

    for instance in instances:
        try:
            url = f"{instance}/search?q={quote_plus(query)}&format=json"
            time.sleep(random.uniform(0.5, 1.5))

            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get('results', [])[:max_results]:
                    results.append({
                        'title': item.get('title', 'No title'),
                        'url': item.get('url', ''),
                        'content': item.get('content', '')[:200]
                    })
                return results
        except Exception as e:
            print(f"SearX {instance} failed: {e}")
            continue

    return []


def main():
    print("=" * 60)
    print("웹 검색 - 봇 탐지 우회")
    print("=" * 60)

    # 검색 쿼리
    queries = [
        "Stable Diffusion 3.5 LoRA anime style",
        "SD 3.5 LoRA HuggingFace Civitai",
        "best anime LoRA for Stable Diffusion 2024"
    ]

    all_results = []

    for query in queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print("=" * 60)

        # SearX 시도 (JSON API, 더 깔끔함)
        results = search_searx(query, max_results=5)

        if not results:
            # DuckDuckGo 백업
            results = search_duckduckgo(query, max_results=5)

        if results:
            print(f"\nFound {len(results)} results:\n")
            for i, r in enumerate(results, 1):
                print(f"{i}. {r['title']}")
                print(f"   {r['url']}")
                if 'content' in r:
                    print(f"   {r['content'][:100]}...")
                print()
            all_results.extend(results)
        else:
            print("No results found")

        time.sleep(2)  # 쿼리 간 지연

    # 요약
    print(f"\n{'='*60}")
    print(f"Total results: {len(all_results)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
