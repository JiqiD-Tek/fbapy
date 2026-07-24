from __future__ import annotations

from backend.app.cloud.service.resource.providers.led.ledword.effects._shared.centered_reveal_runtime import LocalEffectContext, RevealEffectProfile


def build_box_open_reveal_profile(context: LocalEffectContext) -> RevealEffectProfile:
    return RevealEffectProfile(
        mode="box_open",
        display_motion="a small center box opens outward and reveals the word inside it",
        reveal_frames=20,
        hold_frames=10,
        fade_frames=8,
        blank_frames=4,
        extra_json={"box_margin": 1},
    )


__all__ = ["build_box_open_reveal_profile"]

