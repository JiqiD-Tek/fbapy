from __future__ import annotations

import random
from typing import Optional

from backend.app.cloud.service.resource.providers.led.ledword.common import (
    is_cjk_character,
    is_latin_character,
    recognition_handoff_units,
    visible_chars,
    visible_text_length,
)
from backend.app.cloud.service.resource.providers.led.ledword.style_catalog import (
    BACKGROUND_STYLE_PRESETS,
    BACKGROUND_STYLE_RANDOM_GROUPS,
    BACKGROUND_STYLE_RANDOM_GROUP_WEIGHTS,
    DEFAULT_BACKGROUND_STYLE,
    DEFAULT_FONT_STYLE,
    FONT_STYLE_PRESETS,
    TEXT_EFFECT_DESIGN_ALIASES,
    TEXT_EFFECT_DESIGN_TYPES,
    TEXT_EFFECT_LENGTH_LIMITS,
    TEXT_EFFECT_NAME_ALIASES,
    TEXT_EFFECT_PRESETS,
    TEXT_EFFECT_TO_DESIGN_TYPE,
    BackgroundStylePreset,
    FontStylePreset,
    TextEffectDesignType,
    TextEffectPreset,
)


LATIN_TEXT_EFFECT_LENGTH_OVERRIDES = {
    "pixel_reveal": 24,
    "sequential_pixel_reveal": 24,
    "star_gather_reveal": 24,
    "scanline_reveal": 24,
    "flipboard_reveal": 24,
    "decode_reveal": 24,
    "glitch_hold": 24,
    "center_burst_reveal": 16,
    "outline_scan_reveal": 24,
    "sequential_outline_scan_reveal": 24,
    "stroke_write_reveal": 24,
    "stamp_pop_reveal": 16,
    "raindrop_reveal": 24,
    "wave_reveal": 24,
    "horizontal_stretch_reveal": 24,
    "box_open_reveal": 24,
    "inverse_flash_reveal": 24,
}


def supported_font_styles() -> tuple[str, ...]:
    return tuple(
        sorted(
            name
            for name, preset in FONT_STYLE_PRESETS.items()
            if preset.font_path.exists()
        )
    )


def resolve_background_style(
    style_name: str = DEFAULT_BACKGROUND_STYLE,
    *,
    seed: Optional[int] = None,
) -> BackgroundStylePreset:
    normalized_name = str(style_name or DEFAULT_BACKGROUND_STYLE).strip().lower()
    if normalized_name in {"", "random"}:
        return _resolve_random_background_style(seed=seed)
    if normalized_name in BACKGROUND_STYLE_RANDOM_GROUPS:
        return _resolve_random_background_style(
            seed=seed,
            color_group=normalized_name,
        )
    preset = BACKGROUND_STYLE_PRESETS.get(normalized_name)
    if preset is None:
        raise ValueError(
            "unsupported background style: {0}. supported values: random, color groups ({1}), presets ({2})".format(
                normalized_name,
                ", ".join(sorted(BACKGROUND_STYLE_RANDOM_GROUPS.keys())),
                ", ".join(sorted(BACKGROUND_STYLE_PRESETS.keys())),
            )
        )
    return preset


def _resolve_random_background_style(
    *,
    seed: Optional[int],
    color_group: Optional[str] = None,
) -> BackgroundStylePreset:
    rng = random.Random(seed)
    if color_group is None:
        color_group = rng.choice(BACKGROUND_STYLE_RANDOM_GROUP_WEIGHTS)
    candidate_names = tuple(
        name
        for name in BACKGROUND_STYLE_RANDOM_GROUPS.get(color_group, ())
        if name in BACKGROUND_STYLE_PRESETS
    )
    if not candidate_names:
        raise ValueError("background color group has no registered presets: {0}".format(color_group))
    return BACKGROUND_STYLE_PRESETS[rng.choice(candidate_names)]


def resolve_font_style(
    style_name: str = DEFAULT_FONT_STYLE,
    *,
    text: Optional[str] = None,
    seed: Optional[int] = None,
) -> FontStylePreset:
    normalized_name = str(style_name or DEFAULT_FONT_STYLE).strip().lower()
    visible_length = visible_text_length(text)
    available_names = supported_font_styles()

    if normalized_name in {"", "random"}:
        candidate_names = tuple(
            name
            for name in available_names
            if _supports_text_length(FONT_STYLE_PRESETS[name], visible_length)
        ) or available_names
        if not candidate_names:
            raise FileNotFoundError("no supported font style preset is available on this machine")
        rng = random.Random(seed)
        return FONT_STYLE_PRESETS[rng.choice(candidate_names)]

    preset = FONT_STYLE_PRESETS.get(normalized_name)
    if preset is None or not preset.font_path.exists():
        raise ValueError(
            "unsupported font style: {0}. supported values: random, {1}".format(
                normalized_name,
                ", ".join(available_names),
            )
        )
    return preset


def infer_font_script(text: Optional[str]) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return "cjk"
    has_cjk = any(is_cjk_character(char) for char in normalized)
    if has_cjk:
        has_latin = any(is_latin_character(char) for char in normalized)
        return "mixed" if has_latin else "cjk"
    return "latin"


def resolve_text_effect_name_from_design_type(design_type: str) -> str:
    normalized_design_type = _normalize_text_effect_design_selector(design_type)
    preset = TEXT_EFFECT_DESIGN_TYPES.get(normalized_design_type)
    if preset is None:
        raise ValueError(
            "unsupported text effect design type: {0}. supported values: {1}".format(
                design_type,
                ", ".join(
                    design.display_name
                    for _, design in sorted(TEXT_EFFECT_DESIGN_TYPES.items())
                ),
            )
        )
    return preset.implemented_effect


def resolve_text_effect(
    effect_name: str,
    *,
    text: Optional[str] = None,
    design_type: Optional[str] = None,
) -> TextEffectPreset:
    if design_type:
        effect_name = resolve_text_effect_name_from_design_type(design_type)
    normalized_name = _normalize_text_effect_selector(effect_name)
    measured_length = _text_effect_display_unit_count(normalized_name, text)
    preset = TEXT_EFFECT_PRESETS.get(normalized_name)
    if preset is None:
        raise ValueError(
            "unsupported text effect: {0}. supported values: {1}".format(
                effect_name,
                ", ".join(TEXT_EFFECT_PRESETS.keys()),
            )
        )
    if not supports_text_effect_for_text(preset.name, text):
        limit = text_effect_length_limit_for_text(preset.name, text=text)
        raise ValueError(
            "text effect {0} supports up to {1} display units; current text has {2} display units".format(
                preset.name,
                limit,
                measured_length,
            )
        )
    return preset


def text_effect_design_type_for_effect(effect_name: str) -> Optional[TextEffectDesignType]:
    normalized_name = _normalize_text_effect_selector(effect_name)
    design_name = TEXT_EFFECT_TO_DESIGN_TYPE.get(normalized_name)
    if design_name is None:
        return None
    return TEXT_EFFECT_DESIGN_TYPES.get(design_name)


def text_effect_length_limit_for_text(
    effect_name: str,
    *,
    text: Optional[str] = None,
) -> Optional[int]:
    base_limit = TEXT_EFFECT_LENGTH_LIMITS.get(effect_name)
    if base_limit is None:
        return None
    visible = visible_chars(str(text or ""))
    if not visible:
        return base_limit
    has_cjk = any(is_cjk_character(char) for char in visible)
    has_latin = any(is_latin_character(char) for char in visible)
    if has_latin and not has_cjk:
        return LATIN_TEXT_EFFECT_LENGTH_OVERRIDES.get(effect_name, base_limit)
    return base_limit


def supports_text_effect_for_text(
    effect_name: str,
    text: Optional[str],
) -> bool:
    visible_length = _text_effect_display_unit_count(effect_name, text)
    limit = text_effect_length_limit_for_text(effect_name, text=text)
    if limit is None or visible_length <= 0:
        return True
    return visible_length <= limit


def _supports_text_length(preset: FontStylePreset, visible_length: int) -> bool:
    if preset.max_preferred_chars is None or visible_length <= 0:
        return True
    return visible_length <= preset.max_preferred_chars


def _normalize_text_effect_selector(value: str) -> str:
    normalized = str(value or "").strip().lower()
    return TEXT_EFFECT_NAME_ALIASES.get(normalized, normalized)


def _normalize_text_effect_design_selector(value: str) -> str:
    normalized = str(value or "").strip().lower()
    return TEXT_EFFECT_DESIGN_ALIASES.get(normalized, normalized)


def _text_effect_display_unit_count(
    effect_name: str,
    text: Optional[str],
) -> int:
    if _normalize_text_effect_selector(effect_name) == "recognition_handoff_reveal":
        return len(recognition_handoff_units(text))
    return visible_text_length(text)


__all__ = [
    "BACKGROUND_STYLE_PRESETS",
    "BackgroundStylePreset",
    "DEFAULT_BACKGROUND_STYLE",
    "DEFAULT_FONT_STYLE",
    "FONT_STYLE_PRESETS",
    "FontStylePreset",
    "TEXT_EFFECT_PRESETS",
    "TEXT_EFFECT_DESIGN_TYPES",
    "TextEffectPreset",
    "TextEffectDesignType",
    "infer_font_script",
    "resolve_background_style",
    "resolve_font_style",
    "resolve_text_effect",
    "resolve_text_effect_name_from_design_type",
    "supported_font_styles",
    "supports_text_effect_for_text",
    "text_effect_length_limit_for_text",
    "text_effect_design_type_for_effect",
]

