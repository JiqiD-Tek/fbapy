from __future__ import annotations

from typing import Dict

from backend.app.cloud.service.resource.providers.led.ledword.font_paths import resolve_font_asset

from .models import FontStylePreset


FONT_STYLE_PRESETS: Dict[str, FontStylePreset] = {
    "misans_heavy": FontStylePreset(
        name="misans_heavy",
        font_path=resolve_font_asset("MiSans-Heavy.ttf"),
        max_preferred_chars=None,
    ),
    "roundpix_pixel": FontStylePreset(
        name="roundpix_pixel",
        font_path=resolve_font_asset("ZLabsRoundPix_16px_M_CN.ttf"),
        max_preferred_chars=None,
    ),
}

__all__ = ["FONT_STYLE_PRESETS"]

