from __future__ import annotations

import json
import re

from typing import Any

from backend.app.led.schema.domain import (
    EXPECTED_HEIGHT,
    EXPECTED_INTERVAL_MS,
    EXPECTED_WIDTH,
    SemanticDesign,
)


DESIGN_SYSTEM_PROMPT = """You are the semantic designer for a music-reactive LED matrix animation.

Your job in stage one is not to write code. Convert a short user request into a stable, concrete, implementation-ready semantic design JSON for stage two.

Design priorities:
1. Keep the requested subject recognizable at first glance.
2. Define subject, palette, composition, and motion before describing low / medium / high energy mapping.
3. Do not collapse a concrete subject into generic particles, waves, breathing lights, or abstract noise.
4. Make colors specific. Name the key colors and explain where they belong.
5. Make composition specific. Explain where the subject sits and how the background supports it.
6. Make motion specific. Explain which structures move and which must remain stable.
7. Energy mapping must change structure, emphasis, or rhythm, not only brightness.
8. Avoid-list items must be concrete and directly relevant to failure cases.
9. Human-readable fields should use the same language as the user's request.
10. If the user request is short, infer only the minimum extra detail needed for a stable and recognizable result.

Return JSON only.
"""


CODE_SYSTEM_PROMPT = """You are the JavaScript generator for a music-reactive LED matrix animation.

Your only task in stage two is to convert an approved semantic design JSON into executable JavaScript that defines renderFrame(energy).

Hard constraints:
1. The LED board is always 29 columns by 16 rows.
2. The public API must remain renderFrame(energy).
3. The function must return frame[row][column] = [r, g, b].
4. Every RGB channel must be an integer in the range 0-255.
5. Internal animation state is allowed, but do not add new public parameters.
6. Do not use randomness, current time, network access, third-party packages, or host-specific APIs.
7. Preserve the semantic design's subject, palette, composition, motion rules, energy mapping, and avoid-list.
8. Do not degrade a concrete subject into an abstract full-screen effect.
9. Keep at least one stable subject layer and one energy-reactive motion layer.
10. Return JSON only.
"""


FAST_GENERATION_SYSTEM_PROMPT = """You are a single-pass generator for a music-reactive LED matrix animation.

Your internal workflow must mirror a stable two-stage process:
1. First derive a concrete semantic design.
2. Then generate renderFrame(energy) from that semantic design.

Do not reveal hidden reasoning, drafts, or intermediate notes. Return only the final JSON object.

Quality priorities:
1. Preserve recognizability of the requested subject.
2. Keep palette, composition, and motion rules specific rather than generic.
3. Do not degrade concrete subjects into abstract full-screen effects.
4. Make the semantic design strong enough that the generated code would match a separate design-first workflow.
5. Keep the semantic design and function_code mutually consistent.
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

Generate strict JSON with exactly one field:
- function_code

Requirements for function_code:
1. It must contain a complete JavaScript implementation of renderFrame(energy).
2. It must return a {height}-row by {width}-column frame of [r, g, b] pixels.
3. It must clamp both energy and RGB values.
4. It must keep explicit animation state such as smoothEnergy, phase, beatBoost, trail, or another equivalent mechanism.
5. It must visibly differentiate low / medium / high energy behavior.
6. It must honor the semantic design's avoid_list.
7. It must keep the subject readable before adding secondary lighting or background motion.
8. It must avoid full-screen synchronous flashing.
9. It should be portable plain JavaScript suitable for repeated host calls every {frame_interval_ms}ms.

Return JSON only, for example:
{{
  "function_code": "function renderFrame(energy) {{ ... }}"
}}""".format(
                design_json=design_json,
                width=width,
                height=height,
                frame_interval_ms=frame_interval_ms,
            ).strip(),
        ]
    )


def build_fast_generation_prompt(
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
            FAST_GENERATION_SYSTEM_PROMPT.strip(),
            '[USER]',
            _build_fast_generation_user_prompt(
                normalized_description,
                width=width,
                height=height,
                frame_interval_ms=frame_interval_ms,
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


def parse_fast_generation_response(raw_text: str) -> tuple[SemanticDesign, str]:
    payload = _parse_json_object(raw_text)
    semantic_design = payload.get('semantic_design')
    if not isinstance(semantic_design, dict):
        raise ValueError('model output does not contain semantic_design')

    function_code = str(payload.get('function_code') or '').strip()
    if not function_code:
        raise ValueError('model output does not contain function_code')

    return SemanticDesign.from_dict(semantic_design), function_code


def _build_design_user_prompt(
    description: str,
    *,
    width: int,
    height: int,
    frame_interval_ms: int,
) -> str:
    return """User request:
{description}

Target board:
- width: {width}
- height: {height}
- frame interval: {frame_interval_ms}ms
- public render function: renderFrame(energy)

Return strict JSON with these fields:
{semantic_design_fields}

Field requirements:
{semantic_design_field_requirements}

Quality bar:
- Design for a low-resolution board; silhouettes and anchors matter.
- Keep the subject specific when the user asks for a concrete thing.
- Add only the minimum missing detail required for a stable design.
- Avoid unrelated decorative elements.

Return JSON only.""".format(
        description=description,
        width=width,
        height=height,
        frame_interval_ms=frame_interval_ms,
        semantic_design_fields=_semantic_design_field_list(),
        semantic_design_field_requirements=_semantic_design_field_requirements(),
    )


def _build_fast_generation_user_prompt(
    description: str,
    *,
    width: int,
    height: int,
    frame_interval_ms: int,
) -> str:
    return """User request:
{description}

Target board:
- width: {width}
- height: {height}
- frame interval: {frame_interval_ms}ms
- public render function: renderFrame(energy)

Internally follow this workflow:
1. Derive a stable semantic_design that would be good enough for a separate design stage.
2. Generate function_code that follows that semantic_design exactly.
3. Do not output hidden reasoning or intermediate drafts.

Return strict JSON with exactly two fields:
- semantic_design
- function_code

semantic_design must contain these fields:
{semantic_design_fields}

semantic_design field requirements:
{semantic_design_field_requirements}

function_code requirements:
1. It must contain a complete JavaScript implementation of renderFrame(energy).
2. It must return a {height}-row by {width}-column frame of [r, g, b] pixels.
3. It must clamp both energy and RGB values.
4. It must keep explicit animation state such as smoothEnergy, phase, beatBoost, trail, or another equivalent mechanism.
5. It must visibly differentiate low / medium / high energy behavior.
6. It must honor semantic_design.avoid_list.
7. It must keep the subject readable before adding secondary lighting or background motion.
8. It must avoid full-screen synchronous flashing.
9. It should be portable plain JavaScript suitable for repeated host calls every {frame_interval_ms}ms.

Quality bar:
- Keep the subject recognizable at first glance.
- Keep palette, composition, motion rules, and energy mapping specific.
- Do not let the code drift away from the semantic_design you generated.

Return JSON only.""".format(
        description=description,
        width=width,
        height=height,
        frame_interval_ms=frame_interval_ms,
        semantic_design_fields=_semantic_design_field_list(),
        semantic_design_field_requirements=_semantic_design_field_requirements(),
    )


def _semantic_design_field_list() -> str:
    return """- name
- user_request
- summary
- subject
- color_palette
- composition
- motion_rules
- energy_mapping
- avoid_list
- implementation_hints"""


def _semantic_design_field_requirements() -> str:
    return """1. name: short ASCII slug suitable for filenames.
2. user_request: preserve the original user request meaning.
3. summary: one sentence summarizing subject, palette, and overall motion.
4. subject: the key recognizable visual anchor.
5. color_palette: at least 2 items, each describing color + region + purpose.
6. composition: at least 2 items describing layout and visual hierarchy.
7. motion_rules: at least 3 items covering stable structure, reactive structure, and restrained background behavior.
8. energy_mapping: object with low / medium / high arrays, each with at least 2 items describing structural or rhythmic change.
9. avoid_list: at least 2 concrete mistakes to avoid.
10. implementation_hints: at least 3 concrete hints that help code generation stay faithful."""


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
    'FAST_GENERATION_SYSTEM_PROMPT',
    'build_code_prompt',
    'build_design_prompt',
    'build_fast_generation_prompt',
    'parse_code_response',
    'parse_design_response',
    'parse_fast_generation_response',
]
