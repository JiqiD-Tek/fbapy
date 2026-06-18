from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from backend.app.cloud.service.led.ledword.core import BOARD_HEIGHT, BOARD_WIDTH
from backend.app.cloud.service.led.ledword.styles import BackgroundStylePreset, FontStylePreset, TextEffectPreset

from ..common import (
    build_ordered_pixel_points_for_unit,
    extract_visible_units,
    resolve_local_four_way_palette,
)
from .profile import PIXEL_REVEAL_EFFECT_NAMES, resolve_pixel_reveal_order_mode


def build_local_pixel_reveal_function_code(
    *,
    text: str,
    background_style: BackgroundStylePreset,
    text_effect: TextEffectPreset,
    font_path: Path,
    seed: Optional[int],
) -> tuple[int, str]:
    visible_units = extract_visible_units(text)
    if not visible_units:
        raise ValueError("pixel reveal requires at least one visible character")

    order_mode = resolve_pixel_reveal_order_mode(
        text=text,
        text_effect_name=text_effect.name,
        visible_units=visible_units,
        seed=seed,
    )
    char_points = [
        build_ordered_pixel_points_for_unit(
            unit,
            font_path=font_path,
            order_mode=order_mode,
            unit_index=unit_index,
            seed=seed,
        )
        for unit_index, unit in enumerate(visible_units)
    ]
    if not all(points for points in char_points):
        raise ValueError("pixel reveal produced an empty character sprite")

    palette = resolve_local_four_way_palette(background_style)
    points_json = json.dumps(char_points, ensure_ascii=False)
    units_json = json.dumps(visible_units, ensure_ascii=False)
    bg_dark_json = json.dumps(palette["bg_dark"])
    bg_mid_json = json.dumps(palette["bg_mid"])
    bg_light_json = json.dumps(palette["bg_light"])
    accent_json = json.dumps(palette["accent"])
    text_main_json = json.dumps(palette["text_main"])
    text_alt_json = json.dumps(palette["text_alt"])
    text_edge_json = json.dumps(palette["text_edge"])
    halo_json = json.dumps(palette["halo"])
    text_ramp_json = json.dumps(palette["text_ramp"])
    effect_name_json = json.dumps(text_effect.name)
    order_mode_json = json.dumps(order_mode)

    reveal_frames = 20
    hold_frames = 8
    fade_frames = 14
    gap_frames = 4
    frames_per_char = reveal_frames + hold_frames + fade_frames + gap_frames
    loop_length_frames = frames_per_char * len(visible_units)

    lines = [
        "function renderFrame(audio) {",
        f"  const W = {BOARD_WIDTH};",
        f"  const H = {BOARD_HEIGHT};",
        f"  const EFFECT = {effect_name_json};",
        f"  const ORDER_MODE = {order_mode_json};",
        f"  const UNITS = {units_json};",
        f"  const CHAR_POINTS = {points_json};",
        f"  const REVEAL_FRAMES = {reveal_frames};",
        f"  const HOLD_FRAMES = {hold_frames};",
        f"  const FADE_FRAMES = {fade_frames};",
        f"  const GAP_FRAMES = {gap_frames};",
        f"  const FRAMES_PER_CHAR = {frames_per_char};",
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
        "    return [",
        "      mix(a[0], b[0], t),",
        "      mix(a[1], b[1], t),",
        "      mix(a[2], b[2], t),",
        "    ];",
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
        "    const nx = W <= 1 ? 0 : x / (W - 1);",
        "    const ny = H <= 1 ? 0 : y / (H - 1);",
        "    const sweep = 0.5 + 0.5 * Math.sin(phase * Math.PI * 2.0 + nx * 3.1 - ny * 1.7);",
        "    const scan = 0.5 + 0.5 * Math.sin(phase * Math.PI * 4.0 + ny * Math.PI * 2.3);",
        "    let color = mixColor(BG_DARK, BG_MID, 0.08 + ny * 0.22);",
        "    color = mixColor(color, BG_LIGHT, 0.015 + sweep * 0.04 + scan * 0.02);",
        "    if ((x + y + Math.floor(phase * 11.0)) % 9 === 0) {",
        "      color = mixColor(color, ACCENT, 0.03);",
        "    }",
        "    if (y === 0 || y === H - 1) {",
        "      color = mixColor(color, BG_DARK, 0.16);",
        "    }",
        "    return color;",
        "  }",
        "",
        "  function sampleTextColor(x, y, flash, unitIndex) {",
        "    const nx = W <= 1 ? 0.5 : x / (W - 1);",
        "    const ny = H <= 1 ? 0.5 : y / (H - 1);",
        "    const shimmer = 0.5 + 0.5 * Math.sin(nx * 4.8 + ny * 2.4 + unitIndex * 0.7);",
        "    let body = sampleRamp(nx * 0.42 + ny * 0.16 + unitIndex * 0.09 + shimmer * 0.08);",
        "    body = mixColor(body, sampleRamp(0.62 + ny * 0.18), 0.16 + nx * 0.10);",
        "    if (EFFECT === \"pixel_reveal\" || EFFECT === \"sequential_pixel_reveal\") {",
        "      body = mixColor(body, HALO, 0.06 + nx * 0.10 + shimmer * 0.04);",
        "    }",
        "    const peak = mixColor(HALO, [255, 255, 245], 0.18);",
        "    const edgeLift = mixColor(TEXT_EDGE, ACCENT, 0.20 + unitIndex * 0.03 + shimmer * 0.08);",
        "    body = mixColor(body, edgeLift, 0.12);",
        "    return mixColor(body, peak, 0.52 * flash);",
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
        "  const charIndex = Math.floor(frameIndex / FRAMES_PER_CHAR);",
        "  const localFrame = frameIndex % FRAMES_PER_CHAR;",
        "  const points = CHAR_POINTS[charIndex] || [];",
        "  const pointTotal = points.length || 1;",
        "  let revealProgress = 0.0;",
        "  let fadeAlpha = 1.0;",
        "  if (localFrame < REVEAL_FRAMES) {",
        "    revealProgress = localFrame / REVEAL_FRAMES;",
        "  } else if (localFrame < REVEAL_FRAMES + HOLD_FRAMES) {",
        "    revealProgress = 1.0;",
        "  } else if (localFrame < REVEAL_FRAMES + HOLD_FRAMES + FADE_FRAMES) {",
        "    revealProgress = 1.0;",
        "    fadeAlpha = 1.0 - (localFrame - REVEAL_FRAMES - HOLD_FRAMES) / FADE_FRAMES;",
        "  } else {",
        "    revealProgress = 0.0;",
        "    fadeAlpha = 0.0;",
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
        "  if (fadeAlpha <= 0.0 || points.length === 0) {",
        "    return frame;",
        "  }",
        "",
        "  const visibleCount =",
        "    localFrame < REVEAL_FRAMES",
        "      ? Math.max(0, Math.min(points.length, Math.floor(revealProgress * points.length + 0.0001)))",
        "      : points.length;",
        "  const haloBase = ORDER_MODE === \"pseudo_random\" ? 0.10 : 0.08;",
        "  for (let index = 0; index < visibleCount; index++) {",
        "    const point = points[index];",
        "    const px = point[0];",
        "    const py = point[1];",
        "    if (px < 0 || px >= W || py < 0 || py >= H) continue;",
        "    const activationFrame = Math.floor(index * REVEAL_FRAMES / pointTotal);",
        "    const age = localFrame - activationFrame;",
        "    const flash = age < 0 ? 0 : age >= 3 ? 0 : 1.0 - age / 3.0;",
        "    const haloStrength = fadeAlpha * (haloBase + flash * 0.10);",
        "    const haloColor = scaleColor(mixColor(ACCENT, HALO, 0.58), haloStrength);",
        "    const haloNeighbors = [[px - 1, py], [px + 1, py], [px, py - 1], [px, py + 1]];",
        "    for (let h = 0; h < haloNeighbors.length; h++) {",
        "      const nx = haloNeighbors[h][0];",
        "      const ny = haloNeighbors[h][1];",
        "      if (nx < 0 || nx >= W || ny < 0 || ny >= H) continue;",
        "      frame[ny][nx] = [",
        "        clamp255(frame[ny][nx][0] + haloColor[0]),",
        "        clamp255(frame[ny][nx][1] + haloColor[1]),",
        "        clamp255(frame[ny][nx][2] + haloColor[2]),",
        "      ];",
        "    }",
        "  }",
        "",
        "  for (let index = 0; index < visibleCount; index++) {",
        "    const point = points[index];",
        "    const px = point[0];",
        "    const py = point[1];",
        "    if (px < 0 || px >= W || py < 0 || py >= H) continue;",
        "    const activationFrame = Math.floor(index * REVEAL_FRAMES / pointTotal);",
        "    const age = localFrame - activationFrame;",
        "    const flash = age < 0 ? 0 : age >= 3 ? 0 : 1.0 - age / 3.0;",
        "    let color = sampleTextColor(px, py, flash, charIndex);",
        "    color = scaleColor(color, 0.10 + fadeAlpha * 0.90);",
        "    frame[py][px] = [clamp255(color[0]), clamp255(color[1]), clamp255(color[2])];",
        "  }",
        "",
        "  return frame;",
        "}",
    ]
    return loop_length_frames, "\n".join(lines) + "\n"
def build_local_pixel_reveal_note(
    *,
    text: str,
    background_style: BackgroundStylePreset,
    font_style: FontStylePreset,
    text_effect: TextEffectPreset,
    loop_length_frames: int,
) -> str:
    visible_units = extract_visible_units(text)
    return "\n".join(
        [
            "[LOCAL]",
            "generator: deterministic pixel reveal",
            f"text: {text}",
            "motion: one character at a time, pixel-by-pixel reveal, hold, fade, then next character",
            f"board: {BOARD_WIDTH}x{BOARD_HEIGHT}",
            f"visible_units: {len(visible_units)}",
            "reveal_order: deterministic selected local order",
            f"loop_length_frames: {loop_length_frames}",
            f"background_style: {background_style.name}",
            f"font_style: {font_style.name}",
            f"text_effect: {text_effect.name}",
            "reason: pixel_reveal uses a dedicated local character-by-character builder to preserve one-character cadence and deterministic pixel timing",
        ]
    )
__all__ = [
    "build_local_pixel_reveal_function_code",
    "build_local_pixel_reveal_note",
    "extract_visible_units",
    "PIXEL_REVEAL_EFFECT_NAMES",
    "resolve_pixel_reveal_order_mode",
]

