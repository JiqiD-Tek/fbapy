from __future__ import annotations

import random
from typing import List, Optional

from backend.app.cloud.service.resource.providers.led.ledword.common import derive_seed, is_latin_character

PIXEL_REVEAL_EFFECT_NAMES = frozenset({"pixel_reveal", "sequential_pixel_reveal"})
FORCED_LEFT_TO_RIGHT_PIXEL_REVEAL_EFFECT_NAMES = frozenset({"sequential_pixel_reveal"})


def resolve_pixel_reveal_order_mode(
    *,
    text: str,
    text_effect_name: str,
    visible_units: List[str],
    seed: Optional[int],
) -> str:
    if text_effect_name in FORCED_LEFT_TO_RIGHT_PIXEL_REVEAL_EFFECT_NAMES:
        return "left_to_right"
    if any(is_latin_character(char) for char in visible_units):
        candidate_modes = ("left_to_right", "center_out", "pseudo_random")
    else:
        candidate_modes = ("center_out", "bottom_to_top", "pseudo_random")
    rng = random.Random(derive_seed(seed, 887) or len(text) * 31 + len(visible_units) * 17)
    return candidate_modes[rng.randrange(len(candidate_modes))]


__all__ = [
    "FORCED_LEFT_TO_RIGHT_PIXEL_REVEAL_EFFECT_NAMES",
    "PIXEL_REVEAL_EFFECT_NAMES",
    "resolve_pixel_reveal_order_mode",
]

