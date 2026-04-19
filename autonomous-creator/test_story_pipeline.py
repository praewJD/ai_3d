# -*- coding: utf-8 -*-
"""
Story-to-Video Pipeline Test

Character extraction -> Prompt generation -> Location DB test
"""
import sys
import os
from pathlib import Path

# Set encoding
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

from infrastructure.script_parser import CharacterExtractor, SceneParser
from infrastructure.prompt import PromptBuilder, CharacterTemplate, LocationDB
from core.domain.entities.character import Character, CharacterType, CharacterAppearance


def test_character_extraction():
    """Character extraction test"""
    print("\n" + "="*50)
    print("1. Character Extraction Test")
    print("="*50)

    extractor = CharacterExtractor()

    # Thai script example
    thai_script = """
    Characters:
    - Napha: Young girl with long black hair, big eyes, wearing school uniform
    - Thana: Handsome young man with short hair, wearing black jacket

    Napha enters the classroom. Thana looks at her.
    """

    characters = extractor.extract(thai_script, "th")
    print(f"  Extracted characters: {len(characters)}")
    for char in characters:
        print(f"    - {char.name} ({char.type.value})")

    # Korean script example
    korean_script = """
    Characters:
    - Min-su: Protagonist, black-haired young man
    - Su-jin: Heroine, long-haired woman

    Min-su stands on the rooftop. Su-jin approaches.
    """

    characters = extractor.extract(korean_script, "ko")
    print(f"  Extracted characters: {len(characters)}")
    for char in characters:
        print(f"    - {char.name} ({char.type.value})")

    return characters


def test_scene_parser():
    """Scene parser test"""
    print("\n" + "="*50)
    print("2. Scene Parser Test")
    print("="*50)

    parser = SceneParser()

    script = """
    [SCENE 1] Bangkok rooftop - night
    NARRATION: The stars shine in the night sky.
    Min-su looks at the sky.

    [SCENE 2] Seoul street - evening
    Su-jin walks down the street.
    """

    scenes = parser.parse(script, "en")
    print(f"  Parsed scenes: {len(scenes)}")
    for i, scene in enumerate(scenes):
        print(f"    Scene {i+1}: {scene.location} ({scene.time_of_day})")
        if scene.dialogue:
            print(f"      Dialogue: {scene.dialogue[:30]}...")


def test_location_db():
    """Location DB test"""
    print("\n" + "="*50)
    print("3. Location DB Test")
    print("="*50)

    location_db = LocationDB()

    # Bangkok night prompt
    prompt = location_db.build_location_prompt(
        city="bangkok",
        place_type="rooftop",
        time="night"
    )
    print(f"  Bangkok Rooftop Night Prompt:")
    print(f"    {prompt[:100]}...")

    # Seoul night prompt
    prompt = location_db.build_location_prompt(
        city="seoul",
        place_type="street",
        time="night"
    )
    print(f"  Seoul Street Night Prompt:")
    print(f"    {prompt[:100]}...")

    # Available locations
    print(f"\n  Available cities: {location_db.list_cities()}")
    print(f"  Available places: {location_db.list_place_types()}")


def test_prompt_builder():
    """Prompt builder test"""
    print("\n" + "="*50)
    print("4. Prompt Builder Test")
    print("="*50)

    builder = PromptBuilder()

    # Create test character
    char = Character(
        name="Min-su",
        type=CharacterType.HERO,
        appearance=CharacterAppearance(
            gender="male",
            age="young adult",
            hair="short black hair",
            distinctive_features=["sharp eyes"]
        )
    )

    positive, negative = builder.build_character_prompt(
        character=char,
        pose="standing",
        action="looking at the night sky",
        style="cinematic"
    )

    print(f"  Positive Prompt:")
    print(f"    {positive[:150]}...")
    print(f"\n  Negative Prompt:")
    print(f"    {negative[:100]}...")


def test_character_cache():
    """Character cache test"""
    print("\n" + "="*50)
    print("5. Character Cache Test")
    print("="*50)

    from infrastructure.image.character_cache import CharacterCache

    cache = CharacterCache("data/test_cache")

    # Check cache status
    size_info = cache.get_cache_size()
    print(f"  Cache Status:")
    print(f"    Characters: {size_info['character_count']}")
    print(f"    Files: {size_info['file_count']}")
    print(f"    Size: {size_info['total_mb']:.2f} MB")

    # List cached characters
    cached = cache.list_cached()
    if cached:
        print(f"\n  Cached Characters:")
        for entry in cached:
            print(f"    - {entry.character_name} ({entry.character_id})")


def main():
    print("\n" + "="*60)
    print("  Story-to-Video Pipeline Integration Test")
    print("="*60)

    try:
        test_character_extraction()
        test_scene_parser()
        test_location_db()
        test_prompt_builder()
        test_character_cache()

        print("\n" + "="*60)
        print("  All Tests Completed!")
        print("="*60)

    except Exception as e:
        print(f"\nTest Failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
