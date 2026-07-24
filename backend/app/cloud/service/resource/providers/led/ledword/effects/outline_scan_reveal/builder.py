from __future__ import annotations

from backend.app.cloud.service.resource.providers.led.ledword.effects._shared.centered_reveal_runtime import build_centered_local_effect_spec

from .profile import build_outline_scan_reveal_profile


OUTLINE_SCAN_REVEAL_SPEC = build_centered_local_effect_spec(
    name="outline_scan_reveal",
    profile_builder=build_outline_scan_reveal_profile,
)

__all__ = [
    "OUTLINE_SCAN_REVEAL_SPEC",
]

