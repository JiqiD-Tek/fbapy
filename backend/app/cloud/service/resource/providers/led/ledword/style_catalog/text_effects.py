from __future__ import annotations

from typing import Dict, Optional

from .design_names import DESIGN_TYPE_DEFINITIONS
from .models import TextEffectPreset


TEXT_EFFECT_PRESETS: Dict[str, TextEffectPreset] = {
    definition.effect_name: TextEffectPreset(name=definition.effect_name)
    for definition in DESIGN_TYPE_DEFINITIONS
}

TEXT_EFFECT_LENGTH_LIMITS: Dict[str, Optional[int]] = {
    'pixel_reveal': 24,
    'sequential_pixel_reveal': 24,
    'star_gather_reveal': 8,
    'scanline_reveal': 12,
    'flipboard_reveal': 16,
    'decode_reveal': 12,
    'glitch_hold': 12,
    'center_burst_reveal': 8,
    'outline_scan_reveal': 12,
    'sequential_outline_scan_reveal': 12,
    'stroke_write_reveal': 12,
    'stamp_pop_reveal': 8,
    'raindrop_reveal': 12,
    'wave_reveal': 12,
    'horizontal_stretch_reveal': 12,
    'box_open_reveal': 12,
    'inverse_flash_reveal': 12,
    'recognition_handoff_reveal': None,
}

TEXT_EFFECT_NAME_ALIASES: Dict[str, str] = {}
for definition in DESIGN_TYPE_DEFINITIONS:
    TEXT_EFFECT_NAME_ALIASES[definition.effect_name] = definition.effect_name
    TEXT_EFFECT_NAME_ALIASES[definition.key] = definition.effect_name
    TEXT_EFFECT_NAME_ALIASES[definition.display_name] = definition.effect_name
    for alias in definition.design_aliases:
        TEXT_EFFECT_NAME_ALIASES[alias] = definition.effect_name
    for alias in definition.effect_aliases:
        TEXT_EFFECT_NAME_ALIASES[alias] = definition.effect_name

__all__ = ['TEXT_EFFECT_LENGTH_LIMITS', 'TEXT_EFFECT_NAME_ALIASES', 'TEXT_EFFECT_PRESETS']
