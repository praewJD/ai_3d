"""
Character System Example - 캐릭터 시스템 사용 예시

Disney 3D 스타일 캐릭터 생성 및 관리
"""
import asyncio
from infrastructure.character import (
    get_character_library,
    get_character_generator,
    DISNEY_3D_TEMPLATES,
    HAIR_STYLES,
    OUTFIT_TEMPLATES
)
from core.domain.entities.character.character import (
    CharacterType,
    CharacterRole,
    CharacterGender
)


async def main():
    # 캐릭터 생성기 및 라이브러리 초기화
    generator = get_character_generator()
    library = get_character_library()

    # ============================================================
    # 1. 주인공 캐릭터 생성 (Disney 3D 스타일)
    # ============================================================
    print("=== 주인공 캐릭터 생성 ===")

    ella = await generator.create_character(
        name="엘라",
        character_type=CharacterType.PROTAGONIST,
        role=CharacterRole.HERO,
        gender=CharacterGender.FEMALE,
        description="마법의 힘을 가진 공주. 차가운 외모와 달리 따뜻한 마음을 가짐",
        appearance_details={
            "age": "young adult",
            "face": "large expressive blue eyes, small delicate nose, heart-shaped face",
            "hair": "long flowing platinum blonde hair, side braid",
            "body": "slender elegant build, graceful posture",
            "skin": "fair porcelain skin",
            "eye_color": "ice blue"
        },
        default_outfit="ice blue ball gown with snowflake patterns, translucent cape",
        personality=["kind", "protective", "reserved", "powerful"],
        generate_reference=True
    )

    print(f"생성됨: {ella.name}")
    print(f"프롬프트: {ella.get_full_prompt(expression='happy')}")

    # ============================================================
    # 2. 조연 캐릭터 생성
    # ============================================================
    print("\n=== 조연 캐릭터 생성 ===")

    olaf = await generator.create_character(
        name="올라프",
        character_type=CharacterType.SUPPORTING,
        role=CharacterRole.COMIC_RELIEF,
        gender=CharacterGender.MALE,
        description="사랑스러운 눈사람. 여름을 동경함",
        appearance_details={
            "body": "cute snowman, carrot nose, stick arms, warm smile",
            "face": "large friendly eyes, carrot nose, big smile"
        },
        default_outfit="no clothes (snowman)",
        personality=["cheerful", "innocent", "loyal", "funny"]
    )

    print(f"생성됨: {olaf.name}")

    # ============================================================
    # 3. 동물 캐릭터 생성
    # ============================================================
    print("\n=== 동물 캐릭터 생성 ===")

    sven = await generator.create_animal(
        name="스벤",
        species="reindeer",
        description="충성스러운 순록. 간식을 좋아함",
        appearance_details={
            "features": "large antlers, warm brown fur, expressive eyes",
            "accessories": "red saddle"
        },
        personality=["loyal", "hungry", "playful"]
    )

    print(f"생성됨: {sven.name}")

    # ============================================================
    # 4. 캐릭터 의상 변형 추가
    # ============================================================
    print("\n=== 의상 변형 추가 ===")

    await generator.add_outfit_variant(
        character_id=ella.id,
        variant_name="coronation",
        outfit_description="elegant coronation dress, green and purple, crown"
    )

    await generator.add_outfit_variant(
        character_id=ella.id,
        variant_name="casual",
        outfit_description="simple blue dress, comfortable for travel"
    )

    # ============================================================
    # 5. 장면용 프롬프트 생성
    # ============================================================
    print("\n=== 장면 프롬프트 생성 ===")

    # 엘라와 올라프가 함께 있는 장면
    scene_prompt = await generator.get_scene_prompt(
        character_ids=[ella.id, olaf.id],
        scene_description="snowy mountain landscape, northern lights in sky",
        expressions={ella.id: "happy", olaf.id: "excited"},
        poses={ella.id: "standing", olaf.id: "standing"},
        outfits={ella.id: "default", olaf.id: "default"}
    )

    print("장면 프롬프트:")
    print(scene_prompt[:200] + "...")

    # ============================================================
    # 6. 캐릭터 검색 및 관리
    # ============================================================
    print("\n=== 캐릭터 관리 ===")

    # 모든 주인공 조회
    protagonists = await library.get_protagonists()
    print(f"주인공 수: {len(protagonists)}")

    # 이름으로 검색
    found = await library.get_by_name("엘라")
    print(f"검색 결과: {found.name if found else '없음'}")

    # 통계
    stats = await library.get_stats()
    print(f"라이브러리 통계: {stats}")

    # ============================================================
    # 7. 에피소드에 캐릭터 등록
    # ============================================================
    print("\n=== 에피소드 등록 ===")

    # 캐릭터에 에피소드 추가
    ella.add_episode("episode_001")
    ella.add_episode("episode_002")
    await library.save(ella)

    # 에피소드별 등장 캐릭터 조회
    ep1_chars = await library.get_episode_characters("episode_001")
    print(f"에피소드 1 등장 캐릭터: {[c.name for c in ep1_chars]}")


if __name__ == "__main__":
    asyncio.run(main())
