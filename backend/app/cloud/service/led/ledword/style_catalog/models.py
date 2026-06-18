from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


DEFAULT_BACKGROUND_STYLE = "black"
DEFAULT_FONT_STYLE = "misans_heavy"


@dataclass(frozen=True)
class BackgroundStylePreset:
    name: str


@dataclass(frozen=True)
class FontStylePreset:
    name: str
    font_path: Path
    max_preferred_chars: Optional[int]


@dataclass(frozen=True)
class TextEffectPreset:
    name: str


@dataclass(frozen=True)
class TextEffectDesignType:
    name: str
    display_name: str
    implemented_effect: str


__all__ = [
    "BackgroundStylePreset",
    "DEFAULT_BACKGROUND_STYLE",
    "DEFAULT_FONT_STYLE",
    "FontStylePreset",
    "TextEffectDesignType",
    "TextEffectPreset",
]
