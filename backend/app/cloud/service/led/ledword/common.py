from __future__ import annotations

import unicodedata
from typing import Dict, List, Optional, Sequence


LOCAL_EFFECT_STYLE_PALETTES: Dict[str, Dict[str, List[int]]] = {
    "black": {
        "bg_dark": [0, 0, 0],
        "bg_mid": [0, 0, 0],
        "bg_light": [0, 0, 0],
        "accent": [255, 138, 102],
        "text_main": [255, 216, 104],
        "text_alt": [108, 238, 255],
        "text_edge": [92, 38, 14],
        "halo": [255, 244, 206],
        "text_ramp": [
            [255, 84, 84],
            [255, 156, 72],
            [255, 226, 94],
            [148, 246, 98],
            [84, 236, 255],
            [102, 156, 255],
            [206, 118, 255],
        ],
    },
    "magenta_pixel": {
        "bg_dark": [20, 8, 34],
        "bg_mid": [94, 26, 88],
        "bg_light": [210, 84, 164],
        "accent": [255, 166, 222],
        "text_main": [116, 244, 255],
        "text_alt": [255, 204, 112],
        "text_edge": [78, 22, 56],
        "halo": [130, 246, 255],
    },
    "cyan_arcade": {
        "bg_dark": [8, 22, 34],
        "bg_mid": [18, 88, 132],
        "bg_light": [86, 216, 255],
        "accent": [176, 246, 255],
        "text_main": [255, 220, 96],
        "text_alt": [255, 246, 188],
        "text_edge": [10, 48, 68],
        "halo": [255, 226, 116],
    },
    "sunset_orange": {
        "bg_dark": [34, 10, 6],
        "bg_mid": [126, 42, 20],
        "bg_light": [255, 164, 82],
        "accent": [255, 210, 144],
        "text_main": [116, 240, 255],
        "text_alt": [190, 222, 255],
        "text_edge": [98, 24, 10],
        "halo": [132, 232, 255],
    },
    "emerald_neon": {
        "bg_dark": [6, 24, 16],
        "bg_mid": [22, 112, 70],
        "bg_light": [116, 242, 178],
        "accent": [180, 255, 222],
        "text_main": [255, 220, 96],
        "text_alt": [128, 226, 255],
        "text_edge": [10, 58, 38],
        "halo": [255, 226, 116],
    },
    "violet_glass": {
        "bg_dark": [16, 10, 34],
        "bg_mid": [72, 42, 122],
        "bg_light": [198, 110, 234],
        "accent": [236, 192, 255],
        "text_main": [118, 248, 255],
        "text_alt": [255, 176, 96],
        "text_edge": [54, 24, 88],
        "halo": [132, 246, 255],
    },
    "lime_matrix": {
        "bg_dark": [14, 22, 8],
        "bg_mid": [70, 116, 20],
        "bg_light": [190, 248, 98],
        "accent": [232, 255, 174],
        "text_main": [116, 210, 255],
        "text_alt": [255, 244, 176],
        "text_edge": [40, 66, 10],
        "halo": [132, 220, 255],
    },
    "ruby_laser": {
        "bg_dark": [84, 0, 0],
        "bg_mid": [255, 8, 0],
        "bg_light": [255, 80, 42],
        "accent": [255, 112, 74],
        "text_main": [255, 238, 142],
        "text_alt": [255, 184, 84],
        "text_edge": [120, 0, 0],
        "halo": [255, 86, 50],
    },
    "cobalt_electric": {
        "bg_dark": [5, 10, 36],
        "bg_mid": [18, 52, 150],
        "bg_light": [76, 136, 255],
        "accent": [150, 210, 255],
        "text_main": [255, 226, 96],
        "text_alt": [128, 252, 214],
        "text_edge": [8, 28, 86],
        "halo": [255, 232, 116],
    },
    "teal_circuit": {
        "bg_dark": [4, 22, 24],
        "bg_mid": [16, 104, 108],
        "bg_light": [76, 238, 224],
        "accent": [172, 255, 246],
        "text_main": [255, 220, 96],
        "text_alt": [255, 246, 188],
        "text_edge": [8, 58, 60],
        "halo": [255, 226, 116],
    },
    "amber_gold": {
        "bg_dark": [32, 16, 2],
        "bg_mid": [138, 80, 10],
        "bg_light": [255, 196, 76],
        "accent": [255, 232, 146],
        "text_main": [116, 236, 255],
        "text_alt": [184, 214, 255],
        "text_edge": [96, 52, 6],
        "halo": [126, 228, 255],
    },
    "rose_candy": {
        "bg_dark": [28, 8, 24],
        "bg_mid": [126, 34, 94],
        "bg_light": [255, 118, 196],
        "accent": [255, 196, 232],
        "text_main": [112, 246, 255],
        "text_alt": [255, 190, 118],
        "text_edge": [88, 20, 66],
        "halo": [132, 244, 255],
    },
    "royal_indigo": {
        "bg_dark": [10, 8, 38],
        "bg_mid": [44, 34, 132],
        "bg_light": [124, 92, 255],
        "accent": [194, 178, 255],
        "text_main": [118, 244, 255],
        "text_alt": [255, 170, 104],
        "text_edge": [34, 24, 94],
        "halo": [136, 238, 255],
    },
    "ice_blue": {
        "bg_dark": [5, 18, 34],
        "bg_mid": [22, 92, 146],
        "bg_light": [136, 226, 255],
        "accent": [214, 250, 255],
        "text_main": [255, 220, 96],
        "text_alt": [255, 248, 196],
        "text_edge": [8, 52, 82],
        "halo": [255, 228, 118],
    },
    "jade_lantern": {
        "bg_dark": [6, 28, 14],
        "bg_mid": [24, 126, 48],
        "bg_light": [112, 244, 110],
        "accent": [196, 255, 170],
        "text_main": [255, 224, 96],
        "text_alt": [132, 236, 255],
        "text_edge": [10, 70, 28],
        "halo": [255, 230, 118],
    },
    "coral_reef": {
        "bg_dark": [28, 12, 18],
        "bg_mid": [134, 50, 58],
        "bg_light": [255, 118, 92],
        "accent": [112, 242, 236],
        "text_main": [118, 246, 255],
        "text_alt": [255, 178, 118],
        "text_edge": [92, 28, 34],
        "halo": [128, 238, 255],
    },
    "sapphire_violet": {
        "bg_dark": [8, 10, 42],
        "bg_mid": [30, 48, 142],
        "bg_light": [128, 94, 244],
        "accent": [102, 228, 255],
        "text_main": [118, 242, 255],
        "text_alt": [255, 220, 118],
        "text_edge": [16, 28, 88],
        "halo": [140, 236, 255],
    },
    "copper_heat": {
        "bg_dark": [30, 12, 4],
        "bg_mid": [126, 58, 18],
        "bg_light": [238, 132, 52],
        "accent": [255, 206, 130],
        "text_main": [120, 238, 255],
        "text_alt": [178, 216, 255],
        "text_edge": [88, 34, 8],
        "halo": [132, 230, 255],
    },
    "mint_aurora": {
        "bg_dark": [4, 22, 20],
        "bg_mid": [20, 104, 86],
        "bg_light": [102, 250, 186],
        "accent": [178, 255, 224],
        "text_main": [255, 220, 96],
        "text_alt": [255, 248, 188],
        "text_edge": [8, 58, 48],
        "halo": [255, 226, 116],
    },
    "crimson_noir": {
        "bg_dark": [72, 0, 0],
        "bg_mid": [255, 0, 0],
        "bg_light": [255, 44, 34],
        "accent": [255, 104, 64],
        "text_main": [255, 242, 152],
        "text_alt": [255, 190, 88],
        "text_edge": [112, 0, 6],
        "halo": [255, 74, 48],
    },
    "aqua_lagoon": {
        "bg_dark": [4, 20, 30],
        "bg_mid": [12, 96, 126],
        "bg_light": [72, 230, 246],
        "accent": [170, 255, 236],
        "text_main": [255, 220, 96],
        "text_alt": [255, 246, 188],
        "text_edge": [8, 54, 70],
        "halo": [255, 226, 116],
    },
    "lemon_lime": {
        "bg_dark": [18, 22, 4],
        "bg_mid": [92, 120, 14],
        "bg_light": [232, 250, 64],
        "accent": [255, 255, 162],
        "text_main": [118, 196, 255],
        "text_alt": [246, 255, 220],
        "text_edge": [58, 72, 8],
        "halo": [136, 210, 255],
    },
    "soft_lavender": {
        "bg_dark": [18, 12, 34],
        "bg_mid": [82, 58, 130],
        "bg_light": [190, 146, 244],
        "accent": [230, 206, 255],
        "text_main": [118, 244, 255],
        "text_alt": [255, 176, 104],
        "text_edge": [58, 38, 90],
        "halo": [134, 238, 255],
    },
    "tangerine_pink": {
        "bg_dark": [30, 8, 10],
        "bg_mid": [136, 40, 42],
        "bg_light": [255, 118, 58],
        "accent": [255, 168, 210],
        "text_main": [116, 238, 255],
        "text_alt": [255, 164, 116],
        "text_edge": [92, 22, 24],
        "halo": [132, 232, 255],
    },
    "deep_sea": {
        "bg_dark": [2, 14, 30],
        "bg_mid": [8, 58, 112],
        "bg_light": [36, 160, 228],
        "accent": [112, 238, 255],
        "text_main": [255, 224, 96],
        "text_alt": [130, 248, 222],
        "text_edge": [4, 34, 68],
        "halo": [255, 230, 118],
    },
    "plasma_blue": {
        "bg_dark": [8, 8, 34],
        "bg_mid": [24, 34, 146],
        "bg_light": [62, 98, 255],
        "accent": [255, 128, 230],
        "text_main": [255, 224, 96],
        "text_alt": [122, 246, 255],
        "text_edge": [14, 22, 92],
        "halo": [255, 230, 118],
    },
}

OPENING_PUNCTUATION = frozenset({
    "(",
    "[",
    "{",
    "<",
    "（",
    "【",
    "《",
    "〈",
    "「",
    "『",
    "〔",
    "〖",
    "〘",
    "〚",
    "“",
    "‘",
})

TRAILING_PUNCTUATION = frozenset({
    ")",
    "]",
    "}",
    ">",
    "）",
    "】",
    "》",
    "〉",
    "」",
    "』",
    "〕",
    "〗",
    "〙",
    "〛",
    "”",
    "’",
    "、",
    "。",
    "，",
    "；",
    "：",
    "！",
    "？",
    ",",
    ".",
    "!",
    "?",
    ";",
    ":",
})


def derive_seed(seed: Optional[int], salt: int) -> Optional[int]:
    if seed is None:
        return None
    return int(seed) * 9973 + salt


def is_latin_character(char: str) -> bool:
    codepoint = ord(char)
    return (
        0x0041 <= codepoint <= 0x005A
        or 0x0061 <= codepoint <= 0x007A
        or 0x00C0 <= codepoint <= 0x024F
    )


def is_cjk_character(char: str) -> bool:
    codepoint = ord(char)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x20000 <= codepoint <= 0x2A6DF
        or 0x2A700 <= codepoint <= 0x2B73F
        or 0x2B740 <= codepoint <= 0x2B81F
        or 0x2B820 <= codepoint <= 0x2CEAF
    )


def visible_chars(text: str) -> List[str]:
    return [char for char in str(text or "") if not char.isspace()]


def visible_text_length(text: Optional[str]) -> int:
    return len(visible_chars(str(text or "")))


def recognition_handoff_units(text: Optional[str]) -> List[str]:
    normalized = str(text or "").strip()
    if not normalized:
        return []

    base_units: List[str] = []
    current_word: List[str] = []
    for char in normalized:
        if char.isspace():
            _flush_recognition_word(base_units, current_word)
            continue
        if _is_recognition_word_char(char):
            current_word.append(char)
            continue
        _flush_recognition_word(base_units, current_word)
        base_units.append(char)
    _flush_recognition_word(base_units, current_word)

    units: List[str] = []
    pending_prefix = ""
    for token in base_units:
        if _is_opening_punctuation_token(token):
            pending_prefix += token
            continue
        if _is_trailing_punctuation_token(token):
            if units:
                units[-1] += token
            else:
                pending_prefix += token
            continue
        units.append(pending_prefix + token)
        pending_prefix = ""

    if pending_prefix:
        if units:
            units[-1] += pending_prefix
        else:
            units.append(pending_prefix)
    return units


def _flush_recognition_word(units: List[str], current_word: List[str]) -> None:
    if current_word:
        units.append("".join(current_word))
        current_word.clear()


def _is_recognition_word_char(char: str) -> bool:
    return is_latin_character(char) or char.isdigit() or char in {"'", "’", "-", "_"}


def _is_opening_punctuation_token(token: str) -> bool:
    return len(token) == 1 and token in OPENING_PUNCTUATION


def _is_trailing_punctuation_token(token: str) -> bool:
    if len(token) != 1:
        return False
    if token in TRAILING_PUNCTUATION:
        return True
    return unicodedata.category(token).startswith("P")


def mix_rgb(color_a: Sequence[int], color_b: Sequence[int], t: float) -> List[int]:
    resolved_t = max(0.0, min(1.0, float(t)))
    return [
        int(round(channel_a + (channel_b - channel_a) * resolved_t))
        for channel_a, channel_b in zip(color_a, color_b)
    ]


def resolve_local_palette(style_name: str) -> Dict[str, List[int]]:
    resolved_style_name = style_name if style_name in LOCAL_EFFECT_STYLE_PALETTES else "cyan_arcade"
    base_palette = LOCAL_EFFECT_STYLE_PALETTES[resolved_style_name]

    bg_dark = mix_rgb(base_palette["bg_dark"], [0, 0, 0], 0.12)
    bg_mid = mix_rgb(base_palette["bg_mid"], bg_dark, 0.14)
    bg_light = mix_rgb(base_palette["bg_light"], base_palette["bg_mid"], 0.10)
    accent = mix_rgb(base_palette["accent"], [255, 255, 255], 0.06)
    text_main = mix_rgb(base_palette["text_main"], [255, 255, 255], 0.08)
    text_alt = mix_rgb(base_palette["text_alt"], [255, 255, 255], 0.06)
    text_edge = mix_rgb(base_palette["text_edge"], bg_dark, 0.22)
    halo = mix_rgb(base_palette["halo"], [255, 255, 255], 0.08)
    base_ramp = base_palette.get("text_ramp")
    if base_ramp:
        text_ramp = [mix_rgb(color, [255, 255, 255], 0.04) for color in base_ramp]
    else:
        text_ramp = [
            text_main,
            mix_rgb(text_main, accent, 0.42),
            mix_rgb(text_main, text_alt, 0.58),
            text_alt,
            mix_rgb(text_alt, halo, 0.40),
            mix_rgb(accent, halo, 0.58),
            halo,
        ]
    return {
        "bg_dark": bg_dark,
        "bg_mid": bg_mid,
        "bg_light": bg_light,
        "accent": accent,
        "text_main": text_main,
        "text_alt": text_alt,
        "text_edge": text_edge,
        "halo": halo,
        "text_ramp": text_ramp,
    }


__all__ = [
    "LOCAL_EFFECT_STYLE_PALETTES",
    "derive_seed",
    "is_cjk_character",
    "is_latin_character",
    "mix_rgb",
    "recognition_handoff_units",
    "resolve_local_palette",
    "visible_chars",
    "visible_text_length",
]
