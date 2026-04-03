from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class RoutingOptionDefinition:
    name: str
    summary: str
    design_hint: str
    code_prompt_lines: tuple[str, ...]


@dataclass(frozen=True)
class SubjectFamilyDefinition:
    name: str
    summary: str
    design_hint: str
    code_prompt_lines: tuple[str, ...]
    default_view: str
    default_shape_anchors: tuple[str, ...]


FAMILY_DEFINITIONS: dict[str, SubjectFamilyDefinition] = {
    'abstract_motif': SubjectFamilyDefinition(
        name='abstract_motif',
        summary='centered abstract motif with repeatable contour grammar',
        design_hint='use one dominant abstract motif with a repeatable contour, restrained support detail, and a stable visual center',
        code_prompt_lines=(
            'Keep one dominant motif stable enough to read before adding reactive texture.',
            'Use contour bands or layered masks instead of uniform full-screen noise.',
            'Let audio reshape the motif edges or inner rhythm without dissolving its center.',
        ),
        default_view='centered iconic motif view',
        default_shape_anchors=('dominant center mass', 'secondary contour band'),
    ),
    'animal_profile': SubjectFamilyDefinition(
        name='animal_profile',
        summary='single recognizable animal silhouette, usually profile view',
        design_hint='use one recognizable animal silhouette in profile and keep only one or two supporting structural accents',
        code_prompt_lines=(
            'Preserve the animal profile before adding any reactive accents.',
            'Keep head, torso, and one tail or leg accent legible at all times.',
            'Localize motion to breathing, edge shimmer, or one secondary accent zone.',
        ),
        default_view='side profile silhouette',
        default_shape_anchors=('head silhouette', 'torso mass', 'leg or tail accent'),
    ),
    'architectural_silhouette': SubjectFamilyDefinition(
        name='architectural_silhouette',
        summary='building, skyline, or tower silhouette',
        design_hint='compress the scene into a clean skyline or tower silhouette with one clear roofline and a quiet base band',
        code_prompt_lines=(
            'Preserve a stable skyline or tower silhouette across all energy levels.',
            'Attach reactive detail to windows, beacon lights, or edge glints instead of moving the whole structure.',
            'Keep the base and roofline readable before adding atmosphere.',
        ),
        default_view='straight-on skyline silhouette',
        default_shape_anchors=('roofline silhouette', 'central tower mass', 'base skyline band'),
    ),
    'banded_flow': SubjectFamilyDefinition(
        name='banded_flow',
        summary='continuous banded flow such as wave, river, or lava sheet',
        design_hint='choose one continuous banded subject such as wave, river, lava sheet, or cloud belt and preserve horizontal continuity with one clear crest',
        code_prompt_lines=(
            'Use horizontally continuous layered bands as the primary geometry; do not fragment the body into detached particles.',
            'Keep one readable crest, lip, or leading edge attached to the main body at all times.',
            'Concentrate reactive detail near the contour while the heavier base mass stays stable.',
        ),
        default_view='side cross-section flow view',
        default_shape_anchors=('main crest arc', 'stable flow body band', 'attached edge highlight'),
    ),
    'face_mask': SubjectFamilyDefinition(
        name='face_mask',
        summary='front-facing face or mask with a few anchored features',
        design_hint='use a front-facing face or mask with a stable outline and only a few anchored features such as eyes and mouth',
        code_prompt_lines=(
            'Keep the head outline and eye region stable before adding reactive lighting.',
            'Confine motion to eyes, mouth, markings, or aura accents instead of shifting the whole face.',
            'Avoid symmetry-breaking distortions that make the face unreadable.',
        ),
        default_view='front mask view',
        default_shape_anchors=('head outline', 'eye region', 'mouth or chin anchor'),
    ),
    'flower_bloom': SubjectFamilyDefinition(
        name='flower_bloom',
        summary='single bloom-based flower subject such as rose, lotus, or daisy',
        design_hint='choose one dominant bloom head plus a small stem base and prioritize the flower-specific silhouette, core structure, and iconic low-resolution view',
        code_prompt_lines=(
            'Make the bloom head dominate the active pixels and keep any stem or leaf accents clearly subordinate.',
            'Represent petals as readable layers, lobes, cups, spokes, or overlaps; avoid a uniform circular glow blob.',
            'Reserve the strongest motion for core breathing and edge highlights without losing the flower silhouette.',
        ),
        default_view='side-view half-bloom',
        default_shape_anchors=('dominant bloom head', 'inner petal core', 'short stem base'),
    ),
    'object_icon': SubjectFamilyDefinition(
        name='object_icon',
        summary='single simplified object icon with a clear silhouette',
        design_hint='compress the request into one dominant object silhouette plus one or two small structural accents',
        code_prompt_lines=(
            'Preserve the canonical view and anchor shapes as the minimum readable skeleton before adding secondary motion.',
            'Favor one dominant silhouette plus one or two subordinate accents instead of many equal details.',
            'When simplification is necessary, remove support detail before weakening the main anchor shapes.',
        ),
        default_view='iconic simplified object view',
        default_shape_anchors=('dominant object silhouette', 'secondary structural accent'),
    ),
    'stacked_icon': SubjectFamilyDefinition(
        name='stacked_icon',
        summary='tiered or vertically stacked icon such as cake or layered lantern',
        design_hint='use tiered or vertically stacked iconic objects and preserve the width hierarchy from bottom to top',
        code_prompt_lines=(
            'Preserve a clear bottom-to-top width hierarchy so the stacked silhouette reads immediately.',
            'Keep the main body stable and attach reactive accents to the upper tier or candle/flame zone.',
            'Avoid melting or slumping the tiers into one rounded mass.',
        ),
        default_view='front stacked icon view',
        default_shape_anchors=('wide lower tier', 'smaller upper tier', 'vertical candle tips'),
    ),
    'symbol_mark': SubjectFamilyDefinition(
        name='symbol_mark',
        summary='symbol, punctuation mark, logo-like sign, or emblem',
        design_hint='keep one centered symbol or mark with a clean contour and very restrained support detail',
        code_prompt_lines=(
            'Keep the main symbol contour stable and centered.',
            'Use reactive accents as edge glints, interior fills, or detached mark highlights.',
            'Do not let background activity overpower the symbol body.',
        ),
        default_view='centered symbol mark view',
        default_shape_anchors=('main symbol body', 'accent mark or detached element'),
    ),
    'vehicle_side': SubjectFamilyDefinition(
        name='vehicle_side',
        summary='side-view vehicle silhouette with minimal structural accents',
        design_hint='use a side-view vehicle silhouette and keep only the shell, wheel base, and one front or tail accent',
        code_prompt_lines=(
            'Preserve the side silhouette before adding lighting or trail effects.',
            'Keep wheels or the underside as a stable anchor zone.',
            'Localize reactive detail to windows, exhaust, headlights, or trim lines.',
        ),
        default_view='side silhouette view',
        default_shape_anchors=('main body shell', 'wheel or underside anchor', 'front or tail accent'),
    ),
}

TOPOLOGY_DEFINITIONS: dict[str, RoutingOptionDefinition] = {
    'single_contour': RoutingOptionDefinition(
        name='single_contour',
        summary='one dominant closed contour with minimal detached support',
        design_hint='compress the subject into one primary contour or silhouette with at most one small detached accent',
        code_prompt_lines=(
            'Build one primary silhouette mask before adding interior detail.',
            'Keep detached accents rare and clearly subordinate to the main body.',
            'Use interior detail only when it reinforces the dominant contour.',
        ),
    ),
    'radial_core': RoutingOptionDefinition(
        name='radial_core',
        summary='central core with petals, spokes, rays, or a surrounding ring',
        design_hint='use a readable center plus evenly staged surrounding lobes, spokes, or petals that orbit that center',
        code_prompt_lines=(
            'Keep the central core readable before adding outer repeated elements.',
            'Group repeated outer elements into coherent sectors instead of noisy independent flicker.',
            'Preserve radial balance even when outer segments react strongly.',
        ),
    ),
    'layered_overlap': RoutingOptionDefinition(
        name='layered_overlap',
        summary='overlapping shells or lobes wrapped around an inner core',
        design_hint='use foreground, mid-layer, and inner-core overlaps so recognizability comes from occlusion and layered depth instead of flat fill',
        code_prompt_lines=(
            'Build front, mid, and inner layers explicitly so overlaps create depth.',
            'Use shadow gaps, notches, or rim highlights to separate overlapping forms.',
            'Keep the inner core readable without rotating or warping the entire subject.',
        ),
    ),
    'horizontal_band': RoutingOptionDefinition(
        name='horizontal_band',
        summary='continuous left-to-right band with one readable leading edge or crest',
        design_hint='organize the subject as attached horizontal bands with one clear lip, crest, or leading contour',
        code_prompt_lines=(
            'Keep the main band attached and continuous across the frame.',
            'Concentrate energy near the leading edge while the heavier body stays stable.',
            'Avoid breaking the flow into isolated particles or disconnected blobs.',
        ),
    ),
    'vertical_stack': RoutingOptionDefinition(
        name='vertical_stack',
        summary='bottom-to-top stacked tiers or repeated masses',
        design_hint='preserve the width hierarchy and stacking order from the base upward so the subject reads as tiered',
        code_prompt_lines=(
            'Preserve the stacked order and width hierarchy from bottom to top.',
            'Attach reactive detail to the upper tiers or tip zone rather than destabilizing the base.',
            'Avoid merging the tiers into one rounded undifferentiated mass.',
        ),
    ),
    'bilateral_face': RoutingOptionDefinition(
        name='bilateral_face',
        summary='front-facing mirrored structure with anchored left and right features',
        design_hint='anchor the design with mirrored left and right structural zones around a stable centerline',
        code_prompt_lines=(
            'Keep the centerline stable and the left/right anchor regions legible.',
            'Use asymmetry only as a small accent, not enough to break face readability.',
            'Confine motion to feature zones instead of shifting the entire mask or face.',
        ),
    ),
    'side_profile': RoutingOptionDefinition(
        name='side_profile',
        summary='left-right directional profile with front and back distinction',
        design_hint='preserve the front-back reading of the silhouette so the subject clearly points or moves in one direction',
        code_prompt_lines=(
            'Keep the front and back of the profile clearly distinct.',
            'Maintain one readable head or nose zone and one readable tail or rear zone.',
            'Use motion along the body or edge accents without erasing the directional silhouette.',
        ),
    ),
    'grounded_silhouette': RoutingOptionDefinition(
        name='grounded_silhouette',
        summary='bottom-anchored silhouette rising from a stable base band',
        design_hint='attach the main form to a stable lower base so the subject rises upward from a clear ground or skyline line',
        code_prompt_lines=(
            'Keep the lower base band stable and let detail rise from it.',
            'Preserve the upper silhouette before adding internal texture or lighting.',
            'Use height variation and a readable roofline or tip sequence to define the subject.',
        ),
    ),
}

RENDER_STRATEGY_DEFINITIONS: dict[str, RoutingOptionDefinition] = {
    'bold_silhouette': RoutingOptionDefinition(
        name='bold_silhouette',
        summary='large filled silhouette with restrained internal accents',
        design_hint='favor a strong readable fill shape first, then add only a few internal accents or highlights',
        code_prompt_lines=(
            'Prioritize the filled silhouette over internal decoration.',
            'Keep internal detail sparse and high-value so it sharpens the read instead of cluttering it.',
            'Use highlight or shadow accents only where they reinforce the main shape.',
        ),
    ),
    'segmented_repeaters': RoutingOptionDefinition(
        name='segmented_repeaters',
        summary='subject built from repeated readable modules along a shared skeleton',
        design_hint='use repeated modules such as petals, rays, windows, or fins, but keep them tied to one stable underlying skeleton',
        code_prompt_lines=(
            'Use repeated modules only when they stay tied to a stable centerline, ring, or body.',
            'Animate repeated segments in grouped sectors rather than pure per-segment randomness.',
            'Keep module count low enough that each repeated shape still reads on a 29x16 board.',
        ),
    ),
    'nested_contours': RoutingOptionDefinition(
        name='nested_contours',
        summary='concentric or nested contour bands with readable spacing',
        design_hint='build the subject from nested contour bands or rings that preserve separation between outer shell, mid layer, and core',
        code_prompt_lines=(
            'Use contour spacing and layer thickness to separate outer shell, mid layer, and core.',
            'Keep contour counts small and readable; do not over-fragment them.',
            'Let audio reshape contour spacing or thickness without destroying their order.',
        ),
    ),
    'overlapping_shells': RoutingOptionDefinition(
        name='overlapping_shells',
        summary='overlapping masks or lobes with occlusion, rim light, and shadow gaps',
        design_hint='represent the subject through overlapping shells, cups, or lobes so depth comes from occlusion and shadow separation',
        code_prompt_lines=(
            'Build overlapping masks that partially occlude one another.',
            'Use rim highlights and shadow gaps to keep each shell separate.',
            'Avoid collapsing layered forms into one blended blob with uniform fill.',
        ),
    ),
    'banded_layers': RoutingOptionDefinition(
        name='banded_layers',
        summary='stacked directional bands separated by contour or palette ramps',
        design_hint='use attached directional bands with a readable order from foreground contour to background mass',
        code_prompt_lines=(
            'Use attached directional bands rather than detached ribbons.',
            'Keep the leading band edge crisp enough to read before background bands move.',
            'Use palette ramps to separate band depth rather than treating all bands equally.',
        ),
    ),
    'cutout_features': RoutingOptionDefinition(
        name='cutout_features',
        summary='solid body punctuated by interior voids, windows, or feature cutouts',
        design_hint='keep the main body solid and use a few voids, eye holes, windows, or cut lines to define the subject',
        code_prompt_lines=(
            'Keep the main body solid enough that cutouts feel intentional and structural.',
            'Use negative space only for the most recognition-critical interior features.',
            'Do not let interior cutouts exceed the visual weight of the main body.',
        ),
    ),
    'stroked_mark': RoutingOptionDefinition(
        name='stroked_mark',
        summary='stroke-led contour or calligraphic mark with minimal fill',
        design_hint='treat the subject as a contour or mark whose stroke path matters more than filled mass',
        code_prompt_lines=(
            'Preserve the stroke path and turning points before adding glow or fill.',
            'Keep stroke thickness consistent enough that the symbol remains legible.',
            'Use detached accents sparingly so the main mark remains dominant.',
        ),
    ),
}

SYMMETRY_MODE_DEFINITIONS: dict[str, RoutingOptionDefinition] = {
    'radial': RoutingOptionDefinition(
        name='radial',
        summary='balanced around a center with circular or spoke-like organization',
        design_hint='preserve rotational or ring balance around the center so the subject reads as organized around a core',
        code_prompt_lines=(
            'Keep the center as the compositional anchor.',
            'Balance outer accents around the center rather than letting one side dominate accidentally.',
            'Use grouped sector variation instead of breaking the radial read.',
        ),
    ),
    'bilateral': RoutingOptionDefinition(
        name='bilateral',
        summary='mirrored left-right balance around a centerline',
        design_hint='keep left and right sides legible as a pair and use asymmetry only in minor accents',
        code_prompt_lines=(
            'Maintain the centerline and preserve paired left-right anchor zones.',
            'Mirror large-scale structure even if highlights differ slightly.',
            'Avoid drift that makes one half collapse or detach from the other.',
        ),
    ),
    'directional': RoutingOptionDefinition(
        name='directional',
        summary='clear front-back or leading-trailing directionality',
        design_hint='use asymmetric balance that clearly points, flows, or travels in one direction',
        code_prompt_lines=(
            'Preserve the intended leading edge or front-facing side.',
            'Bias trails, highlights, or deformation along the direction of travel.',
            'Avoid re-centering the subject into a symmetric blob that loses direction.',
        ),
    ),
    'soft_asymmetric': RoutingOptionDefinition(
        name='soft_asymmetric',
        summary='balanced overall but intentionally uneven in local structure',
        design_hint='keep the subject stable overall while allowing the local layers or lobes to remain uneven and organic',
        code_prompt_lines=(
            'Keep the total mass stable while allowing local lobes or layers to differ.',
            'Use asymmetry to suggest organic growth or overlap, not chaos.',
            'Keep the dominant silhouette readable even when internal layers are uneven.',
        ),
    ),
    'stacked': RoutingOptionDefinition(
        name='stacked',
        summary='organized primarily by bottom-to-top balance rather than left-right symmetry',
        design_hint='maintain the vertical tier order and treat each layer as supporting the one above it',
        code_prompt_lines=(
            'Preserve the vertical order and make the base feel heavier than the top.',
            'Keep upper tiers smaller or lighter so the stack stays readable.',
            'Use motion that respects gravity and attachment between tiers.',
        ),
    ),
    'freeform': RoutingOptionDefinition(
        name='freeform',
        summary='intentionally irregular contour grammar with one stable center of mass',
        design_hint='allow an irregular contour, but still preserve one stable center of mass and a repeatable internal logic',
        code_prompt_lines=(
            'Keep one stable center of mass even when the contour is irregular.',
            'Use repeatable contour logic so the shape still feels designed, not random.',
            'Let reactive motion deform the form without destroying its core identity.',
        ),
    ),
}

DEFAULT_SUBJECT_FAMILY = 'object_icon'
DEFAULT_TOPOLOGY = 'single_contour'
DEFAULT_RENDER_STRATEGY = 'bold_silhouette'
DEFAULT_SYMMETRY_MODE = 'freeform'

SUPPORTED_SUBJECT_FAMILIES = tuple(FAMILY_DEFINITIONS.keys())
SUPPORTED_TOPOLOGIES = tuple(TOPOLOGY_DEFINITIONS.keys())
SUPPORTED_RENDER_STRATEGIES = tuple(RENDER_STRATEGY_DEFINITIONS.keys())
SUPPORTED_SYMMETRY_MODES = tuple(SYMMETRY_MODE_DEFINITIONS.keys())


def iter_family_definitions() -> Iterable[SubjectFamilyDefinition]:
    return FAMILY_DEFINITIONS.values()


def iter_topology_definitions() -> Iterable[RoutingOptionDefinition]:
    return TOPOLOGY_DEFINITIONS.values()


def iter_render_strategy_definitions() -> Iterable[RoutingOptionDefinition]:
    return RENDER_STRATEGY_DEFINITIONS.values()


def iter_symmetry_mode_definitions() -> Iterable[RoutingOptionDefinition]:
    return SYMMETRY_MODE_DEFINITIONS.values()


def get_subject_family_summary(name: str) -> str:
    family = FAMILY_DEFINITIONS.get(str(name or '').strip())
    if family is None:
        return 'generic simplified low-resolution family'
    return family.summary


def get_topology_summary(name: str) -> str:
    topology = TOPOLOGY_DEFINITIONS.get(str(name or '').strip())
    if topology is None:
        return 'generic dominant-subject pixel topology'
    return topology.summary


def get_render_strategy_summary(name: str) -> str:
    strategy = RENDER_STRATEGY_DEFINITIONS.get(str(name or '').strip())
    if strategy is None:
        return 'generic layered low-resolution construction strategy'
    return strategy.summary


def get_symmetry_mode_summary(name: str) -> str:
    symmetry = SYMMETRY_MODE_DEFINITIONS.get(str(name or '').strip())
    if symmetry is None:
        return 'generic balance mode with one stable center of mass'
    return symmetry.summary


def get_subject_family_design_hint(name: str) -> str:
    family = FAMILY_DEFINITIONS.get(str(name or '').strip())
    if family is None:
        return 'preserve one dominant motif, clear layering, and a stable readable center'
    return family.design_hint


def get_topology_design_hint(name: str) -> str:
    topology = TOPOLOGY_DEFINITIONS.get(str(name or '').strip())
    if topology is None:
        return 'organize the subject around one readable structural skeleton'
    return topology.design_hint


def get_render_strategy_design_hint(name: str) -> str:
    strategy = RENDER_STRATEGY_DEFINITIONS.get(str(name or '').strip())
    if strategy is None:
        return 'build the subject from explicit low-resolution-friendly layers and accents'
    return strategy.design_hint


def get_symmetry_mode_design_hint(name: str) -> str:
    symmetry = SYMMETRY_MODE_DEFINITIONS.get(str(name or '').strip())
    if symmetry is None:
        return 'keep overall balance stable while allowing only controlled asymmetry'
    return symmetry.design_hint


def get_subject_family_code_prompt_lines(name: str) -> tuple[str, ...]:
    family = FAMILY_DEFINITIONS.get(str(name or '').strip()) or FAMILY_DEFINITIONS[DEFAULT_SUBJECT_FAMILY]
    return family.code_prompt_lines


def get_topology_code_prompt_lines(name: str) -> tuple[str, ...]:
    topology = TOPOLOGY_DEFINITIONS.get(str(name or '').strip()) or TOPOLOGY_DEFINITIONS[DEFAULT_TOPOLOGY]
    return topology.code_prompt_lines


def get_render_strategy_code_prompt_lines(name: str) -> tuple[str, ...]:
    strategy = RENDER_STRATEGY_DEFINITIONS.get(str(name or '').strip()) or RENDER_STRATEGY_DEFINITIONS[DEFAULT_RENDER_STRATEGY]
    return strategy.code_prompt_lines


def get_symmetry_mode_code_prompt_lines(name: str) -> tuple[str, ...]:
    symmetry = SYMMETRY_MODE_DEFINITIONS.get(str(name or '').strip()) or SYMMETRY_MODE_DEFINITIONS[DEFAULT_SYMMETRY_MODE]
    return symmetry.code_prompt_lines


def default_canonical_view(name: str) -> str:
    family = FAMILY_DEFINITIONS.get(str(name or '').strip()) or FAMILY_DEFINITIONS[DEFAULT_SUBJECT_FAMILY]
    return family.default_view


def default_shape_anchors(name: str, *, subject: str = '') -> list[str]:
    family = FAMILY_DEFINITIONS.get(str(name or '').strip()) or FAMILY_DEFINITIONS[DEFAULT_SUBJECT_FAMILY]
    anchors = list(family.default_shape_anchors)
    if name == DEFAULT_SUBJECT_FAMILY and subject.strip():
        anchors[0] = subject.strip()
    return anchors


__all__ = [
    'DEFAULT_RENDER_STRATEGY',
    'DEFAULT_SUBJECT_FAMILY',
    'DEFAULT_SYMMETRY_MODE',
    'DEFAULT_TOPOLOGY',
    'SUPPORTED_RENDER_STRATEGIES',
    'SUPPORTED_SUBJECT_FAMILIES',
    'SUPPORTED_SYMMETRY_MODES',
    'SUPPORTED_TOPOLOGIES',
    'default_canonical_view',
    'default_shape_anchors',
    'get_render_strategy_code_prompt_lines',
    'get_render_strategy_design_hint',
    'get_render_strategy_summary',
    'get_subject_family_code_prompt_lines',
    'get_subject_family_design_hint',
    'get_subject_family_summary',
    'get_symmetry_mode_code_prompt_lines',
    'get_symmetry_mode_design_hint',
    'get_symmetry_mode_summary',
    'get_topology_code_prompt_lines',
    'get_topology_design_hint',
    'get_topology_summary',
    'iter_family_definitions',
    'iter_render_strategy_definitions',
    'iter_symmetry_mode_definitions',
    'iter_topology_definitions',
]
