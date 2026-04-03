from __future__ import annotations

import json
import re
from typing import Any

from backend.app.cloud.service.led.domain import (
    ALLOWED_COMPLEXITY_LEVELS,
    EXPECTED_HEIGHT,
    EXPECTED_INTERVAL_MS,
    EXPECTED_WIDTH,
    SemanticDesign,
    SUPPORTED_RENDER_STRATEGIES,
    SUPPORTED_SUBJECT_FAMILIES,
    SUPPORTED_SYMMETRY_MODES,
    SUPPORTED_TOPOLOGIES,
    build_audio_feature_guidance_lines,
)
from backend.app.cloud.service.led.families import (
    get_render_strategy_code_prompt_lines,
    get_render_strategy_design_hint,
    get_render_strategy_summary,
    get_subject_family_code_prompt_lines,
    get_subject_family_design_hint,
    get_subject_family_summary,
    get_symmetry_mode_code_prompt_lines,
    get_symmetry_mode_design_hint,
    get_symmetry_mode_summary,
    get_topology_code_prompt_lines,
    get_topology_design_hint,
    get_topology_summary,
    iter_family_definitions,
    iter_render_strategy_definitions,
    iter_symmetry_mode_definitions,
    iter_topology_definitions,
)


DESIGN_SYSTEM_PROMPT = """You are the semantic designer for a music-reactive LED matrix animation.

Your job in stage one is not to write code. Convert a short user request into a stable, concrete, implementation-ready semantic design JSON for stage two.

Interpret the raw request as a bundle of visual directives:
- nouns and named entities define the subject or scene anchor
- adjectives define material, style, mood, lighting, and edge quality
- verbs define motion grammar and energy behavior
- explicit colors define palette priority
- spatial words define framing, camera angle, and composition
- negative phrases define avoid_list and simplification boundaries

Design priorities:
1. Preserve the user's core intent and visible style cues; do not replace them with generic LED cliches.
2. Keep the requested subject or dominant motif recognizable at first glance.
3. If the request already specifies style, material, lighting, pacing, or framing, keep those choices and build around them.
4. Translate atmospheric or stylistic words into concrete visual rules: shape language, edge hardness, density, depth, highlight behavior, and motion character.
5. Define subject, palette, composition, and motion before describing low / medium / high energy mapping.
6. Treat audio.energy as the global envelope, then map bass / mid / high / onset to clearly different specialized visual jobs.
7. Do not collapse a concrete subject into generic particles, waves, breathing lights, or abstract noise.
8. Make colors specific. Name the key colors, where they belong, and what visual role they serve.
9. Make composition specific. Explain where the main subject sits, what occupies foreground / midground / background, and how supporting elements stay subordinate.
10. Make motion specific. Explain which structures move, which must remain stable, how motion propagates, and what kind of rhythm or easing it has.
11. Energy mapping must change structure, emphasis, rhythm, density, or spacing, not only brightness.
12. Avoid-list items must be concrete and directly relevant to likely failure cases for this request.
13. For a 29x16 board, simplify aggressively: prefer one dominant subject and only the minimum supporting details required for recognition.
14. Choose the most iconic low-resolution-friendly view, pose, crop, or framing for the subject.
15. Classify each request into one subject_family, one topology, one render_strategy, and one symmetry_mode before writing the rest of the semantic design.
16. subject_family is the coarse content family, topology is the subject's spatial skeleton, render_strategy is how stage-two code should build it, and symmetry_mode is the intended balance rule.
17. Choose the routing fields from visible structure, not merely from noun matching.
18. Choose one canonical_view after the routing fields are set.
19. Define 2 to 4 shape_anchors that must remain readable at all times; these anchors are the minimum skeleton of the subject.
20. You must output concrete layout_constraints with numeric pixel budgets for the subject, supporting detail, background activity, bright pixels, and centroid drift.
21. Define 2 to 4 stable regions that must remain readable and at least 1 reactive region that may move without destroying recognition.
22. Secondary elements and background must stay subordinate; if they compete with the main subject, shrink or omit them.
23. Motion should deform existing structure, not smear the subject into one soft blob.
24. If the user asks for an abstract look instead of a concrete subject, still define one dominant motif, clear layering, and a repeatable motion grammar.
25. raw_user_request must preserve the exact user input text with no rewriting or translation.
26. expanded_request must be an English, code-generation-ready description that adds only the minimum extra detail needed for a stable, expressive, and recognizable result.
27. Keep summary, subject_family, topology, render_strategy, symmetry_mode, canonical_view, shape_anchors, complexity, subject, palette, composition, motion rules, mappings, layout_constraints, implementation hints, and avoid-list consistent with expanded_request.
28. If a feature should stay subtle, state what it preserves, accents, or triggers instead of leaving it vague.
29. If the user request is short, infer only the minimum extra detail needed for a stable and recognizable result.
30. When the user includes strong stylistic wording, preserve its visual personality through concrete rendering decisions rather than repeating the style label abstractly.

Return JSON only.
"""


CODE_SYSTEM_PROMPT = """You are the JavaScript generator for a music-reactive LED matrix animation.

Your only task in stage two is to convert an approved semantic design JSON into executable JavaScript that defines renderFrame(audio).

Hard constraints:
1. The LED board is always 29 columns by 16 rows.
2. The public API must remain renderFrame(audio).
3. The function must return frame[row][column] = [r, g, b].
4. The input is an object with normalized fields: energy, bass, mid, high, onset.
5. Every input feature and RGB channel must be clamped to valid range.
6. Internal animation state is allowed, but do not add new public parameters.
7. Do not use randomness, current time, network access, third-party packages, or host-specific APIs.
8. Preserve the semantic design's subject_family, topology, render_strategy, symmetry_mode, canonical_view, shape_anchors, complexity, subject, palette, composition, motion rules, energy mapping, audio feature mapping, layout_constraints, implementation hints, and avoid-list.
9. Do not degrade a concrete subject into an abstract full-screen effect.
10. Keep at least one stable subject layer and one audio-reactive motion layer.
11. Treat onset like a fast transient trigger and energy like a slower envelope; they should not behave the same way.
12. Treat subject_family as coarse routing, topology as the geometry skeleton, render_strategy as the construction method, and symmetry_mode as the balance rule.
13. For concrete subjects, build the output around semantic_design.shape_anchors and keep semantic_design.canonical_view recognizable before adding reactive detail.
14. Use explicit layered shapes, masks, contours, segmented geometry, palette ramps, or depth planes when needed; do not rely on one broad blob plus generic noise.
15. Translate style and material cues into concrete rendering behavior: shape language, edge softness or sharpness, density, highlight placement, texture illusion, trail behavior, and motion rhythm.
16. Translate composition cues into real pixel-space organization: foreground, main subject, supporting detail, and background should not all behave the same way.
17. Keep secondary props, scenery, sparkles, and background details clearly subordinate to the main subject.
18. If a support detail harms first-glance readability, reduce or omit it rather than weakening the main subject.
19. Avoid generic fallback aesthetics such as full-screen equalized pulsing, uniform glow blankets, or decorative noise that does not support the requested look.
20. Obey layout_constraints as hard budgets: keep the main readable mass within the requested active-pixel range, keep supporting/background activity under budget, and keep onset flashes localized.
21. Prefer readable, deterministic helper functions and explicit geometry over opaque cleverness.
22. Return JSON only.
"""


def build_design_prompt(
    description: str,
    *,
    width: int = EXPECTED_WIDTH,
    height: int = EXPECTED_HEIGHT,
    frame_interval_ms: int = EXPECTED_INTERVAL_MS,
) -> str:
    normalized_description = _normalize_description(description)
    _validate_board(width=width, height=height, frame_interval_ms=frame_interval_ms)
    return '\n\n'.join(
        [
            '[SYSTEM]',
            DESIGN_SYSTEM_PROMPT.strip(),
            '[USER]',
            _build_design_user_prompt(
                normalized_description,
                width=width,
                height=height,
                frame_interval_ms=frame_interval_ms,
            ).strip(),
        ]
    )


def build_code_prompt(
    design: SemanticDesign,
    *,
    width: int = EXPECTED_WIDTH,
    height: int = EXPECTED_HEIGHT,
    frame_interval_ms: int = EXPECTED_INTERVAL_MS,
) -> str:
    _validate_board(width=width, height=height, frame_interval_ms=frame_interval_ms)
    design_json = json.dumps(design.to_dict(), ensure_ascii=False, indent=2)

    return '\n\n'.join(
        [
            '[SYSTEM]',
            CODE_SYSTEM_PROMPT.strip(),
            '[USER]',
            """Here is the approved semantic design JSON from stage one:

{design_json}

Primary semantic source for code generation:
- Use semantic_design.expanded_request as the main normalized intent.
- Treat semantic_design.raw_user_request as traceability only; never reduce the design back to the short raw input.
- Keep the generated code aligned with semantic_design.summary, subject_family, topology, render_strategy, symmetry_mode, canonical_view, shape_anchors, complexity, subject, color_palette, composition, motion_rules, energy_mapping, audio_feature_mapping, layout_constraints, implementation_hints, and avoid_list.
- Realize preserved style, material, and mood cues through geometry, layering, palette distribution, highlight behavior, and motion character instead of generic decorative overlays.
- When readability conflicts with supporting details, preserve the dominant subject first and simplify the rest.
- Treat semantic_design.subject_family, semantic_design.topology, semantic_design.render_strategy, and semantic_design.symmetry_mode as routing signals, not optional prose.
- Honor these layout constraints as hard budgets:
{layout_constraints}
- Shape anchors to preserve:
{shape_anchors}
- Family-specific realization rules:
{family_rules}
- Topology-specific realization rules:
{topology_rules}
- Render-strategy realization rules:
{render_strategy_rules}
- Symmetry and balance rules:
{symmetry_rules}

Generate strict JSON with exactly one field:
- function_code

Requirements for function_code:
1. It must contain a complete JavaScript implementation of renderFrame(audio).
2. It must return a {height}-row by {width}-column frame of [r, g, b] pixels.
3. It must normalize and clamp audio.energy, audio.bass, audio.mid, audio.high, and audio.onset.
4. It must keep explicit animation state such as smoothEnergy, smoothBass, smoothHigh, phase, beatBoost, trail, or another equivalent mechanism.
5. It must visibly differentiate low / medium / high energy behavior.
6. It must use the audio feature roles distinctly:
{audio_feature_guidance}
7. It should smooth long-envelope features and treat onset as a fast trigger or accent signal.
8. It must not collapse bass, mid, high, and onset into simple aliases of energy or of each other.
9. It must honor the semantic design's avoid_list.
10. It must keep the rendered subject, support detail, background activity, bright pixels, and centroid drift within semantic_design.layout_constraints.
11. It should realize the subject as 2 to 4 stable structural regions or silhouette anchors rather than one undifferentiated mass.
12. For concrete subjects, it should prefer explicit layered or segmented geometry over broad blob fields with generic wave distortion.
13. It should convert style and material cues into concrete pixel behavior such as edge treatment, fill density, depth separation, highlight placement, trail persistence, and motion rhythm.
14. It must keep the subject readable before adding secondary lighting or background motion.
15. It must keep supporting details subordinate and may simplify or omit them if needed for recognizability.
16. It should separate foreground, subject core, accents, and background so they do not all pulse identically.
17. It must avoid full-screen synchronous flashing.
18. It should favor deterministic helper functions, explicit masks, and readable structure over opaque tricks.
19. It should be portable plain JavaScript suitable for repeated host calls every {frame_interval_ms}ms.

Return JSON only, for example:
{{
  "function_code": "function renderFrame(audio) {{ ... }}"
}}""".format(
                design_json=design_json,
                width=width,
                height=height,
                frame_interval_ms=frame_interval_ms,
                audio_feature_guidance=_indented_audio_feature_guidance_block(),
                layout_constraints=_indented_layout_constraints_block(design),
                shape_anchors=_indented_shape_anchor_block(design),
                family_rules=_indented_family_code_prompt_block(design),
                topology_rules=_indented_topology_code_prompt_block(design),
                render_strategy_rules=_indented_render_strategy_code_prompt_block(design),
                symmetry_rules=_indented_symmetry_mode_code_prompt_block(design),
            ).strip(),
        ]
    )


def parse_design_response(raw_text: str) -> SemanticDesign:
    return SemanticDesign.from_dict(_parse_json_object(raw_text))


def parse_code_response(raw_text: str) -> str:
    payload = _parse_json_object(raw_text)
    function_code = str(payload.get('function_code') or '').strip()
    if not function_code:
        raise ValueError('model output does not contain function_code')
    return function_code


def _build_design_user_prompt(
    description: str,
    *,
    width: int,
    height: int,
    frame_interval_ms: int,
) -> str:
    return """User request:
{description}

Important request binding rules:
- raw_user_request must exactly equal the user request above, character-for-character.
- expanded_request must be a richer English description that stage two can use directly for code generation.
- expanded_request should make subject, palette, composition, motion, stability, and key avoid constraints explicit without changing the user's core intent.
- expanded_request should choose an iconic low-resolution-friendly view and keep only the most recognition-critical supporting details.
- expanded_request should explicitly preserve useful user-provided style cues such as material, lighting, atmosphere, texture, pacing, framing, and motion verbs.

Target board:
- width: {width}
- height: {height}
- frame interval: {frame_interval_ms}ms
- public render function: renderFrame(audio)
- audio input fields: energy, bass, mid, high, onset

Return strict JSON with these fields:
{semantic_design_fields}

Field requirements:
{semantic_design_field_requirements}

Routing options:
Subject families:
{subject_family_options}

Topologies:
{topology_options}

Render strategies:
{render_strategy_options}

Symmetry modes:
{symmetry_mode_options}

Routing design hints:
Family hints:
{family_design_hints}

Topology hints:
{topology_design_hints}

Render-strategy hints:
{render_strategy_design_hints}

Symmetry hints:
{symmetry_mode_design_hints}

Audio feature mapping requirements:
- Each feature must describe a different visual responsibility, not just "change brightness".
- If a feature is intentionally subtle, explain what stable layer, edge, or trigger it should control.
{audio_feature_guidance}

Quality bar:
- Mine the user wording for subject nouns, style adjectives, material cues, camera or framing words, motion verbs, palette words, and negative constraints.
- Convert vague atmosphere words into explicit palette, contrast, edge quality, layering, and motion rules.
- If the user names a visual style, express it through shape language, lighting, texture illusion, and movement rather than merely repeating the style name.
- Design for a low-resolution board; silhouettes and anchors matter.
- Keep the subject specific when the user asks for a concrete thing.
- Add only the minimum missing detail required for a stable design.
- Prefer one dominant subject over a crowded scene unless the request explicitly asks for multiple equal subjects.
- State the key silhouette anchors or structural regions that must remain readable.
- Assign a concrete numeric pixel budget through layout_constraints instead of describing simplification only in prose.
- Keep secondary props, support structures, sparkles, and background texture on a clearly smaller pixel budget than the main subject.
- Avoid unrelated decorative elements.

Return JSON only.""".format(
        description=description,
        width=width,
        height=height,
        frame_interval_ms=frame_interval_ms,
        semantic_design_fields=_semantic_design_field_list(),
        semantic_design_field_requirements=_semantic_design_field_requirements(),
        subject_family_options=_subject_family_options_block(),
        topology_options=_topology_options_block(),
        render_strategy_options=_render_strategy_options_block(),
        symmetry_mode_options=_symmetry_mode_options_block(),
        family_design_hints=_family_design_hints_block(),
        topology_design_hints=_topology_design_hints_block(),
        render_strategy_design_hints=_render_strategy_design_hints_block(),
        symmetry_mode_design_hints=_symmetry_mode_design_hints_block(),
        audio_feature_guidance=_audio_feature_guidance_block(),
    )


def _semantic_design_field_list() -> str:
    return """- name
- raw_user_request
- expanded_request
- summary
- subject_family
- topology
- render_strategy
- symmetry_mode
- canonical_view
- shape_anchors
- complexity
- subject
- color_palette
- composition
- motion_rules
- energy_mapping
- audio_feature_mapping
- layout_constraints
- avoid_list
- implementation_hints"""


def _semantic_design_field_requirements() -> str:
    return """1. name: short ASCII slug suitable for filenames.
2. raw_user_request: copy the exact original user input text verbatim with no translation or rewriting.
3. expanded_request: write a richer English request for stage-two code generation, making subject, palette, composition, motion, stable structure, reactive accents, major avoid constraints, and important style cues explicit while staying faithful to the raw request. It should preserve user-specified material, lighting, atmosphere, framing, or pacing when present, choose an iconic low-resolution-friendly view, describe 2 to 4 key silhouette anchors or structural regions, and keep supporting details minimal.
4. summary: one sentence summarizing subject, palette, and overall motion.
5. subject_family: choose exactly one supported family label that best matches the simplified low-resolution subject.
6. topology: choose exactly one supported topology label describing the subject's spatial skeleton on the 29x16 board.
7. render_strategy: choose exactly one supported render strategy label describing how stage-two code should construct the subject.
8. symmetry_mode: choose exactly one supported symmetry label describing whether the subject should read as radial, bilateral, directional, softly asymmetric, stacked, or freeform.
9. canonical_view: one short phrase naming the most iconic low-resolution-friendly view or framing for this subject.
10. shape_anchors: 2 to 4 short items describing the minimum readable structural anchors that must survive simplification.
11. complexity: choose one of {complexity_levels}, based on how aggressively the scene should be simplified.
12. subject: the key recognizable visual anchor plus the minimal silhouette parts, style-defining shape traits, or dominant motif that must remain readable on a 29x16 board.
13. color_palette: at least 2 items, each describing color + region + purpose, including style-relevant lighting or material accents when applicable.
14. composition: at least 2 items describing layout, dominant subject placement, framing or depth cues when relevant, and how secondary elements stay subordinate.
15. motion_rules: at least 3 items covering stable structure, reactive structure, motion character, and explicit deformation limits that preserve recognizability.
16. energy_mapping: object with low / medium / high arrays, each with at least 2 items describing structural or rhythmic change.
17. audio_feature_mapping: object with energy / bass / mid / high / onset arrays, each with at least 2 items describing feature-specific structural targets, accents, textural roles, or trigger behaviors.
18. layout_constraints: object with numeric fields subject_min_pixels, subject_max_pixels, supporting_max_pixels, background_max_pixels, bright_max_pixels, max_centroid_shift, plus stable_regions and reactive_regions arrays. These must describe a feasible 29x16 pixel budget: keep one dominant subject, keep support detail smaller than the subject, keep background activity tightly capped, and keep centroid drift small enough that the subject stays readable.
19. avoid_list: at least 2 concrete mistakes to avoid.
20. implementation_hints: at least 3 concrete hints that help code generation stay faithful, including geometry strategy, layering, palette distribution, motion mechanics, or silhouette-preserving simplification when needed.""".format(
        complexity_levels=', '.join(ALLOWED_COMPLEXITY_LEVELS)
    )


def _audio_feature_guidance_block() -> str:
    return '\n'.join(build_audio_feature_guidance_lines())


def _indented_audio_feature_guidance_block() -> str:
    return '\n'.join(build_audio_feature_guidance_lines(prefix='   - '))


def _indented_layout_constraints_block(design: SemanticDesign) -> str:
    return '\n'.join('   - {0}'.format(line) for line in design.layout_constraints.to_spec_lines())


def _indented_shape_anchor_block(design: SemanticDesign) -> str:
    return '\n'.join('   - {0}'.format(item) for item in design.shape_anchors)


def _subject_family_options_block() -> str:
    return '\n'.join(
        '- {0}: {1}'.format(family, get_subject_family_summary(family))
        for family in SUPPORTED_SUBJECT_FAMILIES
    )


def _topology_options_block() -> str:
    return '\n'.join(
        '- {0}: {1}'.format(topology, get_topology_summary(topology))
        for topology in SUPPORTED_TOPOLOGIES
    )


def _render_strategy_options_block() -> str:
    return '\n'.join(
        '- {0}: {1}'.format(strategy, get_render_strategy_summary(strategy))
        for strategy in SUPPORTED_RENDER_STRATEGIES
    )


def _symmetry_mode_options_block() -> str:
    return '\n'.join(
        '- {0}: {1}'.format(symmetry_mode, get_symmetry_mode_summary(symmetry_mode))
        for symmetry_mode in SUPPORTED_SYMMETRY_MODES
    )


def _family_design_hints_block() -> str:
    return '\n'.join(
        '- {0}: {1}'.format(family.name, get_subject_family_design_hint(family.name))
        for family in iter_family_definitions()
    )


def _topology_design_hints_block() -> str:
    return '\n'.join(
        '- {0}: {1}'.format(topology.name, get_topology_design_hint(topology.name))
        for topology in iter_topology_definitions()
    )


def _render_strategy_design_hints_block() -> str:
    return '\n'.join(
        '- {0}: {1}'.format(strategy.name, get_render_strategy_design_hint(strategy.name))
        for strategy in iter_render_strategy_definitions()
    )


def _symmetry_mode_design_hints_block() -> str:
    return '\n'.join(
        '- {0}: {1}'.format(symmetry_mode.name, get_symmetry_mode_design_hint(symmetry_mode.name))
        for symmetry_mode in iter_symmetry_mode_definitions()
    )


def _indented_family_code_prompt_block(design: SemanticDesign) -> str:
    return '\n'.join(
        '   - {0}'.format(line)
        for line in get_subject_family_code_prompt_lines(design.subject_family)
    )


def _indented_topology_code_prompt_block(design: SemanticDesign) -> str:
    return '\n'.join(
        '   - {0}'.format(line)
        for line in get_topology_code_prompt_lines(design.topology)
    )


def _indented_render_strategy_code_prompt_block(design: SemanticDesign) -> str:
    return '\n'.join(
        '   - {0}'.format(line)
        for line in get_render_strategy_code_prompt_lines(design.render_strategy)
    )


def _indented_symmetry_mode_code_prompt_block(design: SemanticDesign) -> str:
    return '\n'.join(
        '   - {0}'.format(line)
        for line in get_symmetry_mode_code_prompt_lines(design.symmetry_mode)
    )


def _normalize_description(description: str) -> str:
    normalized = str(description or '').strip()
    if not normalized:
        raise ValueError('description must not be empty')
    return normalized


def _validate_board(*, width: int, height: int, frame_interval_ms: int) -> None:
    if width <= 0 or height <= 0:
        raise ValueError('width and height must be positive integers')
    if frame_interval_ms <= 0:
        raise ValueError('frame_interval_ms must be a positive integer')


def _parse_json_object(raw_text: str) -> dict[str, Any]:
    payload = _extract_json_payload(raw_text)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError('model output is not valid JSON: {0}'.format(exc)) from exc
    if not isinstance(data, dict):
        raise ValueError('model output root must be a JSON object')
    return data


def _extract_json_payload(raw_text: str) -> str:
    text = str(raw_text or '').strip()
    if not text:
        raise ValueError('model output is empty')

    fenced_payload = _extract_fenced_json_payload(text)
    if fenced_payload is not None:
        return fenced_payload

    embedded_payload = _extract_first_json_object(text)
    if embedded_payload is not None:
        return embedded_payload

    return text


def _extract_fenced_json_payload(text: str) -> str | None:
    match = re.search(r'```(?:json)?\s*\n(?P<body>[\s\S]*?)\n```', text, re.IGNORECASE)
    if not match:
        return None
    body = match.group('body').strip()
    return body or None


def _extract_first_json_object(text: str) -> str | None:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != '{':
            continue
        try:
            value, end_index = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return text[index : index + end_index]
    return None


__all__ = [
    'CODE_SYSTEM_PROMPT',
    'DESIGN_SYSTEM_PROMPT',
    'build_code_prompt',
    'build_design_prompt',
    'parse_code_response',
    'parse_design_response',
]
