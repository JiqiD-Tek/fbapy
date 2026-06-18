from __future__ import annotations

import random

from backend.app.cloud.service.led.ledword.common import derive_seed
from backend.app.cloud.service.led.ledword.effects._shared.centered_reveal_runtime import LocalEffectContext, RevealEffectProfile


def build_wave_reveal_profile(context: LocalEffectContext) -> RevealEffectProfile:
    rng_seed = derive_seed(context.seed, 4201) or (len(context.text) * 97 + len(context.text_effect.name) * 31)
    rng = random.Random(rng_seed)
    direction = rng.choice(("bottom_to_top", "left_to_right"))
    return RevealEffectProfile(
        mode="wave",
        display_motion="{0} wave front lifts the text from dim to clear".format(direction),
        reveal_frames=22,
        hold_frames=10,
        fade_frames=8,
        blank_frames=4,
        extra_json={"direction": direction, "wave_width": 3.2},
    )


__all__ = ["build_wave_reveal_profile"]

