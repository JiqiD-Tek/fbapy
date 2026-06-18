from __future__ import annotations

import json
import random
from typing import List

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


REVEAL_FRAMES = 24
HOLD_FRAMES = 10
FADE_FRAMES = 8
BLANK_FRAMES = 4
OUTLINE_WINDOW = 0.42


def build_sequential_outline_scan_reveal_spec() -> LocalEffectSpec:
    return LocalEffectSpec(
        name="sequential_outline_scan_reveal",
        supports=_supports_sequential_outline_scan_reveal,
        build=build_sequential_outline_scan_reveal,
    )


def build_sequential_outline_scan_reveal(context: LocalEffectContext) -> LocalEffectResult:
    units = extract_visible_units(context.text)
    if not units:
        raise ValueError("sequential_outline_scan_reveal requires at least one visible unit")

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
    masks = [rendered.rows for rendered in rendered_units]
    directions = [
        _resolve_unit_direction(unit, seed=context.seed, unit_index=index)
        for index, unit in enumerate(units)
    ]

    palette = resolve_local_palette(context.background_style.name)
    masks_json = json.dumps(masks, ensure_ascii=False)
    directions_json = json.dumps(directions, ensure_ascii=False)
    bg_dark_json = json.dumps(palette["bg_dark"])
    bg_mid_json = json.dumps(palette["bg_mid"])
    bg_light_json = json.dumps(palette["bg_light"])
    accent_json = json.dumps(palette["accent"])
    text_main_json = json.dumps(palette["text_main"])
    text_alt_json = json.dumps(palette["text_alt"])
    text_edge_json = json.dumps(palette["text_edge"])
    halo_json = json.dumps(palette["halo"])
    text_ramp_json = json.dumps(palette["text_ramp"])

    frames_per_unit = REVEAL_FRAMES + HOLD_FRAMES + FADE_FRAMES + BLANK_FRAMES
    loop_length_frames = frames_per_unit * len(units)
    lines = [
        "function renderFrame(audio) {",
        f"  const W = {BOARD_WIDTH};",
        f"  const H = {BOARD_HEIGHT};",
        f"  const MASKS = {masks_json};",
        f"  const DIRECTIONS = {directions_json};",
        f"  const REVEAL_FRAMES = {REVEAL_FRAMES};",
        f"  const HOLD_FRAMES = {HOLD_FRAMES};",
        f"  const FADE_FRAMES = {FADE_FRAMES};",
        f"  const BLANK_FRAMES = {BLANK_FRAMES};",
        f"  const FRAMES_PER_UNIT = {frames_per_unit};",
        f"  const LOOP_FRAMES = {loop_length_frames};",
        f"  const OUTLINE_WINDOW = {OUTLINE_WINDOW:.2f};",
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
        "  function isUnitLit(unitIndex, x, y) {",
        "    if (unitIndex < 0 || unitIndex >= MASKS.length) return false;",
        "    if (x < 0 || x >= W || y < 0 || y >= H) return false;",
        "    return MASKS[unitIndex][y].charCodeAt(x) === 49;",
        "  }",
        "",
        "  function unitNeighborCount(unitIndex, x, y) {",
        "    return",
        "      (isUnitLit(unitIndex, x - 1, y) ? 1 : 0) +",
        "      (isUnitLit(unitIndex, x + 1, y) ? 1 : 0) +",
        "      (isUnitLit(unitIndex, x, y - 1) ? 1 : 0) +",
        "      (isUnitLit(unitIndex, x, y + 1) ? 1 : 0);",
        "  }",
        "",
        "  function isOutlinePixel(unitIndex, x, y) {",
        "    if (!isUnitLit(unitIndex, x, y)) return false;",
        "    return unitNeighborCount(unitIndex, x, y) < 4;",
        "  }",
        "",
        "  function sampleBackground(x, y, phase) {",
        "    const nx = W <= 1 ? 0 : x / (W - 1);",
        "    const ny = H <= 1 ? 0 : y / (H - 1);",
        "    const sweep = 0.5 + 0.5 * Math.sin(phase * Math.PI * 2.0 + nx * 2.8 - ny * 1.5);",
        "    const band = 0.5 + 0.5 * Math.sin(phase * Math.PI * 3.0 + ny * Math.PI * 1.9);",
        "    let color = mixColor(BG_DARK, BG_MID, 0.10 + ny * 0.26);",
        "    color = mixColor(color, BG_LIGHT, 0.02 + sweep * 0.05 + band * 0.02);",
        "    if ((x * 5 + y * 3 + Math.floor(phase * 13.0)) % 17 === 0) {",
        "      color = mixColor(color, ACCENT, 0.03);",
        "    }",
        "    return color;",
        "  }",
        "",
        "  function sampleTextColor(x, y, neighbors, phase) {",
        "    const nx = W <= 1 ? 0.5 : x / (W - 1);",
        "    const ny = H <= 1 ? 0.5 : y / (H - 1);",
        "    const edgeStrength = neighbors >= 4 ? 0.0 : neighbors === 3 ? 0.18 : neighbors === 2 ? 0.42 : 0.68;",
        "    const shimmer = 0.5 + 0.5 * Math.sin(phase * Math.PI * 2.0 + nx * 4.2 - ny * 2.0);",
        "    let fill = sampleRamp(nx * 0.44 + ny * 0.20 + shimmer * 0.08);",
        "    fill = mixColor(fill, sampleRamp(0.56 + nx * 0.10), 0.18);",
        "    let edge = mixColor(TEXT_EDGE, ACCENT, 0.12 + nx * 0.14 + shimmer * 0.06);",
        "    fill = mixColor(fill, HALO, 0.05 + Math.max(0.0, 0.5 - Math.abs(ny - 0.5)) * 0.12);",
        "    return mixColor(fill, edge, edgeStrength);",
        "  }",
        "",
        "  if (!renderFrame._state) {",
        "    renderFrame._state = { frame: 0, textVariantIndex: Math.floor(Math.random() * TEXT_RAMP.length) };",
        "  }",
        "  const state = renderFrame._state;",
        "  const frameIndex = state.frame;",
        "  state.frame = (state.frame + 1) % LOOP_FRAMES;",
        "  const phase = frameIndex / LOOP_FRAMES;",
        "  const unitIndex = Math.floor(frameIndex / FRAMES_PER_UNIT);",
        "  const frameInUnit = frameIndex % FRAMES_PER_UNIT;",
        "  const direction = DIRECTIONS[unitIndex] || \"left_to_right\";",
        "  let revealProgress = 0.0;",
        "  let textAlpha = 0.0;",
        "  let scanActive = false;",
        "  if (frameInUnit < REVEAL_FRAMES) {",
        "    revealProgress = REVEAL_FRAMES <= 1 ? 1.0 : frameInUnit / Math.max(1, REVEAL_FRAMES - 1);",
        "    textAlpha = 1.0;",
        "    scanActive = true;",
        "  } else if (frameInUnit < REVEAL_FRAMES + HOLD_FRAMES) {",
        "    revealProgress = 1.0;",
        "    textAlpha = 1.0;",
        "  } else if (frameInUnit < REVEAL_FRAMES + HOLD_FRAMES + FADE_FRAMES) {",
        "    const fadeFrame = frameInUnit - REVEAL_FRAMES - HOLD_FRAMES;",
        "    revealProgress = 1.0;",
        "    textAlpha = 1.0 - (FADE_FRAMES <= 1 ? 1.0 : fadeFrame / Math.max(1, FADE_FRAMES - 1));",
        "  }",
        "  const scanHead = direction === \"top_to_bottom\"",
        "    ? mix(-2.0, H + 1.0, revealProgress)",
        "    : mix(-2.0, W + 1.0, revealProgress);",
        "  const frame = new Array(H);",
        "  for (let y = 0; y < H; y++) {",
        "    const row = new Array(W);",
        "    for (let x = 0; x < W; x++) {",
        "      let color = sampleBackground(x, y, phase);",
        "      const coord = direction === \"top_to_bottom\" ? y : x;",
        "      if (scanActive) {",
        "        const bandGlow = Math.max(0.0, 1.0 - Math.abs(coord - scanHead) / 2.4);",
        "        color = mixColor(color, mixColor(ACCENT, HALO, 0.55), bandGlow * 0.12);",
        "      }",
        "      if (textAlpha > 0.0 && isUnitLit(unitIndex, x, y)) {",
        "        const outlinePixel = isOutlinePixel(unitIndex, x, y);",
        "        const visible = coord <= scanHead && (outlinePixel || revealProgress >= OUTLINE_WINDOW);",
        "        if (visible) {",
        "          const neighbors = unitNeighborCount(unitIndex, x, y);",
        "          const headBoost = scanActive ? Math.max(0.0, 1.0 - Math.abs(coord - scanHead) / 1.6) : 0.0;",
        "          let textColor = sampleTextColor(x, y, neighbors, phase);",
        "          if (outlinePixel) {",
        "            textColor = mixColor(textColor, ACCENT, 0.12 + headBoost * 0.18);",
        "          }",
        "          textColor = mixColor(textColor, HALO, headBoost * 0.22);",
        "          textColor = scaleColor(textColor, textAlpha * (0.82 + headBoost * 0.20));",
        "          color = textColor;",
        "        }",
        "      }",
        "      row[x] = [clamp255(color[0]), clamp255(color[1]), clamp255(color[2])];",
        "    }",
        "    frame[y] = row;",
        "  }",
        "  return frame;",
        "}",
    ]
    directions_preview = ", ".join(directions)
    note = "\n".join(
        [
            "[LOCAL]",
            "generator: sequential outline scan reveal",
            f"text: {context.text}",
            "motion: each visible unit is centered and revealed one by one with an outline-first scan before the interior fills in",
            f"units: {' | '.join(units)}",
            f"unit_directions: {directions_preview}",
            f"board: {BOARD_WIDTH}x{BOARD_HEIGHT}",
            f"shared_font_size: {shared_font_size}",
            f"shared_threshold: {shared_threshold}",
            f"loop_length_frames: {loop_length_frames}",
            f"background_style: {context.background_style.name}",
            f"font_style: {context.font_style.name}",
            f"text_effect: {context.text_effect.name}",
            "constraint: this effect reveals one visible character at a time and ignores spaces while preserving the original letter order",
        ]
    )
    return LocalEffectResult(
        loop_length_frames=loop_length_frames,
        function_code="\n".join(lines) + "\n",
        note=note,
    )


def _supports_sequential_outline_scan_reveal(context: LocalEffectContext) -> bool:
    return bool(extract_visible_units(context.text)) and supports_text_effect_for_text(
        "sequential_outline_scan_reveal",
        context.text,
    )


def _resolve_unit_direction(unit: str, *, seed: int | None, unit_index: int) -> str:
    visible = [char for char in str(unit or "") if not char.isspace()]
    if any(is_latin_character(char) or char.isdigit() for char in visible):
        return "left_to_right"
    rng_seed = derive_seed(seed, 5301 + unit_index * 29) or (
        (unit_index + 1) * 311 + sum(ord(char) for char in visible) * 7
    )
    rng = random.Random(rng_seed)
    return rng.choice(("left_to_right", "top_to_bottom"))


__all__ = [
    "build_sequential_outline_scan_reveal",
    "build_sequential_outline_scan_reveal_spec",
]


