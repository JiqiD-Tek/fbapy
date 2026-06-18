from __future__ import annotations

from typing import Dict

from .design_names import DESIGN_TYPE_DEFINITIONS
from .models import TextEffectDesignType


TEXT_EFFECT_DESIGN_TYPES: Dict[str, TextEffectDesignType] = {
    definition.key: TextEffectDesignType(
        name=definition.key,
        display_name=definition.display_name,
        implemented_effect=definition.effect_name,
    )
    for definition in DESIGN_TYPE_DEFINITIONS
}

TEXT_EFFECT_TO_DESIGN_TYPE: Dict[str, str] = {
    definition.effect_name: definition.key
    for definition in DESIGN_TYPE_DEFINITIONS
}

TEXT_EFFECT_DESIGN_ALIASES: Dict[str, str] = {}
for definition in DESIGN_TYPE_DEFINITIONS:
    TEXT_EFFECT_DESIGN_ALIASES[definition.key] = definition.key
    TEXT_EFFECT_DESIGN_ALIASES[definition.display_name] = definition.key
    TEXT_EFFECT_DESIGN_ALIASES[definition.effect_name] = definition.key
    for alias in definition.design_aliases:
        TEXT_EFFECT_DESIGN_ALIASES[alias] = definition.key

__all__ = [
    'TEXT_EFFECT_DESIGN_ALIASES',
    'TEXT_EFFECT_DESIGN_TYPES',
    'TEXT_EFFECT_TO_DESIGN_TYPE',
]
