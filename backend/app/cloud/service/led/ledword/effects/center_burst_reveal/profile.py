from __future__ import annotations

from backend.app.cloud.service.led.ledword.effects._shared.centered_reveal_runtime import LocalEffectContext, RevealEffectProfile


def build_center_burst_reveal_profile(context: LocalEffectContext) -> RevealEffectProfile:
    return RevealEffectProfile(
        mode="center_burst",
        display_motion="text energy expands outward from the center until the full word stabilizes",
        reveal_frames=20,
        hold_frames=10,
        fade_frames=8,
        blank_frames=4,
        extra_json={"center_bias": 1.0},
    )


__all__ = ["build_center_burst_reveal_profile"]

