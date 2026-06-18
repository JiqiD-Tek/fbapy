from __future__ import annotations

import random

from backend.app.cloud.service.led.ledword.common import derive_seed
from backend.app.cloud.service.led.ledword.effects._shared.centered_reveal_runtime import LocalEffectContext, RevealEffectProfile


def build_glitch_hold_profile(context: LocalEffectContext) -> RevealEffectProfile:
    rng_seed = derive_seed(context.seed, 4201) or (len(context.text) * 97 + len(context.text_effect.name) * 31)
    rng = random.Random(rng_seed)
    return RevealEffectProfile(
        mode="glitch",
        display_motion="steady readable text with short random glitch pulses and tiny dropouts",
        reveal_frames=1,
        hold_frames=52,
        fade_frames=7,
        blank_frames=4,
        extra_json={"pulse_stride": 11 + rng.randrange(5), "jitter": 2},
    )


__all__ = ["build_glitch_hold_profile"]

