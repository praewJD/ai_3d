# -*- coding: utf-8 -*-
"""
프롬프트 확장기 - 간단한 타이틀을 구체적인 이미지 프롬프트로 변환
"""
import sys
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# 도시/장소 특징 데이터베이스
LOCATION_DB = {
    "방콕": {
        "bangkok": {
            "elements": ["tuk-tuks", "Thai street food vendors", "BTS skytrain", "pink and green taxis",
                        "Thai script neon signs", "wat temple roofs", "tropical palm trees", "humid atmosphere"],
            "colors": ["neon pink", "green", "orange", "warm yellow"],
            "atmosphere": "chaotic, vibrant, tropical humidity, rainy season",
            "negative": "chinese, hong kong, japanese, korean, chinese characters, red lanterns"
        }
    },
    "서울": {
        "seoul": {
            "elements": ["modern skyscrapers", "Korean hangul signs", "street food pojangmacha",
                        "N Seoul Tower view", "Korean taxis", "crosswalks", "convenience stores",
                        "Korean pedestrians", "neon signage"],
            "colors": ["blue LED", "white", "red accents", "neon"],
            "atmosphere": "modern urban, busy, clean streets, winter cold or summer humid",
            "negative": "chinese, japanese, thai, tropical"
        }
    },
    "도쿄": {
        "tokyo": {
            "elements": ["Japanese neon signs", "Shibuya crossing", "vending machines",
                        "Japanese taxis", "izakaya lanterns", "train stations", "salarymen",
                        "concrete buildings", "illuminated billboards"],
            "colors": ["cyan", "magenta", "white", "red"],
            "atmosphere": "cyberpunk, organized chaos, futuristic, neon-soaked",
            "negative": "chinese, korean, thai"
        }
    },
    "홍콩": {
        "hong kong": {
            "elements": ["dense high-rises", "neon signs vertical stacks", "trams", "Chinese characters",
                        "dim sum restaurants", "harbor view", "narrow streets", "laundry hanging",
                        "old vs new architecture"],
            "colors": ["red", "gold", "cyan", "warm yellow"],
            "atmosphere": "dense, vertical, humid, east meets west",
            "negative": "japanese, korean, thai"
        }
    },
    "상하이": {
        "shanghai": {
            "elements": ["Oriental Pearl Tower", "Bund waterfront", "modern glass towers",
                        "Chinese lanterns", "Huangpu River", "colonial buildings", "neon billboards"],
            "colors": ["red", "gold", "blue LED", "purple"],
            "atmosphere": "futuristic, grand scale, mix of old and new",
            "negative": "japanese, korean, thai"
        }
    }
}

# 시간대 특징
TIME_DB = {
    "밤": "night scene, neon lights, dark sky, street lights, illuminated signs, bokeh",
    "낮": "daytime, natural lighting, blue sky, sunlight, busy streets",
    "저녁": "golden hour, sunset, warm lighting, long shadows, transitioning to night",
    "새벽": "dawn, soft light, misty, empty streets, blue hour"
}

# 분위기 템플릿
MOOD_TEMPLATES = {
    "cinematic": "cinematic composition, dramatic lighting, film grain, anamorphic lens, color graded",
    "documentary": "documentary photography, raw, authentic, unfiltered, National Geographic style",
    "cyberpunk": "cyberpunk aesthetic, neon soaked, rain reflections, high contrast, futuristic",
    "nostalgic": "vintage feel, film photography, warm tones, soft focus, nostalgic mood",
    "dramatic": "dramatic shadows, high contrast, intense lighting, powerful composition"
}


def expand_prompt(title: str, mood: str = "cinematic") -> tuple:
    """
    타이틀을 확장된 프롬프트로 변환

    Args:
        title: 예) "방콕의 밤", "서울의 밤", "도쿄의 밤"
        mood: cinematic, documentary, cyberpunk, nostalgic, dramatic

    Returns:
        (positive_prompt, negative_prompt)
    """
    # 도시/장소 추출
    location_data = None
    location_name = None

    for kr_name, en_data in LOCATION_DB.items():
        if kr_name in title:
            location_name = list(en_data.keys())[0]
            location_data = list(en_data.values())[0]
            break

    if not location_data:
        # 기본값
        location_name = "city"
        location_data = {
            "elements": ["urban streets", "neon lights", "buildings", "pedestrians", "vehicles"],
            "colors": ["neon", "warm lights"],
            "atmosphere": "urban night life",
            "negative": "rural, nature, countryside"
        }

    # 시간대 추출
    time_prompt = "night scene, neon lights"  # 기본값
    for kr_time, en_prompt in TIME_DB.items():
        if kr_time in title:
            time_prompt = en_prompt
            break

    # 분위기 템플릿
    mood_prompt = MOOD_TEMPLATES.get(mood, MOOD_TEMPLATES["cinematic"])

    # 프롬프트 조합
    elements_str = ", ".join(location_data["elements"][:6])
    colors_str = ", ".join(location_data["colors"])

    positive_prompt = f"""{location_name} {time_prompt},
{elements_str},
{colors_str} lighting,
{location_data['atmosphere']},
{mood_prompt},
photorealistic, 8k, high detail"""

    negative_prompt = f"""blurry, low quality, cartoon, anime, watermark, text, oversaturated,
{location_data['negative']}"""

    return positive_prompt.strip(), negative_prompt.strip()


def test():
    print("=" * 60)
    print("프롬프트 확장 테스트")
    print("=" * 60)

    titles = [
        "방콕의 밤",
        "서울의 밤",
        "도쿄의 밤",
        "홍콩의 밤",
    ]

    for title in titles:
        print(f"\n{'='*60}")
        print(f"입력: {title}")
        print("-" * 60)
        pos, neg = expand_prompt(title, mood="cinematic")
        print(f"Positive:\n{pos}")
        print(f"\nNegative:\n{neg}")


if __name__ == "__main__":
    test()
