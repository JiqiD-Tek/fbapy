from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from backend.app.cloud.service.led.ledword.common import derive_seed, is_latin_character, mix_rgb
from backend.app.cloud.service.led.ledword.styles import BackgroundStylePreset, TextEffectPreset

from ..common import extract_visible_units, resolve_local_four_way_palette

SCANLINE_REVEAL_EFFECT_NAMES = frozenset({"scanline_reveal"})


def resolve_scanline_reveal_profile(
    *,
    text: str,
    text_effect: TextEffectPreset,
    seed: Optional[int],
) -> Dict[str, Any]:
    visible_units = extract_visible_units(text)
    if any(is_latin_character(char) for char in visible_units):
        direction_options = ("left_to_right", "right_to_left", "top_to_bottom")
    else:
        direction_options = ("top_to_bottom", "bottom_to_top", "left_to_right")
    profile = {
        "variant_label": "base",
        "reveal_frames": 28,
        "hold_frames": 10,
        "fade_frames": 8,
        "blank_frames": 4,
        "core_width": 0.80,
        "trail_width": 2.30,
        "panel_scan_strength": 0.22,
        "trail_strength": 0.12,
        "text_scan_boost": 0.96,
    }
    rng_seed = derive_seed(seed, 1499) or (len(text) * 61 + len(text_effect.name) * 29)
    rng = random.Random(rng_seed)
    profile["direction"] = direction_options[rng.randrange(len(direction_options))]
    return profile


def resolve_local_scanline_palette(
    *,
    background_style: BackgroundStylePreset,
    text_effect: TextEffectPreset,
) -> Dict[str, List[int]]:
    base_palette = resolve_local_four_way_palette(background_style)
    palette = {name: list(color) for name, color in base_palette.items()}
    palette["scan_head"] = mix_rgb(base_palette["halo"], [255, 255, 245], 0.42)
    palette["scan_trail"] = mix_rgb(base_palette["accent"], base_palette["halo"], 0.56)
    return palette


__all__ = [
    "SCANLINE_REVEAL_EFFECT_NAMES",
    "resolve_local_scanline_palette",
    "resolve_scanline_reveal_profile",
]

