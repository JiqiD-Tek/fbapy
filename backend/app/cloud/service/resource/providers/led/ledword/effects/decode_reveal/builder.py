from __future__ import annotations

from backend.app.cloud.service.resource.providers.led.ledword.effects._shared.centered_reveal_runtime import build_centered_local_effect_spec

from .profile import build_decode_reveal_profile


DECODE_REVEAL_SPEC = build_centered_local_effect_spec(
    name="decode_reveal",
    profile_builder=build_decode_reveal_profile,
)

__all__ = [
    "DECODE_REVEAL_SPEC",
]

