from __future__ import annotations

import random

from backend.app.cloud.service.resource.providers.led.ledword.common import derive_seed, is_latin_character, visible_chars
from backend.app.cloud.service.resource.providers.led.ledword.effects._shared.centered_reveal_runtime import LocalEffectContext, RevealEffectProfile


def build_outline_scan_reveal_profile(context: LocalEffectContext) -> RevealEffectProfile:
    rng_seed = derive_seed(context.seed, 4201) or (len(context.text) * 97 + len(context.text_effect.name) * 31)
    rng = random.Random(rng_seed)
    visible = visible_chars(context.text)
    has_latin = any(is_latin_character(char) for char in visible)
    direction = "left_to_right" if has_latin else rng.choice(("top_to_bottom", "left_to_right"))
    return RevealEffectProfile(
        mode="outline_scan",
        display_motion="{0} scan traces the outline first and fills the interior second".format(direction),
        reveal_frames=24,
        hold_frames=10,
        fade_frames=8,
        blank_frames=4,
        extra_json={"direction": direction, "outline_window": 0.42},
    )


__all__ = ["build_outline_scan_reveal_profile"]

