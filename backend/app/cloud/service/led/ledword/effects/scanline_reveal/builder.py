from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from backend.app.cloud.service.led.ledword.text_board import render_text_board
from backend.app.cloud.service.led.ledword.core import BOARD_HEIGHT, BOARD_WIDTH
from backend.app.cloud.service.led.ledword.styles import BackgroundStylePreset, FontStylePreset, TextEffectPreset

from .profile import (
    SCANLINE_REVEAL_EFFECT_NAMES,
    resolve_local_scanline_palette,
    resolve_scanline_reveal_profile,
)

def build_local_scanline_reveal_function_code(
    *,
    text: str,
    background_style: BackgroundStylePreset,
    text_effect: TextEffectPreset,
    font_path: Path,
    seed: Optional[int],
) -> tuple[int, str]:
    board_render = render_text_board(
        text,
        font_path=font_path,
    )
    profile = resolve_scanline_reveal_profile(
        text=text,
        text_effect=text_effect,
        seed=seed,
    )
    palette = resolve_local_scanline_palette(
        background_style=background_style,
        text_effect=text_effect,
    )
    rows_json = json.dumps(board_render.rows, ensure_ascii=False)
    direction_json = json.dumps(profile["direction"])
    bg_dark_json = json.dumps(palette["bg_dark"])
    bg_mid_json = json.dumps(palette["bg_mid"])
    bg_light_json = json.dumps(palette["bg_light"])
    accent_json = json.dumps(palette["accent"])
    text_main_json = json.dumps(palette["text_main"])
    text_alt_json = json.dumps(palette["text_alt"])
    text_edge_json = json.dumps(palette["text_edge"])
    halo_json = json.dumps(palette["halo"])
    text_ramp_json = json.dumps(palette["text_ramp"])
    scan_head_json = json.dumps(palette["scan_head"])
    scan_trail_json = json.dumps(palette["scan_trail"])

    reveal_frames = int(profile["reveal_frames"])
    hold_frames = int(profile["hold_frames"])
    fade_frames = int(profile["fade_frames"])
    blank_frames = int(profile["blank_frames"])
    loop_length_frames = reveal_frames + hold_frames + fade_frames + blank_frames

    lines = [
        "function renderFrame(audio) {",
        f"  const W = {BOARD_WIDTH};",
        f"  const H = {BOARD_HEIGHT};",
        f"  const MASK = {rows_json};",
        f"  const DIRECTION = {direction_json};",
        f"  const REVEAL_FRAMES = {reveal_frames};",
        f"  const HOLD_FRAMES = {hold_frames};",
        f"  const FADE_FRAMES = {fade_frames};",
        f"  const BLANK_FRAMES = {blank_frames};",
        f"  const LOOP_FRAMES = {loop_length_frames};",
        f"  const CORE_WIDTH = {float(profile['core_width']):.3f};",
        f"  const TRAIL_WIDTH = {float(profile['trail_width']):.3f};",
        f"  const PANEL_SCAN_STRENGTH = {float(profile['panel_scan_strength']):.3f};",
        f"  const TRAIL_STRENGTH = {float(profile['trail_strength']):.3f};",
        f"  const TEXT_SCAN_BOOST = {float(profile['text_scan_boost']):.3f};",
        f"  const BG_DARK = {bg_dark_json};",
        f"  const BG_MID = {bg_mid_json};",
        f"  const BG_LIGHT = {bg_light_json};",
        f"  const ACCENT = {accent_json};",
        f"  const TEXT_MAIN = {text_main_json};",
        f"  const TEXT_ALT = {text_alt_json};",
        f"  const TEXT_EDGE = {text_edge_json};",
        f"  const HALO = {halo_json};",
        f"  const TEXT_RAMP = {text_ramp_json};",
        f"  const SCAN_HEAD = {scan_head_json};",
        f"  const SCAN_TRAIL = {scan_trail_json};",
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
        "  function isTextLit(x, y) {",
        "    if (x < 0 || x >= W || y < 0 || y >= H) return false;",
        "    return MASK[y].charCodeAt(x) === 49;",
        "  }",
        "",
        "  function textNeighborCount(x, y) {",
        "    return",
        "      (isTextLit(x - 1, y) ? 1 : 0) +",
        "      (isTextLit(x + 1, y) ? 1 : 0) +",
        "      (isTextLit(x, y - 1) ? 1 : 0) +",
        "      (isTextLit(x, y + 1) ? 1 : 0);",
        "  }",
        "",
        "  function sampleBackground(x, y, phase) {",
        "    const nx = W <= 1 ? 0 : x / (W - 1);",
        "    const ny = H <= 1 ? 0 : y / (H - 1);",
        "    const sweep = 0.5 + 0.5 * Math.sin(phase * Math.PI * 2.0 + nx * 2.6 - ny * 1.4);",
        "    const scanBand = 0.5 + 0.5 * Math.sin(phase * Math.PI * 3.0 + ny * Math.PI * 1.8 + nx * 0.9);",
        "    let color = mixColor(BG_DARK, BG_MID, 0.10 + ny * 0.26);",
        "    color = mixColor(color, BG_LIGHT, 0.02 + sweep * 0.05 + scanBand * 0.02);",
        "    if ((x * 5 + y * 3 + Math.floor(phase * 19.0)) % 17 === 0) {",
        "      color = mixColor(color, ACCENT, 0.03);",
        "    }",
        "    if (y === 0 || y === H - 1) {",
        "      color = mixColor(color, BG_DARK, 0.12);",
        "    }",
        "    return color;",
        "  }",
        "",
        "  function sampleTextColor(x, y, neighbors, phase) {",
        "    const nx = W <= 1 ? 0.5 : x / (W - 1);",
        "    const ny = H <= 1 ? 0.5 : y / (H - 1);",
        "    const shimmer = 0.5 + 0.5 * Math.sin(phase * Math.PI * 2.0 + nx * 4.6 - ny * 1.8);",
        "    let edgeStrength = neighbors >= 4 ? 0.0 : neighbors === 3 ? 0.20 : neighbors === 2 ? 0.42 : 0.64;",
        "    let fill = sampleRamp(nx * 0.40 + ny * 0.22 + shimmer * 0.10);",
        "    fill = mixColor(fill, sampleRamp(0.70 + nx * 0.10), 0.18 + (1.0 - ny) * 0.08);",
        "    let edge = mixColor(TEXT_EDGE, ACCENT, 0.18 + nx * 0.10 + shimmer * 0.06);",
        "    fill = mixColor(fill, HALO, 0.06 + nx * 0.05 + shimmer * 0.06);",
        "    return mixColor(fill, edge, edgeStrength);",
        "  }",
        "",
        "  function axisCoord(x, y) {",
        "    return DIRECTION === \"left_to_right\" || DIRECTION === \"right_to_left\" ? x : y;",
        "  }",
        "",
        "  function buildHead(progress) {",
        "    if (DIRECTION === \"left_to_right\") return -2.0 + (W + 3.0) * progress;",
        "    if (DIRECTION === \"right_to_left\") return W + 1.0 - (W + 3.0) * progress;",
        "    if (DIRECTION === \"top_to_bottom\") return -2.0 + (H + 3.0) * progress;",
        "    return H + 1.0 - (H + 3.0) * progress;",
        "  }",
        "",
        "  function hasPassed(coord, head) {",
        "    return DIRECTION === \"left_to_right\" || DIRECTION === \"top_to_bottom\"",
        "      ? coord <= head",
        "      : coord >= head;",
        "  }",
        "",
        "  function behindDistance(coord, head) {",
        "    return DIRECTION === \"left_to_right\" || DIRECTION === \"top_to_bottom\"",
        "      ? head - coord",
        "      : coord - head;",
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
        "  let scanActive = false;",
        "  let revealAll = false;",
        "  let textAlpha = 0.0;",
        "  let head = buildHead(0.0);",
        "  if (frameIndex < REVEAL_FRAMES) {",
        "    const revealProgress = REVEAL_FRAMES <= 1 ? 1.0 : frameIndex / (REVEAL_FRAMES - 1);",
        "    scanActive = true;",
        "    textAlpha = 1.0;",
        "    head = buildHead(revealProgress);",
        "  } else if (frameIndex < REVEAL_FRAMES + HOLD_FRAMES) {",
        "    revealAll = true;",
        "    textAlpha = 1.0;",
        "    head = buildHead(1.0);",
        "  } else if (frameIndex < REVEAL_FRAMES + HOLD_FRAMES + FADE_FRAMES) {",
        "    const fadeFrame = frameIndex - REVEAL_FRAMES - HOLD_FRAMES;",
        "    const fadeProgress = FADE_FRAMES <= 1 ? 1.0 : fadeFrame / (FADE_FRAMES - 1);",
        "    revealAll = true;",
        "    textAlpha = 1.0 - fadeProgress;",
        "    head = buildHead(1.0);",
        "  }",
        "",
        "  const frame = new Array(H);",
        "  for (let y = 0; y < H; y++) {",
        "    const row = new Array(W);",
        "    for (let x = 0; x < W; x++) {",
        "      let color = sampleBackground(x, y, phase);",
        "      const coord = axisCoord(x, y);",
        "      if (scanActive) {",
        "        const absDistance = Math.abs(coord - head);",
        "        const core = Math.max(0.0, 1.0 - absDistance / Math.max(CORE_WIDTH, 0.001));",
        "        const trailDistance = behindDistance(coord, head);",
        "        const trail = trailDistance < 0.0 ? 0.0 : Math.max(0.0, 1.0 - trailDistance / Math.max(TRAIL_WIDTH, 0.001));",
        "        const panelStrength = Math.max(core * PANEL_SCAN_STRENGTH, trail * TRAIL_STRENGTH);",
        "        const panelColor = mixColor(SCAN_TRAIL, SCAN_HEAD, Math.min(1.0, core * 0.84 + trail * 0.16));",
        "        color = mixColor(color, panelColor, panelStrength);",
        "      }",
        "",
        "      if (isTextLit(x, y)) {",
        "        const visible = revealAll || (scanActive && hasPassed(coord, head));",
        "        if (visible && textAlpha > 0.0) {",
        "          const neighbors = textNeighborCount(x, y);",
        "          let textColor = sampleTextColor(x, y, neighbors, phase);",
        "          let scanBoost = 0.0;",
        "          if (scanActive) {",
        "            const absDistance = Math.abs(coord - head);",
        "            const headFlash = Math.max(0.0, 1.0 - absDistance / Math.max(CORE_WIDTH + 0.35, 0.001));",
        "            const trailDistance = behindDistance(coord, head);",
        "            const trailGlow = trailDistance < 0.0 ? 0.0 : Math.max(0.0, 1.0 - trailDistance / Math.max(TRAIL_WIDTH, 0.001));",
        "            scanBoost = Math.max(headFlash, trailGlow * TEXT_SCAN_BOOST);",
        "            textColor = mixColor(textColor, SCAN_HEAD, Math.min(0.78, headFlash * 0.70 + trailGlow * 0.22));",
        "          }",
        "          textColor = scaleColor(textColor, textAlpha * (0.80 + scanBoost * 0.24));",
        "          color = textColor;",
        "        }",
        "      }",
        "",
        "      row[x] = [clamp255(color[0]), clamp255(color[1]), clamp255(color[2])];",
        "    }",
        "    frame[y] = row;",
        "  }",
        "",
        "  return frame;",
        "}",
    ]
    return loop_length_frames, "\n".join(lines) + "\n"
def build_local_scanline_reveal_note(
    *,
    text: str,
    background_style: BackgroundStylePreset,
    font_style: FontStylePreset,
    text_effect: TextEffectPreset,
    loop_length_frames: int,
    seed: Optional[int],
) -> str:
    board_render = render_text_board(
        text,
        font_path=font_style.font_path,
    )
    profile = resolve_scanline_reveal_profile(
        text=text,
        text_effect=text_effect,
        seed=seed,
    )
    return "\n".join(
        [
            "[LOCAL]",
            "generator: deterministic scanline reveal",
            f"text: {text}",
            f"motion: {profile['direction']} scanline reveals the full centered word, holds, then fades cleanly",
            f"board: {BOARD_WIDTH}x{BOARD_HEIGHT}",
            f"lit_pixels: {board_render.lit_pixels}",
            f"font_size_used_for_board_mask: {board_render.font_size}",
            f"loop_length_frames: {loop_length_frames}",
            f"background_style: {background_style.name}",
            f"font_style: {font_style.name}",
            f"text_effect: {text_effect.name}",
            "reason: scanline reveal uses a dedicated local centered-word scanner so direction, trail, and style variants stay isolated from other text effects",
        ]
    )
__all__ = [
    "SCANLINE_REVEAL_EFFECT_NAMES",
    "build_local_scanline_reveal_function_code",
    "build_local_scanline_reveal_note",
    "resolve_local_scanline_palette",
    "resolve_scanline_reveal_profile",
]


