from __future__ import annotations

import random
import re

from dataclasses import dataclass

from backend.app.cloud.service.led.ledword.common import (
    is_cjk_character,
    is_latin_character,
    recognition_handoff_units,
    visible_chars,
    visible_text_length,
)
from backend.app.cloud.service.led.ledword.style_catalog import (
    DESIGN_TYPE_BOX,
    DESIGN_TYPE_CENTER_BURST,
    DESIGN_TYPE_DECODE,
    DESIGN_TYPE_DEFINITIONS,
    DESIGN_TYPE_FLIPBOARD,
    DESIGN_TYPE_GLITCH,
    DESIGN_TYPE_INVERSE,
    DESIGN_TYPE_MARQUEE,
    DESIGN_TYPE_OUTLINE_SCAN,
    DESIGN_TYPE_PIXEL,
    DESIGN_TYPE_RAINDROP,
    DESIGN_TYPE_RECOGNITION,
    DESIGN_TYPE_SCANLINE,
    DESIGN_TYPE_SEQUENTIAL_OUTLINE,
    DESIGN_TYPE_SEQUENTIAL_PIXEL,
    DESIGN_TYPE_STAMP,
    DESIGN_TYPE_STAR_GATHER,
    DESIGN_TYPE_STRETCH,
    DESIGN_TYPE_STROKE,
    DESIGN_TYPE_WAVE,
)
from backend.app.cloud.service.led.ledword.styles import (
    DEFAULT_BACKGROUND_STYLE,
    infer_font_script,
    resolve_text_effect_name_from_design_type,
    text_effect_length_limit_for_text,
)
from backend.app.cloud.service.led.models import LedGenerationSelection, LedTextProfile
from backend.common.exception import errors


MULTI_WORD_PATTERN = re.compile(r'\S+\s+\S+')
LATIN_WORD_PATTERN = re.compile(r'[A-Za-z]+')

FONT_STYLE_ROUNDPIX = 'roundpix_pixel'
FONT_STYLE_MISANS = 'misans_heavy'
LONG_TEXT_FONT_FALLBACK_THRESHOLD = 4
LOW_RES_CJK_RISKY_FONT_NAMES = frozenset({FONT_STYLE_ROUNDPIX})


@dataclass(frozen=True)
class LedDesignCandidate:
    design_type: str
    font_style: str


CHINESE_TWO_CHAR_CANDIDATES = (
    LedDesignCandidate(DESIGN_TYPE_SCANLINE, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_DECODE, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_GLITCH, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_CENTER_BURST, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_OUTLINE_SCAN, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_SEQUENTIAL_OUTLINE, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_STROKE, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_STAMP, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_RAINDROP, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_WAVE, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_STRETCH, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_BOX, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_INVERSE, FONT_STYLE_ROUNDPIX),
)

CHINESE_MULTI_CHAR_CANDIDATES = (
    LedDesignCandidate(DESIGN_TYPE_PIXEL, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_STAR_GATHER, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_FLIPBOARD, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_MARQUEE, FONT_STYLE_MISANS),
    LedDesignCandidate(DESIGN_TYPE_RECOGNITION, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_SEQUENTIAL_PIXEL, FONT_STYLE_ROUNDPIX),
)

LATIN_MULTI_WORD_SHORT_CANDIDATES = (
    LedDesignCandidate(DESIGN_TYPE_FLIPBOARD, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_MARQUEE, FONT_STYLE_ROUNDPIX),
)

LATIN_MULTI_WORD_LONG_CANDIDATES = (
    LedDesignCandidate(DESIGN_TYPE_RECOGNITION, FONT_STYLE_ROUNDPIX),
)

LATIN_SINGLE_WORD_LONG_SAFE_CANDIDATES = (
    LedDesignCandidate(DESIGN_TYPE_PIXEL, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_STAR_GATHER, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_SEQUENTIAL_OUTLINE, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_SEQUENTIAL_PIXEL, FONT_STYLE_ROUNDPIX),
)

LATIN_SINGLE_WORD_SHORT_ONLY_CANDIDATES = (
    LedDesignCandidate(DESIGN_TYPE_SCANLINE, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_DECODE, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_GLITCH, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_CENTER_BURST, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_OUTLINE_SCAN, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_STROKE, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_STAMP, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_RAINDROP, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_WAVE, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_STRETCH, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_BOX, FONT_STYLE_ROUNDPIX),
    LedDesignCandidate(DESIGN_TYPE_INVERSE, FONT_STYLE_ROUNDPIX),
)


def build_text_profile(text: str) -> LedTextProfile:
    normalized_text = str(text or '').replace('\ufeff', '').strip()
    if not normalized_text:
        raise errors.RequestError(msg='text must not be empty')

    visible = visible_chars(normalized_text)
    has_cjk = any(is_cjk_character(char) for char in visible)
    has_latin = any(is_latin_character(char) for char in visible)
    latin_word_count = len(LATIN_WORD_PATTERN.findall(normalized_text))
    return LedTextProfile(
        text=normalized_text,
        visible_length=visible_text_length(normalized_text),
        font_script=infer_font_script(normalized_text),
        latin_word_count=latin_word_count,
        has_cjk=has_cjk,
        has_latin=has_latin,
    )


def resolve_generation_selection(
    *,
    text: str,
    design_type: str | None,
    font_style: str | None,
    background_style: str | None,
    style_seed: int | None,
) -> LedGenerationSelection:
    profile = build_text_profile(text)
    auto_candidate = None
    if not str(design_type or '').strip():
        auto_candidate = select_design_candidate(profile, style_seed=style_seed)
        resolved_design_type = auto_candidate.design_type
    else:
        resolved_design_type = str(design_type).strip()

    try:
        text_effect = resolve_text_effect_name_from_design_type(resolved_design_type)
    except ValueError as exc:
        raise errors.RequestError(msg=str(exc)) from exc

    limit = text_effect_length_limit_for_text(text_effect, text=profile.text)
    measured_units = _measured_display_units(
        text_effect=text_effect,
        text=profile.text,
        visible_length=profile.visible_length,
    )
    if limit is not None and measured_units > limit:
        raise errors.RequestError(
            msg=(
                f'当前文本不支持灯效“{resolved_design_type}”，'
                f'该灯效最多支持 {limit} 个显示单元，'
                f'当前为 {measured_units}'
            )
        )

    if str(font_style or '').strip():
        resolved_font_style = str(font_style).strip()
    elif auto_candidate is not None:
        resolved_font_style = auto_candidate.font_style
    else:
        resolved_font_style = preferred_font_style_for_design(profile, resolved_design_type)

    resolved_font_style = stabilize_font_style_for_text(profile, resolved_font_style)
    normalized_background_style = str(background_style or '').strip() or DEFAULT_BACKGROUND_STYLE
    return LedGenerationSelection(
        profile=profile,
        design_type=resolved_design_type,
        text_effect=text_effect,
        font_style=resolved_font_style,
        background_style=normalized_background_style,
        style_seed=style_seed,
    )


def supported_design_types_for_text(text: str) -> list[str]:
    profile = build_text_profile(text)
    supported: list[str] = []
    for definition in DESIGN_TYPE_DEFINITIONS:
        text_effect = definition.effect_name
        limit = text_effect_length_limit_for_text(text_effect, text=profile.text)
        measured_units = _measured_display_units(
            text_effect=text_effect,
            text=profile.text,
            visible_length=profile.visible_length,
        )
        if limit is None or measured_units <= limit:
            supported.append(definition.display_name)
    return supported


def recommended_design_types_for_text(text: str) -> list[str]:
    return [candidate.design_type for candidate in recommended_design_candidates_for_text(text)]


def recommended_design_candidates_for_text(text: str) -> list[LedDesignCandidate]:
    return recommended_design_candidates_for_profile(build_text_profile(text))


def recommended_design_candidates_for_profile(profile: LedTextProfile) -> list[LedDesignCandidate]:
    candidates = _candidate_pool_for_profile(profile)
    return _filter_supported_candidates(profile, candidates)


def preferred_font_style_for_design(profile: LedTextProfile, design_type: str) -> str:
    for candidate in recommended_design_candidates_for_profile(profile):
        if candidate.design_type == design_type:
            return candidate.font_style
    if design_type == DESIGN_TYPE_MARQUEE and profile.has_cjk:
        return FONT_STYLE_MISANS
    return FONT_STYLE_ROUNDPIX


def stabilize_font_style_for_text(profile: LedTextProfile, font_style: str) -> str:
    if profile.visible_length <= LONG_TEXT_FONT_FALLBACK_THRESHOLD:
        return font_style
    if font_style not in LOW_RES_CJK_RISKY_FONT_NAMES:
        return font_style
    return FONT_STYLE_MISANS


def select_design_candidate(profile: LedTextProfile, *, style_seed: int | None) -> LedDesignCandidate:
    candidates = recommended_design_candidates_for_profile(profile)
    if not candidates:
        raise errors.RequestError(msg='no supported design type is available for current text')
    if len(candidates) == 1:
        return candidates[0]
    return _build_random(style_seed).choice(candidates)


def _candidate_pool_for_profile(profile: LedTextProfile) -> tuple[LedDesignCandidate, ...]:
    if profile.visible_length <= 0:
        raise errors.RequestError(msg='text must not be empty')

    if profile.is_multi_word_latin:
        if profile.visible_length <= 12 and profile.latin_word_count <= 2 and MULTI_WORD_PATTERN.search(profile.text):
            return LATIN_MULTI_WORD_SHORT_CANDIDATES
        return LATIN_MULTI_WORD_LONG_CANDIDATES

    if profile.has_cjk:
        if profile.visible_length <= 2:
            return CHINESE_TWO_CHAR_CANDIDATES
        return CHINESE_MULTI_CHAR_CANDIDATES

    if profile.has_latin and not profile.has_cjk:
        if profile.visible_length > 12:
            return LATIN_SINGLE_WORD_LONG_SAFE_CANDIDATES
        return _dedupe_candidates(
            LATIN_SINGLE_WORD_LONG_SAFE_CANDIDATES + LATIN_SINGLE_WORD_SHORT_ONLY_CANDIDATES
        )

    if profile.visible_length <= 2:
        return CHINESE_TWO_CHAR_CANDIDATES
    return CHINESE_MULTI_CHAR_CANDIDATES


def _filter_supported_candidates(
    profile: LedTextProfile,
    candidates: tuple[LedDesignCandidate, ...],
) -> list[LedDesignCandidate]:
    filtered_candidates: list[LedDesignCandidate] = []
    for candidate in candidates:
        text_effect = resolve_text_effect_name_from_design_type(candidate.design_type)
        limit = text_effect_length_limit_for_text(text_effect, text=profile.text)
        measured_units = _measured_display_units(
            text_effect=text_effect,
            text=profile.text,
            visible_length=profile.visible_length,
        )
        if limit is None or measured_units <= limit:
            filtered_candidates.append(candidate)
    return filtered_candidates


def _dedupe_candidates(candidates: tuple[LedDesignCandidate, ...]) -> tuple[LedDesignCandidate, ...]:
    deduped: list[LedDesignCandidate] = []
    seen_design_types: set[str] = set()
    for candidate in candidates:
        if candidate.design_type in seen_design_types:
            continue
        seen_design_types.add(candidate.design_type)
        deduped.append(candidate)
    return tuple(deduped)


def _build_random(style_seed: int | None) -> random.Random:
    if style_seed is None:
        return random.SystemRandom()
    return random.Random(int(style_seed))


def _measured_display_units(
    *,
    text_effect: str,
    text: str,
    visible_length: int,
) -> int:
    if text_effect == 'recognition_handoff_reveal':
        return len(recognition_handoff_units(text))
    return visible_length


__all__ = [
    'LedDesignCandidate',
    'build_text_profile',
    'recommended_design_candidates_for_text',
    'recommended_design_types_for_text',
    'resolve_generation_selection',
    'supported_design_types_for_text',
]
