from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from backend.app.cloud.service.resource.providers.led.ledword.common import is_cjk_character, is_latin_character, mix_rgb
from backend.app.cloud.service.resource.providers.led.ledword.core import BOARD_WIDTH
from backend.app.cloud.service.resource.providers.led.ledword.styles import BackgroundStylePreset

from ..common import extract_visible_units, resolve_local_four_way_palette

FLIPBOARD_REVEAL_EFFECT_NAMES = frozenset({"flipboard_reveal"})


def extract_flipboard_pages(text: str) -> List[str]:
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []

    explicit_pages = [
        unit.strip()
        for unit in re.split(
            r"(?:\n+|[|/]+|->|=>|\u2192|[\uFF0C,\u3001;\uFF1B]+)",
            normalized,
        )
        if str(unit or "").strip()
    ]
    if len(explicit_pages) >= 2:
        return explicit_pages[:8]

    whitespace_pages = [
        unit.strip()
        for unit in re.split(r"\s+", normalized)
        if str(unit or "").strip()
    ]
    if len(whitespace_pages) >= 2:
        return whitespace_pages[:8]

    visible_chars = extract_visible_units(normalized)
    if len(visible_chars) >= 2 and all(is_cjk_character(char) for char in visible_chars):
        return visible_chars[:8]
    if len(visible_chars) >= 2 and all(
        is_latin_character(char) or char.isdigit() for char in visible_chars
    ):
        return visible_chars[:8]

    return [normalized]


def resolve_flipboard_reveal_profile(
    *,
    text: str,
    page_units: List[str],
    seed: Optional[int],
) -> Dict[str, Any]:
    return {
        "orientation": "columns",
        "order": "forward",
        "segment_count": BOARD_WIDTH,
        "collapse_frames": 1,
        "expand_frames": 1,
        "hold_frames": 12,
        "idle_frames": 4,
    }


def resolve_local_flipboard_palette(
    background_style: BackgroundStylePreset,
) -> Dict[str, List[int]]:
    base_palette = resolve_local_four_way_palette(background_style)
    palette = {name: list(color) for name, color in base_palette.items()}
    palette["flip_highlight"] = mix_rgb(base_palette["halo"], [255, 250, 214], 0.46)
    palette["flip_shadow"] = mix_rgb(base_palette["text_edge"], base_palette["bg_dark"], 0.42)
    palette["text_main"] = mix_rgb(base_palette["text_main"], [255, 236, 184], 0.24)
    palette["text_alt"] = mix_rgb(base_palette["text_alt"], base_palette["accent"], 0.18)
    return palette


__all__ = [
    "FLIPBOARD_REVEAL_EFFECT_NAMES",
    "extract_flipboard_pages",
    "resolve_flipboard_reveal_profile",
    "resolve_local_flipboard_palette",
]

