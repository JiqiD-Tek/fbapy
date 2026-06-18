from __future__ import annotations

from typing import Dict, Tuple

from .models import BackgroundStylePreset


BACKGROUND_STYLE_PRESETS: Dict[str, BackgroundStylePreset] = {
    "black": BackgroundStylePreset(name="black"),
    "magenta_pixel": BackgroundStylePreset(name="magenta_pixel"),
    "cyan_arcade": BackgroundStylePreset(name="cyan_arcade"),
    "sunset_orange": BackgroundStylePreset(name="sunset_orange"),
    "emerald_neon": BackgroundStylePreset(name="emerald_neon"),
    "violet_glass": BackgroundStylePreset(name="violet_glass"),
    "lime_matrix": BackgroundStylePreset(name="lime_matrix"),
    "ruby_laser": BackgroundStylePreset(name="ruby_laser"),
    "cobalt_electric": BackgroundStylePreset(name="cobalt_electric"),
    "teal_circuit": BackgroundStylePreset(name="teal_circuit"),
    "amber_gold": BackgroundStylePreset(name="amber_gold"),
    "rose_candy": BackgroundStylePreset(name="rose_candy"),
    "royal_indigo": BackgroundStylePreset(name="royal_indigo"),
    "ice_blue": BackgroundStylePreset(name="ice_blue"),
    "jade_lantern": BackgroundStylePreset(name="jade_lantern"),
    "coral_reef": BackgroundStylePreset(name="coral_reef"),
    "sapphire_violet": BackgroundStylePreset(name="sapphire_violet"),
    "copper_heat": BackgroundStylePreset(name="copper_heat"),
    "mint_aurora": BackgroundStylePreset(name="mint_aurora"),
    "crimson_noir": BackgroundStylePreset(name="crimson_noir"),
    "aqua_lagoon": BackgroundStylePreset(name="aqua_lagoon"),
    "lemon_lime": BackgroundStylePreset(name="lemon_lime"),
    "soft_lavender": BackgroundStylePreset(name="soft_lavender"),
    "tangerine_pink": BackgroundStylePreset(name="tangerine_pink"),
    "deep_sea": BackgroundStylePreset(name="deep_sea"),
    "plasma_blue": BackgroundStylePreset(name="plasma_blue"),
}

BACKGROUND_STYLE_RANDOM_GROUPS: Dict[str, Tuple[str, ...]] = {
    "red": ("ruby_laser", "crimson_noir"),
    "orange": ("sunset_orange", "copper_heat", "tangerine_pink", "coral_reef"),
    "yellow": ("amber_gold", "lemon_lime", "lime_matrix"),
    "green": ("emerald_neon", "jade_lantern", "mint_aurora"),
    "cyan": ("cyan_arcade", "teal_circuit", "aqua_lagoon"),
    "blue": ("deep_sea", "cobalt_electric", "plasma_blue", "ice_blue"),
    "purple": (
        "violet_glass",
        "royal_indigo",
        "magenta_pixel",
        "rose_candy",
        "soft_lavender",
        "sapphire_violet",
    ),
}

BACKGROUND_STYLE_RANDOM_GROUP_WEIGHTS: Tuple[str, ...] = (
    "red",
    "red",
    "red",
    "orange",
    "orange",
    "yellow",
    "yellow",
    "green",
    "green",
    "cyan",
    "cyan",
    "blue",
    "blue",
    "blue",
    "purple",
)

__all__ = [
    "BACKGROUND_STYLE_PRESETS",
    "BACKGROUND_STYLE_RANDOM_GROUPS",
    "BACKGROUND_STYLE_RANDOM_GROUP_WEIGHTS",
]
