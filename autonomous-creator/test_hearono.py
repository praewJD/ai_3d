# -*- coding: utf-8 -*-
"""
Hearono Episode 1 - Full Pipeline Test

태국어 스크립트 → 영상 생성 전체 파이프라인
"""
import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime

os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.path.insert(0, str(Path(__file__).parent))

# 스크립트
HEARONO_SCRIPT = """
ตัวละครหลัก:
• ฮีโรโน (Hearono): เด็กหนุ่มที่มีพลังพิเศษในการ "ได้ยิน" และควบคุม "คลื่นเสียง" เขาซ่อนตัวตนอยู่ภายใต้ชุดคลุมที่มีฮู้ดและหูฟังตัดเสียงขนาดใหญ่
• เรเวน (Raven): วายร้ายที่สามารถสร้างคลื่นเสียงทำลายล้างเพื่อควบคุมผู้คน

ตอนที่ 1: เมืองที่เงียบงัน (30 วินาที)
• [ฉาก: ทิวทัศน์ยามค่ำคืนของกรุงเทพฯ ปี 20xx - เงียบผิดปกติ ไม่มีเสียงรถยนต์]
• [มุมกล้อง: ต่ำ] รองเท้าบูทของ เรเวน (Raven) เหยียบพื้นคอนกรีต ค่อยๆ เดินขึ้นไปบนยอดตึก
• เสียงพากย์ (เรเวน): "โลกนี้... มันดังเกินไป... มันถึงเวลาของความเงียบที่แท้จริง"

ตอนที่ 2: ความเงียบชั่วคราว (30 วินาที)
• [ภาพตัด: กองบัญชาการตำรวจ] จอภาพแสดงสถานะ: WARNING: Sonic Attack in Progress
• เอกนัด (ตะโกน): "ใครก็ได้! ติดต่อศูนย์วิจัย ค้นหาคลื่นความถี่ที่ตรงกันข้าม!"
• [ภาพตัด: ฮีโรโน ยืนขึ้นบนขอบตึก] เขาถอดหูฟังออก แววตามุ่งมั่น

ตอนที่ 3: เพลงสุดท้าย (30 วินาที)
• [ภาพตัด: เรเวน หันมาเห็นฮีโรโน] ยิ้มเย็น
• เรเวน: "แกจะทำอะไรได้? เสียงแกจะดักแค่ไหน ก็สู้ความเงียบไม่ได้หรอก"
• [ภาพตัด: ฮีโรโน กระโดดลงมาจากตึก] ชกหมัดที่มีคลื่นเสียงไปที่เครื่องส่งสัญญาณ
• เสียงพากย์ (ฮีโรโน): "ฉันไม่เคยต้องการให้ใครได้ยิน... แต่ถ้ามันเพื่อปกป้องเสียงของทุกคน... นี่คือเพลงสุดท้ายของฉัน"
• [ฉากสุดท้าย] หูฟังขนาดใหญ่ตกอยู่เพียงข้างเดียว
"""

OUTPUT_DIR = Path("D:/AI-Video/autonomous-creator/output/hearono_ep1")


async def test_character_extraction():
    """1. 캐릭터 추출"""
    print("\n" + "="*50)
    print("Step 1: Character Extraction")
    print("="*50)

    from infrastructure.script_parser import CharacterExtractor

    extractor = CharacterExtractor()
    characters = extractor.extract(HEARONO_SCRIPT, "th")

    print(f"  Extracted: {len(characters)} characters")
    for char in characters:
        print(f"    - {char.name} ({char.type.value})")

    # 캐릭터 섹션에서도 추출
    section_chars = extractor.extract_from_character_section(HEARONO_SCRIPT, "th")
    print(f"  From character section: {len(section_chars)} characters")
    for char in section_chars:
        print(f"    - {char.name} ({char.type.value})")

    return characters + section_chars


async def test_scene_parsing():
    """2. 장면 파싱"""
    print("\n" + "="*50)
    print("Step 2: Scene Parsing")
    print("="*50)

    from infrastructure.script_parser import SceneParser

    parser = SceneParser()
    scenes = parser.parse(HEARONO_SCRIPT, "th")

    print(f"  Parsed: {len(scenes)} scenes")
    for i, scene in enumerate(scenes):
        print(f"    Scene {i+1}: {scene.location} ({scene.time_of_day})")

    return scenes


async def test_prompt_building(characters):
    """3. 프롬프트 빌딩"""
    print("\n" + "="*50)
    print("Step 3: Prompt Building")
    print("="*50)

    from infrastructure.prompt import PromptBuilder, CharacterTemplate, LocationDB
    from core.domain.entities.character import Character, CharacterType, CharacterAppearance

    builder = PromptBuilder(
        CharacterTemplate(),
        LocationDB()
    )

    # 캐릭터가 없으면 수동 생성
    if not characters:
        hearono = Character(
            name="Hearono",
            name_local="ฮีโรโน",
            type=CharacterType.HERO,
            appearance=CharacterAppearance(
                gender="male",
                age="young adult",
                hair="short dark hair",
                clothing=["hooded cloak", "large headphones"],
                distinctive_features=["determined eyes"]
            )
        )
        raven = Character(
            name="Raven",
            name_local="เรเวน",
            type=CharacterType.VILLAIN,
            appearance=CharacterAppearance(
                gender="male",
                age="adult",
                hair="dark hair",
                clothing=["black armor", "air tubes"],
                distinctive_features=["menacing look"]
            )
        )
        characters = [hearono, raven]

    # 각 캐릭터 프롬프트
    prompts = []
    for char in characters[:2]:
        pos, neg = builder.build_character_prompt(
            character=char,
            pose="standing",
            action="looking at the city",
            style="cinematic"
        )
        prompts.append({
            "character": char.name,
            "positive": pos,
            "negative": neg
        })
        print(f"  {char.name}:")
        print(f"    Positive: {pos[:80]}...")

    # 장소 프롬프트
    location_prompt = builder.location_db.build_location_prompt(
        city="bangkok_night_20xx",
        place_type="rooftop",
        time="night"
    )
    print(f"\n  Location (Bangkok 20xx rooftop night):")
    print(f"    {location_prompt[:80]}...")

    return prompts


async def test_audio_generation():
    """4. 오디오 생성"""
    print("\n" + "="*50)
    print("Step 4: Audio Generation (TTS)")
    print("="*50)

    from infrastructure.tts.factory import TTSFactory
    from core.domain.entities.audio import VoiceSettings

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    audio_dir = OUTPUT_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    tts = TTSFactory.create("th")
    voice = VoiceSettings(language="th", speed=1.0)

    # 주요 대사
    dialogues = [
        ("raven_01", "โลกนี้... มันดังเกินไป... มันถึงเวลาของความเงียบที่แท้จริง"),
        ("eknat_01", "ใครก็ได้! ติดต่อศูนย์วิจัย ค้นหาคลื่นความถี่ที่ตรงกันข้าม!"),
        ("hearono_01", "ฉันไม่เคยต้องการให้ใครได้ยิน... แต่ถ้ามันเพื่อปกป้องเสียงของทุกคน... นี่คือเพลงสุดท้ายของฉัน"),
    ]

    audio_paths = []
    for name, text in dialogues:
        output_path = str(audio_dir / f"{name}.wav")
        print(f"  Generating: {name}...")
        try:
            await tts.generate(text, voice, output_path)
            size = os.path.getsize(output_path) / 1024
            print(f"    Done: {size:.1f} KB")
            audio_paths.append(output_path)
        except Exception as e:
            print(f"    Error: {e}")

    return audio_paths


async def test_image_prompt_generation(characters):
    """5. 이미지 프롬프트 생성 (실제 생성은 별도)"""
    print("\n" + "="*50)
    print("Step 5: Image Prompt Generation")
    print("="*50)

    from infrastructure.prompt import PromptBuilder, CharacterTemplate, LocationDB
    from core.domain.entities.character import Character, CharacterType, CharacterAppearance

    builder = PromptBuilder(CharacterTemplate(), LocationDB())

    # 캐릭터가 없으면 수동 생성
    if not characters:
        hearono = Character(
            name="Hearono",
            name_local="ฮีโรโน",
            type=CharacterType.HERO,
            appearance=CharacterAppearance(
                gender="male",
                age="young adult",
                hair="short dark hair",
                clothing=["hooded cloak", "large headphones"],
                distinctive_features=["determined eyes"]
            )
        )
        raven = Character(
            name="Raven",
            name_local="เรเวน",
            type=CharacterType.VILLAIN,
            appearance=CharacterAppearance(
                gender="male",
                age="adult",
                hair="dark hair",
                clothing=["black armor", "air tubes"],
                distinctive_features=["menacing look"]
            )
        )
        characters = [hearono, raven]

    # 장면별 프롬프트
    scenes = [
        {
            "name": "scene_01_raven_enters",
            "description": "Raven walking up to rooftop, Bangkok 20xx night",
            "character": characters[1] if len(characters) > 1 else None,
            "location": {"city": "bangkok_night_20xx", "place": "rooftop", "time": "night"}
        },
        {
            "name": "scene_02_hearono_reveals",
            "description": "Hearono stands on rooftop, removing headphones",
            "character": characters[0] if characters else None,
            "location": {"city": "bangkok_night_20xx", "place": "rooftop", "time": "night"}
        },
        {
            "name": "scene_03_final_battle",
            "description": "Hearono jumping with sonic punch at transmitter",
            "character": characters[0] if characters else None,
            "location": {"city": "bangkok_night_20xx", "place": "rooftop", "time": "night"}
        },
        {
            "name": "scene_04_headphones",
            "description": "Single headphone left on ground, smoke clearing",
            "character": None,
            "location": {"city": "bangkok_night_20xx", "place": "rooftop", "time": "night"}
        }
    ]

    image_prompts = []
    for scene in scenes:
        # 장소 프롬프트
        loc_prompt = builder.location_db.build_location_prompt(
            city=scene["location"]["city"],
            place_type=scene["location"]["place"],
            time=scene["location"]["time"]
        )

        # 캐릭터 프롬프트
        if scene["character"]:
            char_pos, char_neg = builder.build_character_prompt(
                character=scene["character"],
                pose="action",
                action=scene["description"],
                style="cinematic"
            )
            full_prompt = f"{char_pos}, {loc_prompt}"
        else:
            full_prompt = f"{scene['description']}, {loc_prompt}, cinematic, 8k"

        image_prompts.append({
            "name": scene["name"],
            "prompt": full_prompt[:500]  # 500자 제한
        })
        print(f"  {scene['name']}:")
        print(f"    {full_prompt[:100]}...")

    # 프롬프트 파일 저장
    prompt_file = OUTPUT_DIR / "image_prompts.txt"
    with open(prompt_file, 'w', encoding='utf-8') as f:
        for p in image_prompts:
            f.write(f"=== {p['name']} ===\n")
            f.write(f"{p['prompt']}\n\n")

    print(f"\n  Saved to: {prompt_file}")

    return image_prompts


async def main():
    """메인 테스트 실행"""
    print("="*60)
    print("  HEARONO Episode 1 - Full Pipeline Test")
    print("="*60)
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Output: {OUTPUT_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: 캐릭터 추출
        characters = await test_character_extraction()

        # Step 2: 장면 파싱
        scenes = await test_scene_parsing()

        # Step 3: 프롬프트 빌딩
        prompts = await test_prompt_building(characters)

        # Step 4: 오디오 생성
        audio_paths = await test_audio_generation()

        # Step 5: 이미지 프롬프트 생성
        image_prompts = await test_image_prompt_generation(characters)

        # 요약
        print("\n" + "="*60)
        print("  Pipeline Test Complete!")
        print("="*60)
        print(f"  Characters: {len(characters)}")
        print(f"  Scenes: {len(scenes)}")
        print(f"  Audio files: {len(audio_paths)}")
        print(f"  Image prompts: {len(image_prompts)}")
        print(f"\n  Output directory: {OUTPUT_DIR}")

        # 다음 단계 안내
        print("\n  Next steps:")
        print("  1. Run image generation with SD 3.5")
        print("  2. Run video generation with SVD")
        print("  3. Compose final video")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
