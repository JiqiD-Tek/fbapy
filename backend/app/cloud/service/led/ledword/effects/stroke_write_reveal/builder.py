from __future__ import annotations

import json
import random
from typing import Dict, List, Sequence, Tuple

from backend.app.cloud.service.led.ledword.text_board import render_text_board, render_text_board_with_font_size
from backend.app.cloud.service.led.ledword.common import derive_seed, is_latin_character, resolve_local_palette
from backend.app.cloud.service.led.ledword.core import BOARD_HEIGHT, BOARD_WIDTH
from backend.app.cloud.service.led.ledword.effects._shared.centered_reveal_runtime import (
    LocalEffectContext,
    LocalEffectResult,
    LocalEffectSpec,
)
from backend.app.cloud.service.led.ledword.effects.common import extract_visible_units
from backend.app.cloud.service.led.ledword.styles import supports_text_effect_for_text


REVEAL_FRAMES = 32
HOLD_FRAMES = 8
FADE_FRAMES = 8
GAP_FRAMES = 4
TAIL_POINTS = 2


def build_stroke_write_reveal_spec() -> LocalEffectSpec:
    return LocalEffectSpec(
        name="stroke_write_reveal",
        supports=_supports_stroke_write_reveal,
        build=build_stroke_write_reveal,
    )


def build_stroke_write_reveal(context: LocalEffectContext) -> LocalEffectResult:
    units = extract_visible_units(context.text)
    if not units:
        raise ValueError("stroke_write_reveal requires at least one visible unit")

    initial_renders = [
        render_text_board(
            unit,
            font_path=context.font_path,
        )
        for unit in units
    ]
    shared_font_size = min(rendered.font_size for rendered in initial_renders)
    shared_threshold = min(max(0, min(255, int(rendered.threshold))) for rendered in initial_renders)
    rendered_units = [
        render_text_board_with_font_size(
            unit,
            font_path=context.font_path,
            font_size=shared_font_size,
            threshold=shared_threshold,
        )
        for unit in units
    ]

    stroke_paths = [
        _build_stroke_path(
            rendered.mask,
            seed=context.seed,
            unit_index=index,
            prefer_horizontal=_unit_prefers_horizontal(unit),
        )
        for index, (unit, rendered) in enumerate(zip(units, rendered_units))
    ]
    if not all(path for path in stroke_paths):
        raise ValueError("stroke_write_reveal produced an empty stroke path")

    palette = resolve_local_palette(context.background_style.name)
    units_json = json.dumps(units, ensure_ascii=False)
    paths_json = json.dumps(stroke_paths, ensure_ascii=False)
    bg_dark_json = json.dumps(palette["bg_dark"])
    bg_mid_json = json.dumps(palette["bg_mid"])
    bg_light_json = json.dumps(palette["bg_light"])
    accent_json = json.dumps(palette["accent"])
    text_main_json = json.dumps(palette["text_main"])
    text_alt_json = json.dumps(palette["text_alt"])
    text_edge_json = json.dumps(palette["text_edge"])
    halo_json = json.dumps(palette["halo"])
    text_ramp_json = json.dumps(palette["text_ramp"])

    frames_per_unit = REVEAL_FRAMES + HOLD_FRAMES + FADE_FRAMES + GAP_FRAMES
    loop_length_frames = frames_per_unit * len(units)
    lines = [
        "function renderFrame(audio) {",
        f"  const W = {BOARD_WIDTH};",
        f"  const H = {BOARD_HEIGHT};",
        f"  const UNITS = {units_json};",
        f"  const PATHS = {paths_json};",
        f"  const REVEAL_FRAMES = {REVEAL_FRAMES};",
        f"  const HOLD_FRAMES = {HOLD_FRAMES};",
        f"  const FADE_FRAMES = {FADE_FRAMES};",
        f"  const GAP_FRAMES = {GAP_FRAMES};",
        f"  const TAIL_POINTS = {TAIL_POINTS};",
        f"  const FRAMES_PER_UNIT = {frames_per_unit};",
        f"  const LOOP_FRAMES = {loop_length_frames};",
        f"  const BG_DARK = {bg_dark_json};",
        f"  const BG_MID = {bg_mid_json};",
        f"  const BG_LIGHT = {bg_light_json};",
        f"  const ACCENT = {accent_json};",
        f"  const TEXT_MAIN = {text_main_json};",
        f"  const TEXT_ALT = {text_alt_json};",
        f"  const TEXT_EDGE = {text_edge_json};",
        f"  const HALO = {halo_json};",
        f"  const TEXT_RAMP = {text_ramp_json};",
        "",
        "  function clamp255(value) {",
        "    value = Math.round(value);",
        "    return value < 0 ? 0 : value > 255 ? 255 : value;",
        "  }",
        "",
        "  function mix(a, b, t) {",
        "    return a + (b - a) * t;",
        "  }",
        "",
        "  function mixColor(a, b, t) {",
        "    return [mix(a[0], b[0], t), mix(a[1], b[1], t), mix(a[2], b[2], t)];",
        "  }",
        "",
        "  function sampleRamp(t) {",
        "    const index = state && Number.isInteger(state.textVariantIndex) ? state.textVariantIndex % TEXT_RAMP.length : 0;",
        "    return TEXT_RAMP[index];",
        "  }",
        "",
        "  function scaleColor(color, strength) {",
        "    return [color[0] * strength, color[1] * strength, color[2] * strength];",
        "  }",
        "",
        "  function sampleBackground(x, y, phase) {",
        "    const ny = H <= 1 ? 0 : y / (H - 1);",
        "    let color = mixColor(BG_DARK, BG_MID, 0.08 + ny * 0.22);",
        "    color = mixColor(color, BG_LIGHT, 0.02 + ny * 0.03);",
        "    if (y === 0 || y === H - 1) {",
        "      color = mixColor(color, BG_DARK, 0.14);",
        "    }",
        "    return color;",
        "  }",
        "",
        "  function sampleInkColor(x, y, headBoost, unitIndex) {",
        "    const nx = W <= 1 ? 0.5 : x / (W - 1);",
        "    const ny = H <= 1 ? 0.5 : y / (H - 1);",
        "    const drift = 0.5 + 0.5 * Math.sin(nx * 4.4 + unitIndex * 0.7 - ny * 2.2);",
        "    let ink = sampleRamp(nx * 0.40 + ny * 0.24 + unitIndex * 0.08 + drift * 0.08);",
        "    ink = mixColor(ink, sampleRamp(0.68 + nx * 0.08), 0.18 + nx * 0.06);",
        "    ink = mixColor(ink, TEXT_EDGE, 0.08 + nx * 0.08);",
        "    ink = mixColor(ink, HALO, headBoost * 0.10 + drift * 0.04);",
        "    return ink;",
        "  }",
        "",
        "  if (!renderFrame._state) {",
        "    renderFrame._state = { frame: 0, textVariantIndex: Math.floor(Math.random() * TEXT_RAMP.length) };",
        "  }",
        "  const state = renderFrame._state;",
        "  const frameIndex = state.frame;",
        "  state.frame = (state.frame + 1) % LOOP_FRAMES;",
        "",
        "  const phase = frameIndex / LOOP_FRAMES;",
        "  const unitIndex = Math.floor(frameIndex / FRAMES_PER_UNIT);",
        "  const localFrame = frameIndex % FRAMES_PER_UNIT;",
        "  const path = PATHS[unitIndex] || [];",
        "  const pointTotal = path.length || 1;",
        "  let revealProgress = 0.0;",
        "  let fadeAlpha = 0.0;",
        "  if (localFrame < REVEAL_FRAMES) {",
        "    revealProgress = REVEAL_FRAMES <= 1 ? 1.0 : localFrame / Math.max(1, REVEAL_FRAMES - 1);",
        "    fadeAlpha = 1.0;",
        "  } else if (localFrame < REVEAL_FRAMES + HOLD_FRAMES) {",
        "    revealProgress = 1.0;",
        "    fadeAlpha = 1.0;",
        "  } else if (localFrame < REVEAL_FRAMES + HOLD_FRAMES + FADE_FRAMES) {",
        "    revealProgress = 1.0;",
        "    const fadeFrame = localFrame - REVEAL_FRAMES - HOLD_FRAMES;",
        "    fadeAlpha = 1.0 - (FADE_FRAMES <= 1 ? 1.0 : fadeFrame / Math.max(1, FADE_FRAMES - 1));",
        "  }",
        "",
        "  const frame = new Array(H);",
        "  for (let y = 0; y < H; y++) {",
        "    const row = new Array(W);",
        "    for (let x = 0; x < W; x++) {",
        "      const bg = sampleBackground(x, y, phase);",
        "      row[x] = [clamp255(bg[0]), clamp255(bg[1]), clamp255(bg[2])];",
        "    }",
        "    frame[y] = row;",
        "  }",
        "",
        "  if (fadeAlpha <= 0.0 || path.length === 0) {",
        "    return frame;",
        "  }",
        "",
        "  const visibleCount = localFrame < REVEAL_FRAMES",
        "    ? Math.max(0, Math.min(path.length, Math.ceil(revealProgress * path.length)))",
        "    : path.length;",
        "  if (visibleCount <= 0) {",
        "    return frame;",
        "  }",
        "  const headIndex = visibleCount - 1;",
        "  for (let index = 0; index < visibleCount; index++) {",
        "    const point = path[index];",
        "    const px = point[0];",
        "    const py = point[1];",
        "    if (px < 0 || px >= W || py < 0 || py >= H) continue;",
        "    const headBoost = Math.max(0.0, 1.0 - (headIndex - index) / Math.max(1, TAIL_POINTS));",
        "    let ink = sampleInkColor(px, py, headBoost, unitIndex);",
        "    ink = scaleColor(ink, fadeAlpha * (0.88 + headBoost * 0.08));",
        "    frame[py][px] = [clamp255(ink[0]), clamp255(ink[1]), clamp255(ink[2])];",
        "  }",
        "",
        "  const head = path[headIndex];",
        "  if (head) {",
        "    const hx = head[0];",
        "    const hy = head[1];",
        "    const headColor = scaleColor(mixColor(TEXT_MAIN, HALO, 0.10), fadeAlpha * 0.12);",
        "    frame[hy][hx] = [",
        "      clamp255(frame[hy][hx][0] + headColor[0]),",
        "      clamp255(frame[hy][hx][1] + headColor[1]),",
        "      clamp255(frame[hy][hx][2] + headColor[2]),",
        "    ];",
        "  }",
        "",
        "  return frame;",
        "}",
    ]
    path_lengths = ", ".join(str(len(path)) for path in stroke_paths)
    note = "\n".join(
        [
            "[LOCAL]",
            "generator: stroke write reveal",
            f"text: {context.text}",
            "motion: each visible unit is written one by one along a simple continuous pixel path with steady ink and only a slight pen-tip highlight",
            f"units: {' | '.join(units)}",
            f"path_lengths: {path_lengths}",
            f"board: {BOARD_WIDTH}x{BOARD_HEIGHT}",
            f"shared_font_size: {shared_font_size}",
            f"shared_threshold: {shared_threshold}",
            f"loop_length_frames: {loop_length_frames}",
            f"background_style: {context.background_style.name}",
            f"font_style: {context.font_style.name}",
            f"text_effect: {context.text_effect.name}",
            "constraint: this effect writes one visible character at a time, ignores spaces, and approximates stroke flow from the rasterized glyph",
        ]
    )
    return LocalEffectResult(
        loop_length_frames=loop_length_frames,
        function_code="\n".join(lines) + "\n",
        note=note,
    )


def _supports_stroke_write_reveal(context: LocalEffectContext) -> bool:
    return bool(extract_visible_units(context.text)) and supports_text_effect_for_text(
        "stroke_write_reveal",
        context.text,
    )


def _build_stroke_path(
    mask: Sequence[Sequence[int]],
    *,
    seed: int | None,
    unit_index: int,
    prefer_horizontal: bool,
) -> List[List[int]]:
    points = [(x, y) for y, row in enumerate(mask) for x, value in enumerate(row) if value]
    if not points:
        return []
    full_points = set(points)
    neighbor_counts = {point: _neighbor_count(point, full_points) for point in full_points}
    rng_seed = derive_seed(seed, 6301 + unit_index * 37) or ((unit_index + 1) * 401 + len(points) * 13)
    rng = random.Random(rng_seed)
    unvisited = set(full_points)
    current = _pick_stroke_start(
        unvisited,
        neighbor_counts=neighbor_counts,
        prefer_horizontal=prefer_horizontal,
    )
    previous_direction = (1, 0) if prefer_horizontal else (0, 1)
    ordered: List[List[int]] = []
    while unvisited:
        if current not in unvisited:
            current = _pick_next_stroke_point(
                current,
                unvisited,
                previous_direction=previous_direction,
                neighbor_counts=neighbor_counts,
                prefer_horizontal=prefer_horizontal,
                rng=rng,
            )
            if current is None:
                break
        ordered.append([current[0], current[1]])
        unvisited.remove(current)
        if not unvisited:
            break
        next_point = _pick_next_stroke_point(
            current,
            unvisited,
            previous_direction=previous_direction,
            neighbor_counts=neighbor_counts,
            prefer_horizontal=prefer_horizontal,
            rng=rng,
        )
        if next_point is None:
            break
        previous_direction = (_sign(next_point[0] - current[0]), _sign(next_point[1] - current[1]))
        current = next_point
    return ordered


def _pick_stroke_start(
    points: Sequence[Tuple[int, int]] | set[Tuple[int, int]],
    *,
    neighbor_counts: Dict[Tuple[int, int], int],
    prefer_horizontal: bool,
) -> Tuple[int, int]:
    def score(point: Tuple[int, int]) -> Tuple[float, float, float]:
        x, y = point
        axis_bias = float(x) * 0.08 + float(y) * 0.03 if prefer_horizontal else float(y) * 0.08 + float(x) * 0.03
        return (float(neighbor_counts.get(point, 0)), axis_bias, float(x + y))

    return min(points, key=score)


def _pick_next_stroke_point(
    current: Tuple[int, int],
    points: Sequence[Tuple[int, int]] | set[Tuple[int, int]],
    *,
    previous_direction: Tuple[int, int],
    neighbor_counts: Dict[Tuple[int, int], int],
    prefer_horizontal: bool,
    rng: random.Random,
) -> Tuple[int, int] | None:
    if not points:
        return None
    adjacent = [
        point
        for point in points
        if max(abs(point[0] - current[0]), abs(point[1] - current[1])) <= 1
    ]
    candidates = adjacent if adjacent else list(points)
    best_point: Tuple[int, int] | None = None
    best_score: float | None = None
    for point in candidates:
        dx = point[0] - current[0]
        dy = point[1] - current[1]
        manhattan = abs(dx) + abs(dy)
        chebyshev = max(abs(dx), abs(dy))
        step_direction = (_sign(dx), _sign(dy))
        turn_penalty = _turn_penalty(previous_direction, step_direction)
        density_penalty = float(neighbor_counts.get(point, 0)) * 0.08
        axis_bias = float(point[0]) * 0.04 + float(point[1]) * 0.02
        if not prefer_horizontal:
            axis_bias = float(point[1]) * 0.04 + float(point[0]) * 0.02
        jump_penalty = 0.0 if adjacent else 3.0 + float(manhattan) * 0.35
        score = (
            float(manhattan) * 0.85
            + float(chebyshev) * 0.20
            + turn_penalty
            + density_penalty
            + axis_bias
            + jump_penalty
            + rng.random() * 0.001
        )
        if best_score is None or score < best_score:
            best_score = score
            best_point = point
    return best_point


def _neighbor_count(point: Tuple[int, int], points: set[Tuple[int, int]]) -> int:
    x, y = point
    total = 0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            if (x + dx, y + dy) in points:
                total += 1
    return total


def _turn_penalty(previous_direction: Tuple[int, int], step_direction: Tuple[int, int]) -> float:
    if step_direction == (0, 0):
        return 0.0
    if previous_direction == step_direction:
        return 0.0
    if step_direction == (-previous_direction[0], -previous_direction[1]):
        return 0.95
    if (
        step_direction[0] == previous_direction[0]
        or step_direction[1] == previous_direction[1]
        or (
            abs(step_direction[0] - previous_direction[0]) <= 1
            and abs(step_direction[1] - previous_direction[1]) <= 1
        )
    ):
        return 0.28
    return 0.56


def _unit_prefers_horizontal(unit: str) -> bool:
    visible = [char for char in str(unit or "") if not char.isspace()]
    return any(is_latin_character(char) or char.isdigit() for char in visible)


def _sign(value: int) -> int:
    if value < 0:
        return -1
    if value > 0:
        return 1
    return 0


__all__ = [
    "build_stroke_write_reveal",
    "build_stroke_write_reveal_spec",
]


