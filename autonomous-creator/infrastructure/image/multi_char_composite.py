# -*- coding: utf-8 -*-
"""
MultiCharCompositeGenerator - 다중 인물 이미지 생성기 (방법 2: 개별 생성 + 합성)

SDXL은 cross-attention 한계로 2인 이상 씬에서 인물 appearance 토큰이 뒤섞이는 문제가 있습니다.
이 모듈은 각 캐릭터를 개별적으로 생성한 뒤 합성하는 방식으로 문제를 해결합니다.

동작 순서:
1. 배경 이미지 생성 (캐릭터 없는 장면 설정)
2. 각 캐릭터를 개별적으로 생성 (단순 배경 위에)
3. 캐릭터 마스크 추출 (배경 제거)
4. 배경 위에 캐릭터 합성

RTX 3060 6GB VRAM 환경에서 CPU offload 기반으로 동작합니다.
"""
import logging
import time
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageFilter

from core.domain.entities.preset import StylePreset
from infrastructure.image.sdxl_generator import (
    NEGATIVE_PROMPT_BG,
    NEGATIVE_PROMPT_TEXT,
    SDXLGenerator,
)
from infrastructure.story.story_spec import CharacterSpec, SceneSpec

logger = logging.getLogger(__name__)

# 캐릭터 개별 생성 시 사용할 배경 관련 positive/negative 토큰
CHAR_PLAIN_BG_POSITIVE = (
    "plain background, simple background, solid color background, white background"
)
CHAR_DETAILED_BG_NEGATIVE = (
    "detailed background, scenery, landscape, outdoor, indoor, "
    "environment, room, nature, city, street, sky, ground, floor"
)

# 트리거 워드 (기존 시스템과 동일)
TRIGGER_WORDS = "MG_ip, pixar"

# 공통 스타일 토큰
STYLE_TOKENS = "3d animation, disney pixar style, high quality"


class MultiCharCompositeGenerator:
    """
    다중 인물 이미지 생성기 - 방법 2: 개별 생성 + 합성

    기존 SDXLGenerator 인스턴스를 재사용하여:
    1. 배경 이미지 생성 (캐릭터 없는 장면)
    2. 각 캐릭터를 개별적으로 생성 (단순 배경)
    3. 캐릭터 마스크 추출 (배경 제거)
    4. 배경 위에 캐릭터 합성
    """

    def __init__(
        self,
        generator: SDXLGenerator,
        debug_dir: Optional[str] = None,
    ):
        """
        Args:
            generator: 이미 초기화된 SDXLGenerator 인스턴스
                       (pipeline이 로드되어 있어야 함)
            debug_dir: 중간 결과물 저장 디렉토리 (None이면 저장하지 않음)
        """
        self.generator = generator
        self.debug_dir = debug_dir

        # rembg 사용 가능 여부 확인
        self._rembg_available = self._check_rembg()

        if self._rembg_available:
            logger.info("[MultiCharComposite] rembg 사용 가능 (고품질 배경 제거)")
        else:
            logger.info(
                "[MultiCharComposite] rembg 미설치, PIL 기반 배경 제거 사용"
            )

    def _check_rembg(self) -> bool:
        """rembg 패키지 사용 가능 여부 확인"""
        try:
            import rembg  # noqa: F401
            return True
        except ImportError:
            return False

    # ------------------------------------------------------------------ #
    #  메인 인터페이스
    # ------------------------------------------------------------------ #

    async def generate_multi_char(
        self,
        scene: SceneSpec,
        characters: List[CharacterSpec],
        output_path: str,
        width: int = 576,
        height: int = 1024,
        seed: int = 12345,
        steps: int = 20,
        cfg_scale: float = 7.5,
    ) -> str:
        """
        다중 인물 씬 이미지 생성 (개별 생성 + 합성)

        Args:
            scene: 장면 명세 (location, mood, action 포함)
            characters: 장면에 등장하는 캐릭터 목록 (appearance 포함)
            output_path: 최종 출력 이미지 경로
            width: 이미지 너비
            height: 이미지 높이
            seed: 재현성을 위한 시드값
            steps: SDXL inference steps
            cfg_scale: CFG guidance scale

        Returns:
            생성된 최종 합성 이미지 경로
        """
        start_time = time.time()
        scene_label = f"scene={scene.id}"

        # 장면에 등장하는 캐릭터 필터링 (CharacterSpec으로 변환)
        char_map = {c.id: c for c in characters}
        scene_chars = []
        for char_id in scene.characters:
            if char_id in char_map:
                scene_chars.append(char_map[char_id])
            else:
                logger.warning(
                    f"[MultiCharComposite] {scene_label}: "
                    f"캐릭터 '{char_id}'를 찾을 수 없음, 스킵"
                )

        num_chars = len(scene_chars)
        if num_chars == 0:
            logger.warning(
                f"[MultiCharComposite] {scene_label}: "
                "등장 캐릭터 없음, 배경만 생성"
            )
            return await self._generate_background_only(
                scene, output_path, width, height, seed, steps, cfg_scale
            )

        logger.info(
            f"[MultiCharComposite] {scene_label}: "
            f"다중 인물 합성 시작 ({num_chars}명)"
        )

        # 디버그 디렉토리 준비
        debug_subdir = None
        if self.debug_dir:
            debug_subdir = Path(self.debug_dir) / scene.id
            debug_subdir.mkdir(parents=True, exist_ok=True)

        # 1. 배경 이미지 생성
        logger.info(f"[MultiCharComposite] {scene_label}: 배경 이미지 생성 중...")
        bg_path = str(debug_subdir / "background.png") if debug_subdir else None
        background = await self._generate_background(
            scene=scene,
            width=width,
            height=height,
            seed=seed,
            steps=steps,
            cfg_scale=cfg_scale,
            save_path=bg_path,
        )

        # 2. 각 캐릭터 개별 생성
        char_images: List[Tuple[Image.Image, str]] = []
        for i, char_spec in enumerate(scene_chars):
            logger.info(
                f"[MultiCharComposite] {scene_label}: "
                f"캐릭터 '{char_spec.name}' ({char_spec.id}) 생성 중... "
                f"[{i+1}/{num_chars}]"
            )
            char_save_path = (
                str(debug_subdir / f"char_{i:02d}_{char_spec.id}.png")
                if debug_subdir
                else None
            )
            char_image = await self._generate_character(
                character=char_spec,
                scene=scene,
                char_index=i,
                total_chars=num_chars,
                width=width,
                height=height,
                seed=seed + i + 1,  # 각 캐릭터마다 다른 시드
                steps=steps,
                cfg_scale=cfg_scale,
                save_path=char_save_path,
            )
            char_images.append((char_image, char_spec.id))

        # 3. 캐릭터 배경 제거 (마스크 추출)
        masked_chars: List[Tuple[Image.Image, Image.Image]] = []  # (char_rgba, mask)
        for i, (char_img, char_id) in enumerate(char_images):
            logger.info(
                f"[MultiCharComposite] {scene_label}: "
                f"캐릭터 '{char_id}' 배경 제거 중..."
            )
            char_rgba, mask = self._remove_background(
                char_img,
                save_path=(
                    str(debug_subdir / f"char_{i:02d}_{char_id}_rgba.png")
                    if debug_subdir
                    else None
                ),
                mask_save_path=(
                    str(debug_subdir / f"char_{i:02d}_{char_id}_mask.png")
                    if debug_subdir
                    else None
                ),
            )
            masked_chars.append((char_rgba, mask))

        # 4. 캐릭터 위치 계산
        positions = self._calculate_positions(num_chars, width, height)
        logger.info(
            f"[MultiCharComposite] {scene_label}: "
            f"캐릭터 위치 = {positions}"
        )

        # 5. 합성
        logger.info(f"[MultiCharComposite] {scene_label}: 합성 중...")
        composite = self._composite_characters(
            background=background,
            characters=masked_chars,
            positions=positions,
            width=width,
            height=height,
        )

        # 6. 최종 저장
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        composite.save(output_path, quality=95)

        # 디버그: 합성 결과도 저장
        if debug_subdir:
            composite.save(str(debug_subdir / "final_composite.png"), quality=95)

        elapsed = time.time() - start_time
        logger.info(
            f"[MultiCharComposite] {scene_label}: "
            f"완료 ({elapsed:.1f}초) -> {output_path}"
        )

        return output_path

    # ------------------------------------------------------------------ #
    #  배경 이미지 생성
    # ------------------------------------------------------------------ #

    async def _generate_background(
        self,
        scene: SceneSpec,
        width: int,
        height: int,
        seed: int,
        steps: int,
        cfg_scale: float,
        save_path: Optional[str] = None,
    ) -> Image.Image:
        """
        배경 이미지 생성 (캐릭터 없는 장면)

        scene.location + scene.mood를 사용하여 캐릭터가 없는 배경을 생성합니다.
        """
        # 배경 프롬프트: 장소 + 무드 + 스타일 (캐릭터 언급 없음)
        bg_parts = [TRIGGER_WORDS, STYLE_TOKENS]

        if scene.location:
            bg_parts.append(scene.location)

        # 무드 매핑
        mood_map = {
            "tense": "tense atmosphere, dramatic shadows",
            "dark": "dark moody lighting, noir atmosphere",
            "bright": "bright cheerful lighting, sunny",
            "mysterious": "mysterious foggy atmosphere, mist",
            "peaceful": "peaceful serene ambiance, soft light",
            "epic": "epic grand scale, dramatic lighting",
            "romantic": "warm romantic glow, golden light",
            "horror": "creepy unsettling atmosphere, dark shadows",
            "joyful": "vibrant joyful energy, bright colors",
            "sad": "melancholic muted tones, overcast",
            "neutral": "balanced natural lighting",
            "dramatic": "dramatic high contrast lighting",
            "suspenseful": "suspenseful shadowy lighting",
            "cheerful": "bright warm cheerful tone",
            "gloomy": "gloomy desaturated atmosphere",
        }
        mood_prompt = mood_map.get(scene.mood, f"{scene.mood} atmosphere")
        bg_parts.append(mood_prompt)

        bg_parts.append("empty scene, no people, no characters")
        bg_parts.append("no text, no letters, no watermark")

        bg_prompt = ", ".join(bg_parts)

        # 배경 negative prompt
        bg_negative_parts = [
            "people, person, character, human, figure, man, woman, child",
            "blurry, deformed, low quality, distorted, watermark",
        ]
        bg_negative_parts.append(NEGATIVE_PROMPT_BG)
        bg_negative_parts.append(NEGATIVE_PROMPT_TEXT)
        bg_negative = ", ".join(bg_negative_parts)

        # StylePreset 생성 (배경 전용)
        preset = StylePreset(
            name="multi_char_background",
            base_prompt="",
            negative_prompt=bg_negative,
            seed=seed,
            cfg_scale=cfg_scale,
            steps=steps,
        )

        # 배경 생성 (IP-Adapter 미사용, 캐릭터 참조 없이)
        image = await self.generator.generate(
            prompt=bg_prompt,
            preset=preset,
            output_path=save_path or self._temp_path(),
            width=width,
            height=height,
            use_ip_adapter=False,
        )

        bg_image = Image.open(image).convert("RGB")
        return bg_image

    # ------------------------------------------------------------------ #
    #  캐릭터 개별 생성
    # ------------------------------------------------------------------ #

    async def _generate_character(
        self,
        character: CharacterSpec,
        scene: SceneSpec,
        char_index: int,
        total_chars: int,
        width: int,
        height: int,
        seed: int,
        steps: int,
        cfg_scale: float,
        save_path: Optional[str] = None,
    ) -> Image.Image:
        """
        단일 캐릭터 이미지 생성 (단순 배경 위에)

        character.appearance + action 관련 토큰을 사용하되,
        배경은 단순하게 유지하여 마스크 추출이 용이하도록 합니다.
        """
        # 캐릭터 프롬프트: appearance + style + 단순 배경 지시
        char_parts = [TRIGGER_WORDS, STYLE_TOKENS]

        # 캐릭터 appearance (옷, 머리 등 시각적 특징)
        if character.appearance:
            char_parts.append(character.appearance)

        # 캐릭터 이름/역할 표시
        char_parts.append(f"1person, solo, single character")

        # 단순 배경 강조
        char_parts.append(CHAR_PLAIN_BG_POSITIVE)

        char_parts.append("no text, no letters, no watermark")

        char_prompt = ", ".join(char_parts)

        # 캐릭터 negative prompt (배경 상세 금지)
        char_negative_parts = [
            "blurry, deformed, bad anatomy, low quality, distorted",
            "multiple characters, crowd, extra person, second person",
        ]
        char_negative_parts.append(CHAR_DETAILED_BG_NEGATIVE)
        char_negative_parts.append(NEGATIVE_PROMPT_TEXT)
        char_negative = ", ".join(char_negative_parts)

        # StylePreset (캐릭터 전용)
        preset = StylePreset(
            name="multi_char_character",
            base_prompt="",
            negative_prompt=char_negative,
            seed=seed,
            cfg_scale=cfg_scale,
            steps=steps,
        )

        # 캐릭터 생성
        temp_path = save_path or self._temp_path()
        output = await self.generator.generate(
            prompt=char_prompt,
            preset=preset,
            output_path=temp_path,
            width=width,
            height=height,
            use_ip_adapter=True,
        )

        char_image = Image.open(output).convert("RGB")
        return char_image

    # ------------------------------------------------------------------ #
    #  배경 제거 (마스크 추출)
    # ------------------------------------------------------------------ #

    def _remove_background(
        self,
        image: Image.Image,
        save_path: Optional[str] = None,
        mask_save_path: Optional[str] = None,
    ) -> Tuple[Image.Image, Image.Image]:
        """
        캐릭터 이미지에서 배경 제거

        rembg가 설치되어 있으면 사용 (고품질),
        없으면 PIL 기반 채도/밝기 임계값 방식 사용.

        Args:
            image: 원본 캐릭터 이미지 (RGB)
            save_path: RGBA 결과 저장 경로 (선택)
            mask_save_path: 마스크 저장 경로 (선택)

        Returns:
            (char_rgba, mask) 튜플
            - char_rgba: RGBA 이미지 (배경이 투명한 캐릭터)
            - mask: L 모드 마스크 (255=캐릭터, 0=배경)
        """
        if self._rembg_available:
            char_rgba, mask = self._remove_bg_rembg(image)
        else:
            char_rgba, mask = self._remove_bg_pil(image)

        # 디버그 저장
        if save_path:
            char_rgba.save(save_path)
        if mask_save_path:
            mask.save(mask_save_path)

        return char_rgba, mask

    def _remove_bg_rembg(
        self, image: Image.Image
    ) -> Tuple[Image.Image, Image.Image]:
        """rembg를 사용한 배경 제거 (고품질)"""
        try:
            from rembg import remove

            rgba = remove(image)
            # 마스크 추출
            mask = rgba.split()[3]  # alpha 채널
            # 마스크 엣지 부드럽게
            mask = mask.filter(ImageFilter.GaussianBlur(radius=2))

            return rgba, mask

        except Exception as e:
            logger.warning(
                f"[MultiCharComposite] rembg 실패, PIL 폴백: {e}"
            )
            return self._remove_bg_pil(image)

    def _remove_bg_pil(
        self, image: Image.Image
    ) -> Tuple[Image.Image, Image.Image]:
        """
        PIL 기반 배경 제거 (채도/밝기 임계값)

        단순/흰색 배경 위의 캐릭터를 분리합니다.
        원리:
        1. HSV 변환 후 채도(S)와 명도(V) 분석
        2. 채도가 낮고 명도가 높은 영역 = 배경 (흰색/밝은 단색)
        3. 채도가 높거나 명도가 낮은 영역 = 캐릭터
        """
        # HSV 변환
        hsv_array = np.array(image.convert("HSV"))

        # H: 0-179, S: 0-255, V: 0-255 (PIL HSV 범위)
        hue = hsv_array[:, :, 0].astype(np.float32)
        saturation = hsv_array[:, :, 1].astype(np.float32)
        value = hsv_array[:, :, 2].astype(np.float32)

        # 캐릭터 마스크 조건:
        # 1. 채도가 충분히 높음 (컬러가 있는 영역 = 캐릭터)
        # 2. 명도가 낮음 (어두운 영역 = 캐릭터의 어두운 부분)
        # 3. 색상이 피부톤 범위 (살색 = 캐릭터)
        high_saturation = saturation > 30  # 채도가 있는 영역
        dark_region = value < 180  # 어두운 영역
        skin_region = (
            (hue > 5) & (hue < 25) & (saturation > 40) & (value > 100)
        )  # 피부톤

        # 마스크: 캐릭터로 판단되는 영역
        mask_array = (
            (high_saturation | dark_region | skin_region)
        ).astype(np.uint8) * 255

        # 너무 작은 노이즈 제거 (모폴로지 연산)
        mask = Image.fromarray(mask_array, mode="L")

        # 열기 연산 (침식 + 팽창)으로 작은 노이즈 제거
        mask = mask.filter(ImageFilter.MinFilter(size=3))
        mask = mask.filter(ImageFilter.MaxFilter(size=3))

        # 엣지 부드럽게 (Gaussian blur)
        mask = mask.filter(ImageFilter.GaussianBlur(radius=3))

        # RGBA 이미지 생성
        img_rgba = image.convert("RGBA")
        img_rgba.putalpha(mask)

        return img_rgba, mask

    # ------------------------------------------------------------------ #
    #  캐릭터 위치 계산
    # ------------------------------------------------------------------ #

    def _calculate_positions(
        self,
        num_chars: int,
        canvas_width: int,
        canvas_height: int,
    ) -> List[Tuple[int, int]]:
        """
        캐릭터 배치 위치 계산

        캐릭터 수에 따라 균등 분배:
        - 2명: 왼쪽(30%), 오른쪽(70%)
        - 3명: 왼쪽(20%), 중앙(50%), 오른쪽(80%)
        - 4명+: 균등 분배

        Returns:
            (x, y) 위치 리스트 (캐릭터 중앙 기준)
        """
        if num_chars == 2:
            x_positions = [0.30, 0.70]
        elif num_chars == 3:
            x_positions = [0.20, 0.50, 0.80]
        elif num_chars == 4:
            x_positions = [0.15, 0.38, 0.62, 0.85]
        else:
            # 5명 이상: 균등 분배
            x_positions = [
                (i + 1) / (num_chars + 1) for i in range(num_chars)
            ]

        # y 위치: 세로 중앙 (캐릭터가 이미지 높이의 70% 차지)
        y_center = int(canvas_height * 0.55)  # 약간 아래로 (하단 여백)

        positions = []
        for x_ratio in x_positions:
            x = int(canvas_width * x_ratio)
            positions.append((x, y_center))

        return positions

    # ------------------------------------------------------------------ #
    #  합성
    # ------------------------------------------------------------------ #

    def _composite_characters(
        self,
        background: Image.Image,
        characters: List[Tuple[Image.Image, Image.Image]],
        positions: List[Tuple[int, int]],
        width: int,
        height: int,
    ) -> Image.Image:
        """
        배경 위에 캐릭터 합성

        Args:
            background: 배경 이미지 (RGB)
            characters: (char_rgba, mask) 리스트
            positions: (x, y) 중앙 위치 리스트
            width: 캔버스 너비
            height: 캔버스 높이

        Returns:
            합성된 RGB 이미지
        """
        canvas = background.copy().convert("RGBA")

        for (char_rgba, mask), (cx, cy) in zip(characters, positions):
            # 캐릭터 크기 조정: 이미지 높이의 ~70%
            char_h = int(height * 0.70)
            char_w = int(char_rgba.width * (char_h / char_rgba.height))
            char_resized = char_rgba.resize(
                (char_w, char_h), Image.LANCZOS
            )
            mask_resized = mask.resize(
                (char_w, char_h), Image.LANCZOS
            )

            # 마스크 엣지 블러 (부드러운 합성)
            mask_resized = mask_resized.filter(
                ImageFilter.GaussianBlur(radius=2)
            )

            # 배치 위치: (cx, cy)가 캐릭터 중앙이 되도록 offset 계산
            paste_x = cx - char_w // 2
            paste_y = cy - char_h // 2

            # 캐릭터를 캔버스에 합성 (alpha composite)
            # 임시 이미지에 캐릭터를 올바른 위치에 배치
            temp = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            temp.paste(char_resized, (paste_x, paste_y), mask_resized)
            canvas = Image.alpha_composite(canvas, temp)

        return canvas.convert("RGB")

    # ------------------------------------------------------------------ #
    #  유틸리티
    # ------------------------------------------------------------------ #

    def _temp_path(self) -> str:
        """임시 파일 경로 생성"""
        import tempfile
        import os

        tmpdir = tempfile.gettempdir()
        return os.path.join(tmpdir, f"multi_char_{int(time.time()*1000)}.png")

    async def _generate_background_only(
        self,
        scene: SceneSpec,
        output_path: str,
        width: int,
        height: int,
        seed: int,
        steps: int,
        cfg_scale: float,
    ) -> str:
        """캐릭터가 없는 씬의 경우 배경만 생성"""
        background = await self._generate_background(
            scene, width, height, seed, steps, cfg_scale,
            save_path=output_path,
        )

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        background.save(output_path, quality=95)

        return output_path
