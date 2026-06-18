from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LedTextProfile:
    text: str
    visible_length: int
    font_script: str
    latin_word_count: int
    has_cjk: bool
    has_latin: bool

    @property
    def is_multi_word_latin(self) -> bool:
        return self.has_latin and not self.has_cjk and self.latin_word_count >= 2

    def to_dict(self) -> dict[str, Any]:
        return {
            'visible_length': self.visible_length,
            'font_script': self.font_script,
            'latin_word_count': self.latin_word_count,
            'has_cjk': self.has_cjk,
            'has_latin': self.has_latin,
            'is_multi_word_latin': self.is_multi_word_latin,
        }


@dataclass(frozen=True)
class LedGenerationSelection:
    profile: LedTextProfile
    design_type: str
    text_effect: str
    font_style: str
    background_style: str
    style_seed: int | None


__all__ = ['LedGenerationSelection', 'LedTextProfile']
