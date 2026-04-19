"""
Character Generator - Disney 3D 스타일 캐릭터 생성

일관된 캐릭터 프롬프트 및 참조 이미지 생성
"""
import asyncio
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging
import json

from core.domain.entities.character.character import (
    Character,
    CharacterType,
    CharacterRole,
    CharacterGender,
    create_protagonist,
    create_animal_character
)
from infrastructure.character.character_library import CharacterLibrary, get_character_library
from infrastructure.image.style_consistency import StyleConsistencyManager

logger = logging.getLogger(__name__)


# ============================================================
# Disney 3D 스타일 템플릿
# ============================================================

DISNEY_3D_TEMPLATES = {
    # 성별/나이별 기본 템플릿
    "young_female": {
        "face": "large expressive eyes, small delicate nose, soft cheeks, heart-shaped face",
        "body": "slender build, youthful appearance, graceful posture",
        "expressions": {
            "happy": "bright warm smile, sparkling eyes, rosy cheeks",
            "sad": "tearful eyes, trembling lips, downcast gaze",
            "determined": "focused eyes, slight frown, strong stance",
            "surprised": "wide eyes, slightly open mouth, raised eyebrows"
        }
    },
    "young_male": {
        "face": "defined jawline, expressive eyes, confident features",
        "body": "athletic build, broad shoulders, energetic stance",
        "expressions": {
            "happy": "confident smile, bright eyes",
            "sad": "downcast eyes, somber expression",
            "determined": "intense gaze, set jaw",
            "surprised": "wide eyes, alert posture"
        }
    },
    "adult_female": {
        "face": "elegant features, defined cheekbones, graceful appearance",
        "body": "elegant posture, refined movements",
        "expressions": {
            "happy": "warm gentle smile, kind eyes",
            "sad": "melancholic expression, distant gaze",
            "determined": "strong gaze, composed expression"
        }
    },
    "adult_male": {
        "face": "mature features, strong jawline, wise eyes",
        "body": "strong build, commanding presence",
        "expressions": {
            "happy": "warm genuine smile",
            "sad": "heavy expression, troubled look",
            "determined": "resolute gaze, firm expression"
        }
    },
    "child": {
        "face": "round cheeks, large innocent eyes, small features",
        "body": "small stature, energetic movements",
        "expressions": {
            "happy": "beaming smile, bright excited eyes",
            "sad": "pouty lips, teary eyes",
            "surprised": "wide amazed eyes, open mouth"
        }
    },
    "elderly": {
        "face": "kind wrinkles, warm eyes, gentle features",
        "body": "slight build, wise posture",
        "expressions": {
            "happy": "warm knowing smile, crinkled eyes",
            "sad": "weary expression, distant memories",
            "wise": "thoughtful gaze, serene expression"
        }
    }
}

# 머리 스타일 템플릿
HAIR_STYLES = {
    "long_straight": "long flowing straight hair, silky and smooth",
    "long_wavy": "long wavy hair, romantic curls",
    "long_braided": "long braided hair, intricate braid style",
    "medium_wavy": "medium length wavy hair, tousled look",
    "short_neat": "short neatly styled hair, clean cut",
    "short_messy": "short messy hair, casual style",
    "ponytail": "hair in a ponytail, sporty look",
    "bun": "hair in an elegant bun, sophisticated",
    "curly": "natural curly hair, bouncy curls",
    "afro": "beautiful afro hairstyle, voluminous"
}

# 의상 템플릿
OUTFIT_TEMPLATES = {
    # 판타지
    "royal_gown": "elegant royal gown with intricate embroidery, flowing fabric",
    "warrior_armor": "heroic armor with ornate details, battle-ready",
    "mage_robe": "mystical robe with magical patterns, flowing sleeves",
    "peasant_clothes": "simple rustic clothing, humble appearance",

    # 현대
    "casual_modern": "modern casual outfit, comfortable clothes",
    "formal_suit": "elegant formal suit, sophisticated",
    "school_uniform": "neat school uniform, youthful",
    "adventure_gear": "practical adventure outfit, ready for journey",

    # 시대별
    "medieval_dress": "medieval style dress, period accurate",
    "victorian": "Victorian era clothing, elegant and modest",
    "1920s_flapper": "1920s flapper style, art deco inspired",
    "futuristic": "futuristic clothing, sci-fi aesthetic"
}

# 동물 템플릿
ANIMAL_TEMPLATES = {
    "dog": {
        "appearance": "adorable dog character, fluffy fur, expressive eyes",
        "expressions": {
            "happy": "wagging tail, bright eyes, happy bark expression",
            "sad": "droopy ears, sad puppy eyes",
            "excited": "perked ears, energetic pose"
        }
    },
    "cat": {
        "appearance": "elegant cat character, sleek fur, mysterious eyes",
        "expressions": {
            "happy": "content purring expression, half-closed eyes",
            "curious": "alert ears, wide curious eyes",
            "playful": "mischievous expression, playful pose"
        }
    },
    "bird": {
        "appearance": "colorful bird character, beautiful feathers, bright eyes",
        "expressions": {
            "happy": "cheerful chirping expression, puffed feathers",
            "curious": "head tilted, alert eyes"
        }
    },
    "horse": {
        "appearance": "majestic horse character, flowing mane, strong build",
        "expressions": {
            "proud": "head held high, proud stance",
            "gentle": "soft eyes, gentle expression"
        }
    },
    "rabbit": {
        "appearance": "cute rabbit character, soft fluffy fur, long ears",
        "expressions": {
            "happy": "twitching nose, bright happy eyes",
            "scared": "ears back, wide worried eyes"
        }
    },
    "dragon": {
        "appearance": "majestic dragon character, scaled skin, powerful wings",
        "expressions": {
            "fierce": "glowing eyes, fierce expression",
            "friendly": "kind eyes, gentle smile"
        }
    }
}


class CharacterGenerator:
    """
    Disney 3D 스타일 캐릭터 생성기

    일관된 캐릭터 프롬프트와 참조 이미지 생성
    """

    DISNEY_STYLE_PREFIX = (
        "Disney 3D animation style, Pixar quality, "
        "smooth cel shading, beautiful lighting, "
        "clean renders, expressive features"
    )

    def __init__(
        self,
        library: CharacterLibrary = None,
        style_manager: StyleConsistencyManager = None
    ):
        self.library = library or get_character_library()
        self.style_manager = style_manager

    # ============================================================
    # 캐릭터 생성
    # ============================================================

    async def create_character(
        self,
        name: str,
        character_type: CharacterType,
        gender: CharacterGender,
        age_group: str = "young",
        role: CharacterRole = CharacterRole.BACKGROUND,
        description: str = "",
        personality: List[str] = None,
        appearance_overrides: Dict[str, str] = None,
        generate_reference: bool = False
    ) -> Character:
        """
        캐릭터 생성

        Args:
            name: 이름
            character_type: 타입 (주인공, 조연, 동물 등)
            gender: 성별
            age_group: 연령대 (young, adult, child, elderly)
            role: 역할
            description: 설명
            personality: 성격 특성
            appearance_overrides: 외형 오버라이드
            generate_reference: 참조 이미지 생성 여부

        Returns:
            생성된 캐릭터
        """
        # 템플릿 선택
        if character_type == CharacterType.ANIMAL:
            return await self._create_animal(
                name=name,
                species=description.split()[0] if description else "dog",
                description=description,
                generate_reference=generate_reference
            )

        # 템플릿 키 생성
        template_key = f"{age_group}_{gender.value}"
        template = DISNEY_3D_TEMPLATES.get(template_key, DISNEY_3D_TEMPLATES["young_female"])

        # 오버라이드 적용
        overrides = appearance_overrides or {}

        # 캐릭터 생성
        character = Character(
            name=name,
            type=character_type,
            gender=gender,
            role=role,
            description=description,
            personality=personality or [],
            # 외형
            face_description=overrides.get("face", template.get("face", "")),
            body_description=overrides.get("body", template.get("body", "")),
            hair_description=overrides.get("hair", ""),
            eye_color=overrides.get("eye_color", ""),
            skin_tone=overrides.get("skin_tone", "fair skin"),
            # 의상
            default_outfit=overrides.get("outfit", ""),
            # 표정
            expressions=template.get("expressions", {})
        )

        # 전체 외형 프롬프트 생성
        character.appearance_prompt = self._build_appearance_prompt(character)

        # 참조 이미지 생성
        if generate_reference and self.style_manager:
            await self._generate_reference_image(character)

        # 저장
        await self.library.save(character)

        logger.info(f"Character created: {name} ({character.id})")
        return character

    async def _create_animal(
        self,
        name: str,
        species: str,
        description: str = "",
        generate_reference: bool = False
    ) -> Character:
        """동물 캐릭터 생성"""
        # 동물 템플릿 찾기
        species_lower = species.lower()
        template = ANIMAL_TEMPLATES.get(species_lower, ANIMAL_TEMPLATES["dog"])

        character = Character(
            name=name,
            type=CharacterType.ANIMAL,
            gender=CharacterGender.ANIMAL,
            description=description or f"A {species} character",
            appearance_prompt=f"{template['appearance']}, Disney style",
            expressions=template.get("expressions", {}),
            motion_style="animal-like movements"
        )

        if generate_reference and self.style_manager:
            await self._generate_reference_image(character)

        await self.library.save(character)
        return character

    def _build_appearance_prompt(self, character: Character) -> str:
        """전체 외형 프롬프트 구성"""
        parts = []

        # 기본
        parts.append(character.name)

        # 성별/나이
        if character.gender != CharacterGender.UNKNOWN:
            gender_str = character.gender.value
            parts.append(gender_str)

        # 얼굴
        if character.face_description:
            parts.append(character.face_description)

        # 머리
        if character.hair_description:
            parts.append(character.hair_description)
        if character.eye_color:
            parts.append(f"{character.eye_color} eyes")
        if character.skin_tone:
            parts.append(character.skin_tone)

        # 체형
        if character.body_description:
            parts.append(character.body_description)

        # 의상
        if character.default_outfit:
            parts.append(f"wearing {character.default_outfit}")

        # 액세서리
        if character.accessories:
            parts.append(", ".join(character.accessories))

        return ", ".join(parts)

    # ============================================================
    # 참조 이미지 생성
    # ============================================================

    async def _generate_reference_image(
        self,
        character: Character,
        output_dir: str = "data/characters/references"
    ) -> Optional[str]:
        """참조 이미지 생성"""
        if not self.style_manager:
            logger.warning("Style manager not available for reference generation")
            return None

        output_path = Path(output_dir) / character.type.value / f"{character.id}_ref.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 참조용 프롬프트 (정면, 단순 배경)
        ref_prompt = (
            f"{self.DISNEY_STYLE_PREFIX}, "
            f"{character.get_full_prompt(expression='neutral', pose='standing')}, "
            f"front view, simple background, reference sheet style, "
            f"character design, turn around reference"
        )

        try:
            # 이미지 생성
            images = await self.style_manager.generator.generate(
                prompt=ref_prompt,
                negative_prompt=character.get_negative_prompt(),
                output_path=str(output_path),
                width=768,
                height=1024
            )

            if images:
                character.reference_image_path = str(output_path)
                await self.library.save(character)
                logger.info(f"Reference image generated: {output_path}")
                return str(output_path)

        except Exception as e:
            logger.error(f"Failed to generate reference image: {e}")

        return None

    # ============================================================
    # 캐릭터 변형
    # ============================================================

    async def add_outfit_variant(
        self,
        character_id: str,
        variant_name: str,
        outfit_description: str
    ) -> Optional[Character]:
        """의상 변형 추가"""
        character = await self.library.load(character_id)
        if not character:
            return None

        character.outfit_variants[variant_name] = outfit_description
        return await self.library.save(character)

    async def add_expression(
        self,
        character_id: str,
        expression_name: str,
        expression_description: str
    ) -> Optional[Character]:
        """표정 추가"""
        character = await self.library.load(character_id)
        if not character:
            return None

        character.expressions[expression_name] = expression_description
        return await self.library.save(character)

    async def add_pose(
        self,
        character_id: str,
        pose_name: str,
        pose_description: str
    ) -> Optional[Character]:
        """포즈 추가"""
        character = await self.library.load(character_id)
        if not character:
            return None

        character.poses[pose_name] = pose_description
        return await self.library.save(character)

    # ============================================================
    # 프롬프트 생성
    # ============================================================

    async def get_scene_prompt(
        self,
        character_ids: List[str],
        scene_description: str,
        expressions: Dict[str, str] = None,
        poses: Dict[str, str] = None,
        outfits: Dict[str, str] = None
    ) -> str:
        """
        장면용 캐릭터 프롬프트 생성

        Args:
            character_ids: 캐릭터 ID 목록
            scene_description: 장면 설명
            expressions: 캐릭터별 표정 {char_id: expression}
            poses: 캐릭터별 포즈 {char_id: pose}
            outfits: 캐릭터별 의상 {char_id: outfit}

        Returns:
            완성된 프롬프트
        """
        expressions = expressions or {}
        poses = poses or {}
        outfits = outfits or {}

        parts = [self.DISNEY_STYLE_PREFIX]

        # 캐릭터들 추가
        char_prompts = []
        for char_id in character_ids:
            char = await self.library.load(char_id)
            if char:
                expr = expressions.get(char_id, "default")
                pose = poses.get(char_id, "standing")
                outfit = outfits.get(char_id, "default")

                char_prompt = char.get_full_prompt(
                    expression=expr,
                    pose=pose,
                    outfit=outfit,
                    include_disney_style=False
                )
                char_prompts.append(char_prompt)

        if char_prompts:
            parts.append(", ".join(char_prompts))

        # 장면 설명 추가
        if scene_description:
            parts.append(scene_description)

        return ", ".join(parts)

    async def get_multi_character_prompt(
        self,
        characters: List[Dict[str, Any]]
    ) -> str:
        """
        여러 캐릭터 프롬프트

        Args:
            characters: [{id, expression, pose, outfit}, ...]

        Returns:
            프롬프트
        """
        char_ids = [c["id"] for c in characters]
        expressions = {c["id"]: c.get("expression", "default") for c in characters}
        poses = {c["id"]: c.get("pose", "standing") for c in characters}
        outfits = {c["id"]: c.get("outfit", "default") for c in characters}

        return await self.get_scene_prompt(
            character_ids=char_ids,
            scene_description="",
            expressions=expressions,
            poses=poses,
            outfits=outfits
        )


# ============================================================
# 편의 함수
# ============================================================

def get_character_generator() -> CharacterGenerator:
    """캐릭터 생성기 싱글톤"""
    return CharacterGenerator()
