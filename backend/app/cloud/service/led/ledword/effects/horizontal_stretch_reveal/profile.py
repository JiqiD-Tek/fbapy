from __future__ import annotations

from backend.app.cloud.service.led.ledword.effects._shared.centered_reveal_runtime import LocalEffectContext, RevealEffectProfile


def build_horizontal_stretch_reveal_profile(context: LocalEffectContext) -> RevealEffectProfile:
    return RevealEffectProfile(
        mode="stretch",
        display_motion="a center line stretches horizontally and unfolds into the final word",
        reveal_frames=20,
        hold_frames=10,
        fade_frames=8,
        blank_frames=4,
        extra_json={"axis": "horizontal"},
    )


__all__ = ["build_horizontal_stretch_reveal_profile"]

