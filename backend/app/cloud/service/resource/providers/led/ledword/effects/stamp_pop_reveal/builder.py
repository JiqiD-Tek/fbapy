from __future__ import annotations

from backend.app.cloud.service.resource.providers.led.ledword.effects._shared.centered_reveal_runtime import build_centered_local_effect_spec

from .profile import build_stamp_pop_reveal_profile


STAMP_POP_REVEAL_SPEC = build_centered_local_effect_spec(
    name="stamp_pop_reveal",
    profile_builder=build_stamp_pop_reveal_profile,
)

__all__ = [
    "STAMP_POP_REVEAL_SPEC",
]

