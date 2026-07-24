from __future__ import annotations

from backend.app.cloud.service.resource.providers.led.ledword.effects._shared.centered_reveal_runtime import LocalEffectContext, RevealEffectProfile


def build_inverse_flash_reveal_profile(context: LocalEffectContext) -> RevealEffectProfile:
    return RevealEffectProfile(
        mode="inverse_flash",
        display_motion="the board flashes bright with a dark text cutout, then flips into a normal bright word",
        reveal_frames=14,
        hold_frames=10,
        fade_frames=8,
        blank_frames=4,
        extra_json={"flash_frames": 4},
    )


__all__ = ["build_inverse_flash_reveal_profile"]

