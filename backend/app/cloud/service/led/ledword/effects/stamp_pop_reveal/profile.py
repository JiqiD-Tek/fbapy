from __future__ import annotations

from backend.app.cloud.service.led.ledword.effects._shared.centered_reveal_runtime import LocalEffectContext, RevealEffectProfile


def build_stamp_pop_reveal_profile(context: LocalEffectContext) -> RevealEffectProfile:
    return RevealEffectProfile(
        mode="stamp_pop",
        display_motion="oversized bright stamp hits the center and settles quickly into the final word",
        reveal_frames=12,
        hold_frames=12,
        fade_frames=8,
        blank_frames=4,
        extra_json={"overshoot": 1.8},
    )


__all__ = ["build_stamp_pop_reveal_profile"]

