from __future__ import annotations

from backend.app.cloud.service.resource.providers.led.ledword.effects._shared.centered_reveal_runtime import build_centered_local_effect_spec

from .profile import build_horizontal_stretch_reveal_profile


HORIZONTAL_STRETCH_REVEAL_SPEC = build_centered_local_effect_spec(
    name="horizontal_stretch_reveal",
    profile_builder=build_horizontal_stretch_reveal_profile,
)

__all__ = [
    "HORIZONTAL_STRETCH_REVEAL_SPEC",
]

