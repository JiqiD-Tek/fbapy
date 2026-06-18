from __future__ import annotations

from backend.app.cloud.service.led.ledword.effects._shared.centered_reveal_runtime import build_centered_local_effect_spec

from .profile import build_wave_reveal_profile


WAVE_REVEAL_SPEC = build_centered_local_effect_spec(
    name="wave_reveal",
    profile_builder=build_wave_reveal_profile,
)

__all__ = [
    "WAVE_REVEAL_SPEC",
]

