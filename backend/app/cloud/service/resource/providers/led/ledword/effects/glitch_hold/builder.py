from __future__ import annotations

from backend.app.cloud.service.resource.providers.led.ledword.effects._shared.centered_reveal_runtime import build_centered_local_effect_spec

from .profile import build_glitch_hold_profile


GLITCH_HOLD_SPEC = build_centered_local_effect_spec(
    name="glitch_hold",
    profile_builder=build_glitch_hold_profile,
)

__all__ = [
    "GLITCH_HOLD_SPEC",
]

