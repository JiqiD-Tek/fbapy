from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


EXPECTED_WIDTH = 29
EXPECTED_HEIGHT = 16
EXPECTED_INTERVAL_MS = 30
EXPECTED_PIXEL_COUNT = EXPECTED_WIDTH * EXPECTED_HEIGHT

STANDARD_COORDINATE_ORDER = 'row-major'
STANDARD_LANGUAGE = 'javascript'
STANDARD_FUNCTION_NAME = 'renderFrame'
STANDARD_SIGNATURE = 'function renderFrame(audio)'
STANDARD_PIXEL_ORDER = 'frame[row][column]'
STANDARD_INPUT_NAME = 'audio'
STANDARD_AUDIO_FEATURE_GUIDANCE = [
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
]
STANDARD_AUDIO_FEATURE_NAMES = [name for name, _ in STANDARD_AUDIO_FEATURE_GUIDANCE]


@dataclass(frozen=True)
class BoardSpec:
    width: int
    height: int
    pixel_count: int
    coordinate_order: str

    @classmethod
    def standard(cls) -> 'BoardSpec':
        return cls(
            width=EXPECTED_WIDTH,
            height=EXPECTED_HEIGHT,
            pixel_count=EXPECTED_PIXEL_COUNT,
            coordinate_order=STANDARD_COORDINATE_ORDER,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'BoardSpec':
        return cls(
            width=int(data.get('width', 0)),
            height=int(data.get('height', 0)),
            pixel_count=int(data.get('pixel_count', 0)),
            coordinate_order=_clean_string(data.get('coordinate_order')),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'width': self.width,
            'height': self.height,
            'pixel_count': self.pixel_count,
            'coordinate_order': self.coordinate_order,
        }


@dataclass(frozen=True)
class InputFeatureSpec:
    name: str
    type: str
    minimum: float
    maximum: float
    description: str

    @classmethod
    def standard_audio_features(cls) -> list['InputFeatureSpec']:
        return [
            cls(
                name=name,
                type='number',
                minimum=0.0,
                maximum=1.0,
                description=description,
            )
            for name, description in STANDARD_AUDIO_FEATURE_GUIDANCE
        ]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'InputFeatureSpec':
        return cls(
            name=_clean_string(data.get('name')),
            type=_clean_string(data.get('type')),
            minimum=float(data.get('minimum', 0.0)),
            maximum=float(data.get('maximum', 0.0)),
            description=_clean_string(data.get('description')),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'type': self.type,
            'minimum': self.minimum,
            'maximum': self.maximum,
            'description': self.description,
        }

    def validate(self) -> None:
        _require_non_empty('input_feature.name', self.name)
        if self.type not in {'number', 'float'}:
            raise ValueError("input_feature.type must be 'number' or 'float'")
        if self.minimum > 0.0:
            raise ValueError('input_feature.minimum must be <= 0.0')
        if self.maximum < 1.0:
            raise ValueError('input_feature.maximum must be >= 1.0')
        _require_non_empty('input_feature.description', self.description)


@dataclass(frozen=True)
class InputParameterSpec:
    name: str
    type: str
    description: str
    features: list[InputFeatureSpec]

    @classmethod
    def standard_audio(cls) -> 'InputParameterSpec':
        return cls(
            name=STANDARD_INPUT_NAME,
            type='object',
            description='normalized audio feature bundle with distinct reactive roles',
            features=InputFeatureSpec.standard_audio_features(),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'InputParameterSpec':
        features = data.get('features')
        if not isinstance(features, list):
            raise ValueError('timing.input_parameter.features must be an array')
        return cls(
            name=_clean_string(data.get('name')),
            type=_clean_string(data.get('type')),
            description=_clean_string(data.get('description')),
            features=[InputFeatureSpec.from_dict(item) for item in features],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'type': self.type,
            'description': self.description,
            'features': [feature.to_dict() for feature in self.features],
        }

    def validate(self) -> None:
        _require_exact('timing.input_parameter.name', self.name, STANDARD_INPUT_NAME)
        _require_exact('timing.input_parameter.type', self.type, 'object')
        _require_non_empty('timing.input_parameter.description', self.description)
        if len(self.features) != len(STANDARD_AUDIO_FEATURE_NAMES):
            raise ValueError(
                'timing.input_parameter.features must contain exactly {0} items'.format(
                    len(STANDARD_AUDIO_FEATURE_NAMES)
                )
            )
        actual_feature_names = [feature.name for feature in self.features]
        if actual_feature_names != STANDARD_AUDIO_FEATURE_NAMES:
            raise ValueError(
                'timing.input_parameter.features must be ordered as {0!r}'.format(
                    STANDARD_AUDIO_FEATURE_NAMES
                )
            )
        for feature in self.features:
            feature.validate()


@dataclass(frozen=True)
class TimingSpec:
    frame_interval_ms: int
    input_parameter: InputParameterSpec

    @classmethod
    def standard(cls) -> 'TimingSpec':
        return cls(
            frame_interval_ms=EXPECTED_INTERVAL_MS,
            input_parameter=InputParameterSpec.standard_audio(),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'TimingSpec':
        input_parameter = data.get('input_parameter')
        if not isinstance(input_parameter, dict):
            raise ValueError('timing.input_parameter must be an object')
        return cls(
            frame_interval_ms=int(data.get('frame_interval_ms', 0)),
            input_parameter=InputParameterSpec.from_dict(input_parameter),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'frame_interval_ms': self.frame_interval_ms,
            'input_parameter': self.input_parameter.to_dict(),
        }


@dataclass(frozen=True)
class OutputContractSpec:
    language: str
    function_name: str
    signature: str
    return_type: str
    pixel_order: str

    @classmethod
    def standard_render_frame(cls) -> 'OutputContractSpec':
        return cls(
            language=STANDARD_LANGUAGE,
            function_name=STANDARD_FUNCTION_NAME,
            signature=STANDARD_SIGNATURE,
            return_type=f'{EXPECTED_HEIGHT} rows x {EXPECTED_WIDTH} columns of [r, g, b]',
            pixel_order=STANDARD_PIXEL_ORDER,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'OutputContractSpec':
        return cls(
            language=_clean_string(data.get('language')),
            function_name=_clean_string(data.get('function_name')),
            signature=_clean_string(data.get('signature')),
            return_type=_clean_string(data.get('return_type')),
            pixel_order=_clean_string(data.get('pixel_order')),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'language': self.language,
            'function_name': self.function_name,
            'signature': self.signature,
            'return_type': self.return_type,
            'pixel_order': self.pixel_order,
        }


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

    def to_spec_lines(self) -> list[str]:
        return [
            'Low energy: {0}'.format('; '.join(self.low)),
            'Medium energy: {0}'.format('; '.join(self.medium)),
            'High energy: {0}'.format('; '.join(self.high)),
        ]

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

    def to_spec_lines(self) -> list[str]:
        return [
            'Audio energy: {0}'.format('; '.join(self.energy)),
            'Audio bass: {0}'.format('; '.join(self.bass)),
            'Audio mid: {0}'.format('; '.join(self.mid)),
            'Audio high: {0}'.format('; '.join(self.high)),
            'Audio onset: {0}'.format('; '.join(self.onset)),
        ]

    def validate(self) -> None:
        _require_string_items('audio_feature_mapping.energy', self.energy, minimum=2)
        _require_string_items('audio_feature_mapping.bass', self.bass, minimum=2)
        _require_string_items('audio_feature_mapping.mid', self.mid, minimum=2)
        _require_string_items('audio_feature_mapping.high', self.high, minimum=2)
        _require_string_items('audio_feature_mapping.onset', self.onset, minimum=2)


@dataclass(frozen=True)
class SemanticDesign:
    name: str
    user_request: str
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
            user_request=_clean_string(data.get('user_request')),
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
            'user_request': self.user_request,
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

    def build_visual_notes(self) -> list[str]:
        return (
            ['Subject: {0}'.format(self.subject)]
            + ['Color: {0}'.format(item) for item in self.color_palette]
            + ['Composition: {0}'.format(item) for item in self.composition]
            + ['Motion: {0}'.format(item) for item in self.motion_rules]
        )

    def build_implementation_notes(self) -> list[str]:
        notes = ['Hint: {0}'.format(item) for item in self.implementation_hints]
        if self.avoid_list:
            notes.append('Avoid: {0}'.format('; '.join(self.avoid_list)))
        return notes

    def validate(self) -> None:
        _require_non_empty('name', self.name)
        _require_non_empty('user_request', self.user_request)
        _require_non_empty('summary', self.summary)
        _require_non_empty('subject', self.subject)
        _require_string_items('color_palette', self.color_palette, minimum=2)
        _require_string_items('composition', self.composition, minimum=2)
        _require_string_items('motion_rules', self.motion_rules, minimum=3)
        self.energy_mapping.validate()
        self.audio_feature_mapping.validate()
        _require_string_items('avoid_list', self.avoid_list, minimum=2)
        _require_string_items('implementation_hints', self.implementation_hints, minimum=3)


@dataclass(frozen=True)
class LedAnimationSpec:
    name: str
    user_request: str
    summary: str
    board: BoardSpec
    timing: TimingSpec
    visual_notes: list[str]
    energy_mapping: list[str]
    audio_feature_mapping: list[str]
    implementation_notes: list[str]
    output_contract: OutputContractSpec
    function_code: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'LedAnimationSpec':
        if not isinstance(data, dict):
            raise ValueError('spec payload must be an object')

        board = data.get('board')
        timing = data.get('timing')
        output_contract = data.get('output_contract')
        if not isinstance(board, dict):
            raise ValueError('board must be an object')
        if not isinstance(timing, dict):
            raise ValueError('timing must be an object')
        if not isinstance(output_contract, dict):
            raise ValueError('output_contract must be an object')

        spec = cls(
            name=_clean_string(data.get('name')) or 'led-animation',
            user_request=_clean_string(data.get('user_request')),
            summary=_clean_string(data.get('summary')),
            board=BoardSpec.from_dict(board),
            timing=TimingSpec.from_dict(timing),
            visual_notes=_string_list('visual_notes', data.get('visual_notes', [])),
            energy_mapping=_string_list('energy_mapping', data.get('energy_mapping', [])),
            audio_feature_mapping=_string_list('audio_feature_mapping', data.get('audio_feature_mapping', [])),
            implementation_notes=_string_list('implementation_notes', data.get('implementation_notes', [])),
            output_contract=OutputContractSpec.from_dict(output_contract),
            function_code=_clean_string(data.get('function_code')),
        )
        spec.validate()
        return spec

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'user_request': self.user_request,
            'summary': self.summary,
            'board': self.board.to_dict(),
            'timing': self.timing.to_dict(),
            'visual_notes': list(self.visual_notes),
            'energy_mapping': list(self.energy_mapping),
            'audio_feature_mapping': list(self.audio_feature_mapping),
            'implementation_notes': list(self.implementation_notes),
            'output_contract': self.output_contract.to_dict(),
            'function_code': self.function_code,
        }

    def validate(self) -> None:
        _require_non_empty('name', self.name)
        _require_non_empty('user_request', self.user_request)
        _require_non_empty('summary', self.summary)
        _require_exact('board.width', self.board.width, EXPECTED_WIDTH)
        _require_exact('board.height', self.board.height, EXPECTED_HEIGHT)
        _require_exact('board.pixel_count', self.board.pixel_count, EXPECTED_PIXEL_COUNT)
        _require_exact('board.coordinate_order', self.board.coordinate_order, STANDARD_COORDINATE_ORDER)
        _require_exact('timing.frame_interval_ms', self.timing.frame_interval_ms, EXPECTED_INTERVAL_MS)
        self.timing.input_parameter.validate()
        _require_string_items('visual_notes', self.visual_notes, minimum=1)
        _require_string_items('energy_mapping', self.energy_mapping, minimum=1)
        _require_string_items('audio_feature_mapping', self.audio_feature_mapping, minimum=5)
        _require_string_items('implementation_notes', self.implementation_notes, minimum=1)
        _require_exact('output_contract.language', self.output_contract.language.lower(), STANDARD_LANGUAGE)
        _require_exact('output_contract.function_name', self.output_contract.function_name, STANDARD_FUNCTION_NAME)
        _require_exact('output_contract.signature', self.output_contract.signature, STANDARD_SIGNATURE)
        _require_exact('output_contract.pixel_order', self.output_contract.pixel_order, STANDARD_PIXEL_ORDER)
        if '[r, g, b]' not in self.output_contract.return_type:
            raise ValueError('output_contract.return_type must describe [r, g, b] pixels')
        _require_non_empty('function_code', self.function_code)
        if STANDARD_FUNCTION_NAME not in self.function_code:
            raise ValueError('function_code must contain renderFrame')
        if STANDARD_INPUT_NAME not in self.function_code:
            raise ValueError('function_code must contain audio')
        for feature_name in STANDARD_AUDIO_FEATURE_NAMES:
            if feature_name not in self.function_code:
                raise ValueError(
                    'function_code must reference audio feature {0!r}'.format(feature_name)
                )


def build_spec_from_design(design: SemanticDesign, function_code: str) -> LedAnimationSpec:
    spec = LedAnimationSpec(
        name=design.name,
        user_request=design.user_request,
        summary=design.summary,
        board=BoardSpec.standard(),
        timing=TimingSpec.standard(),
        visual_notes=design.build_visual_notes(),
        energy_mapping=design.energy_mapping.to_spec_lines(),
        audio_feature_mapping=design.audio_feature_mapping.to_spec_lines(),
        implementation_notes=design.build_implementation_notes(),
        output_contract=OutputContractSpec.standard_render_frame(),
        function_code=_clean_string(function_code),
    )
    spec.validate()
    return spec


def build_audio_feature_guidance_lines(prefix: str = '- ') -> list[str]:
    return [
        '{0}{1}: {2}'.format(prefix, feature_name, description)
        for feature_name, description in STANDARD_AUDIO_FEATURE_GUIDANCE
    ]


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


def _require_exact(name: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise ValueError('{0} must be {1!r}, got {2!r}'.format(name, expected, actual))


def _require_string_items(name: str, items: Sequence[str], *, minimum: int) -> None:
    if len(items) < minimum:
        raise ValueError('{0} must contain at least {1} items'.format(name, minimum))
    if any(not item for item in items):
        raise ValueError('{0} must not contain empty items'.format(name))


__all__ = [
    'STANDARD_AUDIO_FEATURE_GUIDANCE',
    'AudioFeatureRoleMapping',
    'BoardSpec',
    'EXPECTED_HEIGHT',
    'EXPECTED_INTERVAL_MS',
    'EXPECTED_PIXEL_COUNT',
    'EXPECTED_WIDTH',
    'EnergyStageMapping',
    'InputFeatureSpec',
    'InputParameterSpec',
    'LedAnimationSpec',
    'OutputContractSpec',
    'SemanticDesign',
    'STANDARD_AUDIO_FEATURE_NAMES',
    'STANDARD_FUNCTION_NAME',
    'TimingSpec',
    'build_audio_feature_guidance_lines',
    'build_spec_from_design',
]
