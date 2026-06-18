from __future__ import annotations

from backend.app.cloud.service.led.ledword.effects._shared.centered_reveal_runtime import LocalEffectContext, RevealEffectProfile


def build_decode_reveal_profile(context: LocalEffectContext) -> RevealEffectProfile:
    return RevealEffectProfile(
        mode="decode",
        display_motion="scrambled offset fragments rapidly decode into the final centered word",
        reveal_frames=18,
        hold_frames=10,
        fade_frames=8,
        blank_frames=4,
        extra_json={"scramble_layers": 3, "jitter": 2},
    )


__all__ = ["build_decode_reveal_profile"]

