from __future__ import annotations

import json
import re
from typing import Any

from backend.app.iot.service.led.domain import (
    EXPECTED_HEIGHT,
    EXPECTED_INTERVAL_MS,
    EXPECTED_WIDTH,
    SemanticDesign,
    build_audio_feature_guidance_lines,
)


DESIGN_SYSTEM_PROMPT = """You are the semantic designer for a music-reactive LED matrix animation.

Your job in stage one is not to write code. Convert a short user request into a stable, concrete, implementation-ready semantic design JSON for stage two.

Design priorities:
1. Keep the requested subject recognizable at first glance.
2. Define subject, palette, composition, and motion before describing low / medium / high energy mapping.
3. Treat audio.energy as the global envelope, then map bass / mid / high / onset to clearly different specialized visual jobs.
4. Do not collapse a concrete subject into generic particles, waves, breathing lights, or abstract noise.
5. Make colors specific. Name the key colors and explain where they belong.
6. Make composition specific. Explain where the subject sits and how the background supports it.
7. Make motion specific. Explain which structures move and which must remain stable.
8. Energy mapping must change structure, emphasis, or rhythm, not only brightness.
9. Avoid-list items must be concrete and directly relevant to failure cases.
10. Human-readable fields should use the same language as the user's request.
11. If a feature should stay subtle, state what it preserves, accents, or triggers instead of leaving it vague.
12. If the user request is short, infer only the minimum extra detail needed for a stable and recognizable result.

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
8. Preserve the semantic design's subject, palette, composition, motion rules, energy mapping, audio feature mapping, and avoid-list.
9. Do not degrade a concrete subject into an abstract full-screen effect.
10. Keep at least one stable subject layer and one audio-reactive motion layer.
11. Treat onset like a fast transient trigger and energy like a slower envelope; they should not behave the same way.
12. Return JSON only.
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
10. It must keep the subject readable before adding secondary lighting or background motion.
11. It must avoid full-screen synchronous flashing.
12. It should be portable plain JavaScript suitable for repeated host calls every {frame_interval_ms}ms.

Return JSON only, for example:
{{
  "function_code": "function renderFrame(audio) {{ ... }}"
}}""".format(
                design_json=design_json,
                width=width,
                height=height,
                frame_interval_ms=frame_interval_ms,
                audio_feature_guidance=_indented_audio_feature_guidance_block(),
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

Audio feature mapping requirements:
- Each feature must describe a different visual responsibility, not just "change brightness".
- If a feature is intentionally subtle, explain what stable layer, edge, or trigger it should control.
{audio_feature_guidance}

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
        audio_feature_guidance=_audio_feature_guidance_block(),
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
- audio_feature_mapping
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
9. audio_feature_mapping: object with energy / bass / mid / high / onset arrays, each with at least 2 items describing feature-specific structural targets, accents, or trigger behaviors.
10. avoid_list: at least 2 concrete mistakes to avoid.
11. implementation_hints: at least 3 concrete hints that help code generation stay faithful."""


def _audio_feature_guidance_block() -> str:
    return '\n'.join(build_audio_feature_guidance_lines())


def _indented_audio_feature_guidance_block() -> str:
    return '\n'.join(build_audio_feature_guidance_lines(prefix='   - '))


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
