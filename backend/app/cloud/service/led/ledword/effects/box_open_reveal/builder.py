from __future__ import annotations

from backend.app.cloud.service.led.ledword.effects._shared.centered_reveal_runtime import build_centered_local_effect_spec

from .profile import build_box_open_reveal_profile


BOX_OPEN_REVEAL_SPEC = build_centered_local_effect_spec(
    name="box_open_reveal",
    profile_builder=build_box_open_reveal_profile,
)

__all__ = [
    "BOX_OPEN_REVEAL_SPEC",
]

