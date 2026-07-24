from __future__ import annotations

from backend.app.cloud.service.resource.providers.led.ledword.effects._shared.centered_reveal_runtime import build_centered_local_effect_spec

from .profile import build_inverse_flash_reveal_profile


INVERSE_FLASH_REVEAL_SPEC = build_centered_local_effect_spec(
    name="inverse_flash_reveal",
    profile_builder=build_inverse_flash_reveal_profile,
)

__all__ = [
    "INVERSE_FLASH_REVEAL_SPEC",
]

