from __future__ import annotations

from backend.app.cloud.service.led.ledword.effects._shared.centered_reveal_runtime import build_centered_local_effect_spec

from .profile import build_center_burst_reveal_profile


CENTER_BURST_REVEAL_SPEC = build_centered_local_effect_spec(
    name="center_burst_reveal",
    profile_builder=build_center_burst_reveal_profile,
)

__all__ = [
    "CENTER_BURST_REVEAL_SPEC",
]

