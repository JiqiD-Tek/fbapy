from __future__ import annotations

from backend.app.cloud.service.resource.providers.led.ledword.effects._shared.centered_reveal_runtime import LocalEffectContext, RevealEffectProfile


def build_raindrop_reveal_profile(context: LocalEffectContext) -> RevealEffectProfile:
    return RevealEffectProfile(
        mode="raindrop",
        display_motion="falling droplets settle into target cells and accumulate the final word from top to bottom",
        reveal_frames=24,
        hold_frames=10,
        fade_frames=8,
        blank_frames=4,
        extra_json={"drop_trail": 3},
    )


__all__ = ["build_raindrop_reveal_profile"]

