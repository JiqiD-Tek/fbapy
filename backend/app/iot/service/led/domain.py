from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


EXPECTED_WIDTH = 29
EXPECTED_HEIGHT = 16
EXPECTED_INTERVAL_MS = 30

STANDARD_FUNCTION_NAME = 'renderFrame'
STANDARD_INPUT_NAME = 'audio'
STANDARD_AUDIO_FEATURE_GUIDANCE = (
    (
        'energy',
        'overall openness, primary motion span, background density, and global intensity staging',
    ),
    (
        'bass',
        'heavy displacement, bottom impact, breathing push, and low-end directional drive',
    ),
    (
        'mid',
        'internal layering, contour reshaping, and core structure variation',
    ),
    (
        'high',
        'edge shimmer, highlight flicker, fine particles, and crisp detail accents',
    ),
    (
        'onset',
        'transient trigger pulses, short flashes, rhythmic hits, and event accents',
    ),
)
STANDARD_AUDIO_FEATURE_NAMES = tuple(name for name, _ in STANDARD_AUDIO_FEATURE_GUIDANCE)
RENDER_FUNCTION_PATTERN = re.compile(r'\brenderFrame\s*\(\s*audio\s*\)')


@dataclass(frozen=True)
class EnergyStageMapping:
    low: list[str]
    medium: list[str]
    high: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'EnergyStageMapping':
        return cls(
            low=_string_list('energy_mapping.low', data.get('low', [])),
            medium=_string_list('energy_mapping.medium', data.get('medium', [])),
            high=_string_list('energy_mapping.high', data.get('high', [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'low': list(self.low),
            'medium': list(self.medium),
            'high': list(self.high),
        }

    def validate(self) -> None:
        _require_string_items('energy_mapping.low', self.low, minimum=2)
        _require_string_items('energy_mapping.medium', self.medium, minimum=2)
        _require_string_items('energy_mapping.high', self.high, minimum=2)


@dataclass(frozen=True)
class AudioFeatureRoleMapping:
    energy: list[str]
    bass: list[str]
    mid: list[str]
    high: list[str]
    onset: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'AudioFeatureRoleMapping':
        return cls(
            energy=_string_list('audio_feature_mapping.energy', data.get('energy', [])),
            bass=_string_list('audio_feature_mapping.bass', data.get('bass', [])),
            mid=_string_list('audio_feature_mapping.mid', data.get('mid', [])),
            high=_string_list('audio_feature_mapping.high', data.get('high', [])),
            onset=_string_list('audio_feature_mapping.onset', data.get('onset', [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'energy': list(self.energy),
            'bass': list(self.bass),
            'mid': list(self.mid),
            'high': list(self.high),
            'onset': list(self.onset),
        }

    def validate(self) -> None:
        _require_string_items('audio_feature_mapping.energy', self.energy, minimum=2)
        _require_string_items('audio_feature_mapping.bass', self.bass, minimum=2)
        _require_string_items('audio_feature_mapping.mid', self.mid, minimum=2)
        _require_string_items('audio_feature_mapping.high', self.high, minimum=2)
        _require_string_items('audio_feature_mapping.onset', self.onset, minimum=2)


@dataclass(frozen=True)
class SemanticDesign:
    name: str
    raw_user_request: str
    expanded_request: str
    summary: str
    subject: str
    color_palette: list[str]
    composition: list[str]
    motion_rules: list[str]
    energy_mapping: EnergyStageMapping
    audio_feature_mapping: AudioFeatureRoleMapping
    avoid_list: list[str]
    implementation_hints: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'SemanticDesign':
        if not isinstance(data, dict):
            raise ValueError('semantic design payload must be an object')

        energy_mapping = data.get('energy_mapping')
        audio_feature_mapping = data.get('audio_feature_mapping')
        if not isinstance(energy_mapping, dict):
            raise ValueError('energy_mapping must be an object')
        if not isinstance(audio_feature_mapping, dict):
            raise ValueError('audio_feature_mapping must be an object')

        design = cls(
            name=_clean_string(data.get('name')) or 'led-animation',
            raw_user_request=_clean_string(data.get('raw_user_request') or data.get('user_request')),
            expanded_request=_clean_string(data.get('expanded_request') or data.get('raw_user_request') or data.get('user_request')),
            summary=_clean_string(data.get('summary')),
            subject=_clean_string(data.get('subject')),
            color_palette=_string_list('color_palette', data.get('color_palette', [])),
            composition=_string_list('composition', data.get('composition', [])),
            motion_rules=_string_list('motion_rules', data.get('motion_rules', [])),
            energy_mapping=EnergyStageMapping.from_dict(energy_mapping),
            audio_feature_mapping=AudioFeatureRoleMapping.from_dict(audio_feature_mapping),
            avoid_list=_string_list('avoid_list', data.get('avoid_list', [])),
            implementation_hints=_string_list('implementation_hints', data.get('implementation_hints', [])),
        )
        design.validate()
        return design

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'raw_user_request': self.raw_user_request,
            'expanded_request': self.expanded_request,
            'summary': self.summary,
            'subject': self.subject,
            'color_palette': list(self.color_palette),
            'composition': list(self.composition),
            'motion_rules': list(self.motion_rules),
            'energy_mapping': self.energy_mapping.to_dict(),
            'audio_feature_mapping': self.audio_feature_mapping.to_dict(),
            'avoid_list': list(self.avoid_list),
            'implementation_hints': list(self.implementation_hints),
        }

    def validate(self) -> None:
        _require_non_empty('name', self.name)
        _require_non_empty('raw_user_request', self.raw_user_request)
        _require_non_empty('expanded_request', self.expanded_request)
        _require_non_empty('summary', self.summary)
        _require_non_empty('subject', self.subject)
        _require_string_items('color_palette', self.color_palette, minimum=2)
        _require_string_items('composition', self.composition, minimum=2)
        _require_string_items('motion_rules', self.motion_rules, minimum=3)
        self.energy_mapping.validate()
        self.audio_feature_mapping.validate()
        _require_string_items('avoid_list', self.avoid_list, minimum=2)
        _require_string_items('implementation_hints', self.implementation_hints, minimum=3)


def build_audio_feature_guidance_lines(prefix: str = '- ') -> list[str]:
    return [
        '{0}{1}: {2}'.format(prefix, feature_name, description)
        for feature_name, description in STANDARD_AUDIO_FEATURE_GUIDANCE
    ]


def validate_function_code(function_code: str) -> str:
    normalized_code = _clean_string(function_code)
    _require_non_empty('function_code', normalized_code)

    if not RENDER_FUNCTION_PATTERN.search(normalized_code):
        raise ValueError('function_code must define renderFrame(audio)')

    for feature_name in STANDARD_AUDIO_FEATURE_NAMES:
        if not re.search(r'\b{0}\b'.format(re.escape(feature_name)), normalized_code):
            raise ValueError(
                'function_code must reference audio feature {0!r}'.format(feature_name)
            )

    return normalized_code


def _clean_string(value: Any) -> str:
    return str(value or '').strip()


def _string_list(name: str, items: Any) -> list[str]:
    if items is None:
        return []
    if isinstance(items, (str, bytes)):
        raise ValueError('{0} must be an array, not a string'.format(name))
    if not isinstance(items, Sequence):
        raise ValueError('{0} must be an array'.format(name))
    return [str(item).strip() for item in items]


def _require_non_empty(name: str, value: str) -> None:
    if not value:
        raise ValueError('{0} must not be empty'.format(name))


def _require_string_items(name: str, items: Sequence[str], *, minimum: int) -> None:
    if len(items) < minimum:
        raise ValueError('{0} must contain at least {1} items'.format(name, minimum))
    if any(not item for item in items):
        raise ValueError('{0} must not contain empty items'.format(name))


__all__ = [
    'EXPECTED_HEIGHT',
    'EXPECTED_INTERVAL_MS',
    'EXPECTED_WIDTH',
    'STANDARD_AUDIO_FEATURE_GUIDANCE',
    'STANDARD_AUDIO_FEATURE_NAMES',
    'AudioFeatureRoleMapping',
    'EnergyStageMapping',
    'SemanticDesign',
    'build_audio_feature_guidance_lines',
    'validate_function_code',
]
