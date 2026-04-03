from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from backend.app.cloud.service.led.families import (
    DEFAULT_RENDER_STRATEGY,
    DEFAULT_SUBJECT_FAMILY,
    DEFAULT_SYMMETRY_MODE,
    DEFAULT_TOPOLOGY,
    SUPPORTED_RENDER_STRATEGIES,
    SUPPORTED_SUBJECT_FAMILIES,
    SUPPORTED_SYMMETRY_MODES,
    SUPPORTED_TOPOLOGIES,
    default_canonical_view,
    default_shape_anchors,
)


EXPECTED_WIDTH = 29
EXPECTED_HEIGHT = 16
EXPECTED_INTERVAL_MS = 30
EXPECTED_PIXEL_COUNT = EXPECTED_WIDTH * EXPECTED_HEIGHT

STANDARD_FUNCTION_NAME = 'renderFrame'
STANDARD_INPUT_NAME = 'audio'
STANDARD_LANGUAGE = 'javascript'
STANDARD_SIGNATURE = 'function renderFrame(audio)'
STANDARD_PIXEL_ORDER = 'frame[row][column]'
STANDARD_COORDINATE_ORDER = 'row-major'
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
ALLOWED_COMPLEXITY_LEVELS = ('minimal', 'moderate', 'dense')
DEFAULT_COMPLEXITY = 'moderate'
RENDER_FUNCTION_PATTERN = re.compile(r'\brenderFrame\s*\(\s*audio\s*\)')


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
        if actual_feature_names != list(STANDARD_AUDIO_FEATURE_NAMES):
            raise ValueError(
                'timing.input_parameter.features must be ordered as {0!r}'.format(
                    list(STANDARD_AUDIO_FEATURE_NAMES)
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
            return_type='{0} rows x {1} columns of [r, g, b]'.format(
                EXPECTED_HEIGHT,
                EXPECTED_WIDTH,
            ),
            pixel_order=STANDARD_PIXEL_ORDER,
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
class LayoutConstraints:
    subject_min_pixels: int
    subject_max_pixels: int
    supporting_max_pixels: int
    background_max_pixels: int
    bright_max_pixels: int
    max_centroid_shift: int
    stable_regions: list[str]
    reactive_regions: list[str]

    @classmethod
    def default(cls) -> 'LayoutConstraints':
        return cls(
            subject_min_pixels=36,
            subject_max_pixels=148,
            supporting_max_pixels=56,
            background_max_pixels=18,
            bright_max_pixels=88,
            max_centroid_shift=4,
            stable_regions=[
                'Main subject silhouette stays readable and spatially anchored.',
                'Core interior or structural layer remains visible across energy changes.',
            ],
            reactive_regions=[
                'Motion accents stay localized to secondary edges, tips, or internal deformation zones.',
            ],
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'LayoutConstraints':
        if not isinstance(data, dict):
            raise ValueError('layout_constraints must be an object')
        return cls(
            subject_min_pixels=int(data.get('subject_min_pixels', 0)),
            subject_max_pixels=int(data.get('subject_max_pixels', 0)),
            supporting_max_pixels=int(data.get('supporting_max_pixels', 0)),
            background_max_pixels=int(data.get('background_max_pixels', 0)),
            bright_max_pixels=int(data.get('bright_max_pixels', 0)),
            max_centroid_shift=int(data.get('max_centroid_shift', 0)),
            stable_regions=_string_list(
                'layout_constraints.stable_regions',
                data.get('stable_regions', []),
            ),
            reactive_regions=_string_list(
                'layout_constraints.reactive_regions',
                data.get('reactive_regions', []),
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'subject_min_pixels': self.subject_min_pixels,
            'subject_max_pixels': self.subject_max_pixels,
            'supporting_max_pixels': self.supporting_max_pixels,
            'background_max_pixels': self.background_max_pixels,
            'bright_max_pixels': self.bright_max_pixels,
            'max_centroid_shift': self.max_centroid_shift,
            'stable_regions': list(self.stable_regions),
            'reactive_regions': list(self.reactive_regions),
        }

    def to_spec_lines(self) -> list[str]:
        return [
            'Active subject pixels: {0}-{1}'.format(self.subject_min_pixels, self.subject_max_pixels),
            'Supporting detail pixels: <= {0}'.format(self.supporting_max_pixels),
            'Background reactive pixels: <= {0}'.format(self.background_max_pixels),
            'Bright pixels per frame: <= {0}'.format(self.bright_max_pixels),
            'Stable regions: {0}'.format('; '.join(self.stable_regions)),
            'Reactive regions: {0}'.format('; '.join(self.reactive_regions)),
            'Max centroid shift between energy stages: <= {0}'.format(self.max_centroid_shift),
        ]

    def validate(self) -> None:
        _require_int_range(
            'layout_constraints.subject_min_pixels',
            self.subject_min_pixels,
            minimum=1,
            maximum=EXPECTED_PIXEL_COUNT,
        )
        _require_int_range(
            'layout_constraints.subject_max_pixels',
            self.subject_max_pixels,
            minimum=self.subject_min_pixels,
            maximum=EXPECTED_PIXEL_COUNT,
        )
        _require_int_range(
            'layout_constraints.supporting_max_pixels',
            self.supporting_max_pixels,
            minimum=0,
            maximum=EXPECTED_PIXEL_COUNT,
        )
        _require_int_range(
            'layout_constraints.background_max_pixels',
            self.background_max_pixels,
            minimum=0,
            maximum=EXPECTED_PIXEL_COUNT,
        )
        _require_int_range(
            'layout_constraints.bright_max_pixels',
            self.bright_max_pixels,
            minimum=1,
            maximum=EXPECTED_PIXEL_COUNT,
        )
        _require_int_range(
            'layout_constraints.max_centroid_shift',
            self.max_centroid_shift,
            minimum=0,
            maximum=max(EXPECTED_WIDTH, EXPECTED_HEIGHT),
        )
        _require_string_items('layout_constraints.stable_regions', self.stable_regions, minimum=2)
        _require_string_items('layout_constraints.reactive_regions', self.reactive_regions, minimum=1)


@dataclass(frozen=True)
class SemanticDesign:
    name: str
    raw_user_request: str
    expanded_request: str
    summary: str
    subject_family: str
    topology: str
    render_strategy: str
    symmetry_mode: str
    canonical_view: str
    shape_anchors: list[str]
    complexity: str
    subject: str
    color_palette: list[str]
    composition: list[str]
    motion_rules: list[str]
    energy_mapping: EnergyStageMapping
    audio_feature_mapping: AudioFeatureRoleMapping
    layout_constraints: LayoutConstraints
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

        subject = _clean_string(data.get('subject'))
        subject_family = _normalize_supported_name(
            'subject_family',
            data.get('subject_family'),
            SUPPORTED_SUBJECT_FAMILIES,
            DEFAULT_SUBJECT_FAMILY,
        )
        topology = _normalize_supported_name(
            'topology',
            data.get('topology'),
            SUPPORTED_TOPOLOGIES,
            DEFAULT_TOPOLOGY,
        )
        render_strategy = _normalize_supported_name(
            'render_strategy',
            data.get('render_strategy'),
            SUPPORTED_RENDER_STRATEGIES,
            DEFAULT_RENDER_STRATEGY,
        )
        symmetry_mode = _normalize_supported_name(
            'symmetry_mode',
            data.get('symmetry_mode'),
            SUPPORTED_SYMMETRY_MODES,
            DEFAULT_SYMMETRY_MODE,
        )

        layout_constraints = data.get('layout_constraints')

        design = cls(
            name=_clean_string(data.get('name')) or 'led-animation',
            raw_user_request=_clean_string(data.get('raw_user_request') or data.get('user_request')),
            expanded_request=_clean_string(
                data.get('expanded_request') or data.get('raw_user_request') or data.get('user_request')
            ),
            summary=_clean_string(data.get('summary')),
            subject_family=subject_family,
            topology=topology,
            render_strategy=render_strategy,
            symmetry_mode=symmetry_mode,
            canonical_view=_normalize_canonical_view(
                data.get('canonical_view'),
                subject_family=subject_family,
            ),
            shape_anchors=_normalize_shape_anchors(
                data.get('shape_anchors'),
                subject_family=subject_family,
                subject=subject,
            ),
            complexity=_normalize_complexity(data.get('complexity')),
            subject=subject,
            color_palette=_string_list('color_palette', data.get('color_palette', [])),
            composition=_string_list('composition', data.get('composition', [])),
            motion_rules=_string_list('motion_rules', data.get('motion_rules', [])),
            energy_mapping=EnergyStageMapping.from_dict(energy_mapping),
            audio_feature_mapping=AudioFeatureRoleMapping.from_dict(audio_feature_mapping),
            layout_constraints=(
                LayoutConstraints.from_dict(layout_constraints)
                if isinstance(layout_constraints, dict)
                else LayoutConstraints.default()
            ),
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
            'subject_family': self.subject_family,
            'topology': self.topology,
            'render_strategy': self.render_strategy,
            'symmetry_mode': self.symmetry_mode,
            'canonical_view': self.canonical_view,
            'shape_anchors': list(self.shape_anchors),
            'complexity': self.complexity,
            'subject': self.subject,
            'color_palette': list(self.color_palette),
            'composition': list(self.composition),
            'motion_rules': list(self.motion_rules),
            'energy_mapping': self.energy_mapping.to_dict(),
            'audio_feature_mapping': self.audio_feature_mapping.to_dict(),
            'layout_constraints': self.layout_constraints.to_dict(),
            'avoid_list': list(self.avoid_list),
            'implementation_hints': list(self.implementation_hints),
        }

    def build_visual_notes(self) -> list[str]:
        return (
            [
                'Family: {0}'.format(self.subject_family),
                'Topology: {0}'.format(self.topology),
                'Render strategy: {0}'.format(self.render_strategy),
                'Symmetry: {0}'.format(self.symmetry_mode),
                'View: {0}'.format(self.canonical_view),
                'Anchors: {0}'.format('; '.join(self.shape_anchors)),
                'Subject: {0}'.format(self.subject),
            ]
            + ['Color: {0}'.format(item) for item in self.color_palette]
            + ['Composition: {0}'.format(item) for item in self.composition]
            + ['Motion: {0}'.format(item) for item in self.motion_rules]
        )

    def build_implementation_notes(self) -> list[str]:
        notes = [
            'Family: {0}'.format(self.subject_family),
            'Topology: {0}'.format(self.topology),
            'Render strategy: {0}'.format(self.render_strategy),
            'Symmetry: {0}'.format(self.symmetry_mode),
            'View: {0}'.format(self.canonical_view),
            'Complexity: {0}'.format(self.complexity),
            'Anchors: {0}'.format('; '.join(self.shape_anchors)),
        ]
        notes.extend('Hint: {0}'.format(item) for item in self.implementation_hints)
        notes.extend('Layout: {0}'.format(item) for item in self.layout_constraints.to_spec_lines())
        if self.avoid_list:
            notes.append('Avoid: {0}'.format('; '.join(self.avoid_list)))
        return notes

    def validate(self) -> None:
        _require_non_empty('name', self.name)
        _require_non_empty('raw_user_request', self.raw_user_request)
        _require_non_empty('expanded_request', self.expanded_request)
        _require_non_empty('summary', self.summary)
        _require_choice('subject_family', self.subject_family, SUPPORTED_SUBJECT_FAMILIES)
        _require_choice('topology', self.topology, SUPPORTED_TOPOLOGIES)
        _require_choice('render_strategy', self.render_strategy, SUPPORTED_RENDER_STRATEGIES)
        _require_choice('symmetry_mode', self.symmetry_mode, SUPPORTED_SYMMETRY_MODES)
        _require_non_empty('canonical_view', self.canonical_view)
        _require_string_items('shape_anchors', self.shape_anchors, minimum=2)
        _require_choice('complexity', self.complexity, ALLOWED_COMPLEXITY_LEVELS)
        _require_non_empty('subject', self.subject)
        _require_string_items('color_palette', self.color_palette, minimum=2)
        _require_string_items('composition', self.composition, minimum=2)
        _require_string_items('motion_rules', self.motion_rules, minimum=3)
        self.energy_mapping.validate()
        self.audio_feature_mapping.validate()
        self.layout_constraints.validate()
        _require_string_items('avoid_list', self.avoid_list, minimum=2)
        _require_string_items('implementation_hints', self.implementation_hints, minimum=3)


@dataclass(frozen=True)
class LedAnimationSpec:
    name: str
    raw_user_request: str
    expanded_request: str
    summary: str
    subject_family: str
    topology: str
    render_strategy: str
    symmetry_mode: str
    canonical_view: str
    shape_anchors: list[str]
    complexity: str
    board: BoardSpec
    timing: TimingSpec
    visual_notes: list[str]
    energy_mapping: list[str]
    audio_feature_mapping: list[str]
    layout_constraints: LayoutConstraints
    implementation_notes: list[str]
    output_contract: OutputContractSpec
    function_code: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'raw_user_request': self.raw_user_request,
            'expanded_request': self.expanded_request,
            'summary': self.summary,
            'subject_family': self.subject_family,
            'topology': self.topology,
            'render_strategy': self.render_strategy,
            'symmetry_mode': self.symmetry_mode,
            'canonical_view': self.canonical_view,
            'shape_anchors': list(self.shape_anchors),
            'complexity': self.complexity,
            'board': self.board.to_dict(),
            'timing': self.timing.to_dict(),
            'visual_notes': list(self.visual_notes),
            'energy_mapping': list(self.energy_mapping),
            'audio_feature_mapping': list(self.audio_feature_mapping),
            'layout_constraints': self.layout_constraints.to_dict(),
            'implementation_notes': list(self.implementation_notes),
            'output_contract': self.output_contract.to_dict(),
            'function_code': self.function_code,
        }

    def validate(self) -> None:
        _require_non_empty('name', self.name)
        _require_non_empty('raw_user_request', self.raw_user_request)
        _require_non_empty('expanded_request', self.expanded_request)
        _require_non_empty('summary', self.summary)
        _require_choice('subject_family', self.subject_family, SUPPORTED_SUBJECT_FAMILIES)
        _require_choice('topology', self.topology, SUPPORTED_TOPOLOGIES)
        _require_choice('render_strategy', self.render_strategy, SUPPORTED_RENDER_STRATEGIES)
        _require_choice('symmetry_mode', self.symmetry_mode, SUPPORTED_SYMMETRY_MODES)
        _require_non_empty('canonical_view', self.canonical_view)
        _require_string_items('shape_anchors', self.shape_anchors, minimum=2)
        _require_choice('complexity', self.complexity, ALLOWED_COMPLEXITY_LEVELS)
        _require_exact('board.width', self.board.width, EXPECTED_WIDTH)
        _require_exact('board.height', self.board.height, EXPECTED_HEIGHT)
        _require_exact('board.pixel_count', self.board.pixel_count, EXPECTED_PIXEL_COUNT)
        _require_exact('board.coordinate_order', self.board.coordinate_order, STANDARD_COORDINATE_ORDER)
        _require_exact('timing.frame_interval_ms', self.timing.frame_interval_ms, EXPECTED_INTERVAL_MS)
        self.timing.input_parameter.validate()
        _require_string_items('visual_notes', self.visual_notes, minimum=1)
        _require_string_items('energy_mapping', self.energy_mapping, minimum=1)
        _require_string_items('audio_feature_mapping', self.audio_feature_mapping, minimum=5)
        self.layout_constraints.validate()
        _require_string_items('implementation_notes', self.implementation_notes, minimum=1)
        _require_exact('output_contract.language', self.output_contract.language.lower(), STANDARD_LANGUAGE)
        _require_exact('output_contract.function_name', self.output_contract.function_name, STANDARD_FUNCTION_NAME)
        _require_exact('output_contract.signature', self.output_contract.signature, STANDARD_SIGNATURE)
        _require_exact('output_contract.pixel_order', self.output_contract.pixel_order, STANDARD_PIXEL_ORDER)
        if '[r, g, b]' not in self.output_contract.return_type:
            raise ValueError('output_contract.return_type must describe [r, g, b] pixels')
        validate_function_code(self.function_code)


def build_audio_feature_guidance_lines(prefix: str = '- ') -> list[str]:
    return [
        '{0}{1}: {2}'.format(prefix, feature_name, description)
        for feature_name, description in STANDARD_AUDIO_FEATURE_GUIDANCE
    ]


def build_spec_from_design(design: SemanticDesign, function_code: str) -> LedAnimationSpec:
    spec = LedAnimationSpec(
        name=design.name,
        raw_user_request=design.raw_user_request,
        expanded_request=design.expanded_request,
        summary=design.summary,
        subject_family=design.subject_family,
        topology=design.topology,
        render_strategy=design.render_strategy,
        symmetry_mode=design.symmetry_mode,
        canonical_view=design.canonical_view,
        shape_anchors=list(design.shape_anchors),
        complexity=design.complexity,
        board=BoardSpec.standard(),
        timing=TimingSpec.standard(),
        visual_notes=design.build_visual_notes(),
        energy_mapping=design.energy_mapping.to_spec_lines(),
        audio_feature_mapping=design.audio_feature_mapping.to_spec_lines(),
        layout_constraints=design.layout_constraints,
        implementation_notes=design.build_implementation_notes(),
        output_contract=OutputContractSpec.standard_render_frame(),
        function_code=validate_function_code(function_code),
    )
    spec.validate()
    return spec


def build_animation_spec(design: SemanticDesign, function_code: str) -> dict[str, Any]:
    return build_spec_from_design(design, function_code).to_dict()


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


def _require_exact(name: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise ValueError('{0} must be {1!r}, got {2!r}'.format(name, expected, actual))


def _require_choice(name: str, value: str, choices: Sequence[str]) -> None:
    if value not in choices:
        raise ValueError('{0} must be one of {1!r}, got {2!r}'.format(name, list(choices), value))


def _require_int_range(name: str, value: int, *, minimum: int, maximum: int) -> None:
    if value < minimum or value > maximum:
        raise ValueError(
            '{0} must be between {1} and {2}, got {3}'.format(
                name,
                minimum,
                maximum,
                value,
            )
        )


def _require_string_items(name: str, items: Sequence[str], *, minimum: int) -> None:
    if len(items) < minimum:
        raise ValueError('{0} must contain at least {1} items'.format(name, minimum))
    if any(not item for item in items):
        raise ValueError('{0} must not contain empty items'.format(name))


def _normalize_supported_name(
    name: str,
    value: Any,
    choices: Sequence[str],
    default: str,
) -> str:
    candidate = _clean_string(value).lower().replace('-', '_').replace(' ', '_')
    if candidate in choices:
        return candidate
    if not candidate:
        return default
    raise ValueError('{0} must be one of {1!r}, got {2!r}'.format(name, list(choices), value))


def _normalize_canonical_view(
    value: Any,
    *,
    subject_family: str,
) -> str:
    candidate = _clean_string(value)
    if candidate:
        return candidate
    return default_canonical_view(subject_family)


def _normalize_shape_anchors(
    value: Any,
    *,
    subject_family: str,
    subject: str,
) -> list[str]:
    if isinstance(value, list):
        anchors = [str(item).strip() for item in value if str(item).strip()]
        if len(anchors) >= 2:
            return anchors
    return default_shape_anchors(subject_family, subject=subject)


def _normalize_complexity(value: Any) -> str:
    candidate = _clean_string(value).lower()
    if candidate in ALLOWED_COMPLEXITY_LEVELS:
        return candidate
    if not candidate:
        return DEFAULT_COMPLEXITY
    raise ValueError(
        'complexity must be one of {0!r}, got {1!r}'.format(
            list(ALLOWED_COMPLEXITY_LEVELS),
            value,
        )
    )


__all__ = [
    'ALLOWED_COMPLEXITY_LEVELS',
    'EXPECTED_HEIGHT',
    'EXPECTED_INTERVAL_MS',
    'EXPECTED_WIDTH',
    'BoardSpec',
    'InputFeatureSpec',
    'InputParameterSpec',
    'LayoutConstraints',
    'LedAnimationSpec',
    'OutputContractSpec',
    'SUPPORTED_RENDER_STRATEGIES',
    'SUPPORTED_SUBJECT_FAMILIES',
    'SUPPORTED_SYMMETRY_MODES',
    'SUPPORTED_TOPOLOGIES',
    'STANDARD_AUDIO_FEATURE_GUIDANCE',
    'STANDARD_AUDIO_FEATURE_NAMES',
    'AudioFeatureRoleMapping',
    'EnergyStageMapping',
    'SemanticDesign',
    'build_animation_spec',
    'build_audio_feature_guidance_lines',
    'build_spec_from_design',
    'validate_function_code',
]
