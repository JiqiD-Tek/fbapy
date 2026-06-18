from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

from backend.app.cloud.service.led.ledword.text_board import render_text_strip
from backend.app.cloud.service.led.ledword.common import resolve_local_palette
from backend.app.cloud.service.led.ledword.core import BOARD_HEIGHT, BOARD_WIDTH
from backend.app.cloud.service.led.ledword.styles import BackgroundStylePreset, FontStylePreset, TextEffectPreset


SCROLL_GAP = 8
BASE_SCROLL_SPEED = 0.42


def build_local_marquee_scroll_reveal_function_code(
    *,
    text: str,
    background_style: BackgroundStylePreset,
    font_style: FontStylePreset,
    text_effect: TextEffectPreset,
    font_path: Path,
    seed: Optional[int],
) -> tuple[int, str]:
    del font_style
    del seed
    strip_render = render_text_strip(
        text,
        font_path=font_path,
    )
    palette = resolve_local_palette(background_style.name)
    loop_span = strip_render.width + BOARD_WIDTH + SCROLL_GAP
    loop_length_frames = int(math.ceil(loop_span / BASE_SCROLL_SPEED)) + 1
    rows_json = json.dumps(strip_render.rows, ensure_ascii=False)
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

    lines = [
        "function renderFrame(audio) {",
        f"  const W = {BOARD_WIDTH};",
        f"  const H = {BOARD_HEIGHT};",
        f"  const STRIP_W = {strip_render.width};",
        f"  const GAP = {SCROLL_GAP};",
        f"  const EFFECT = {effect_name_json};",
        f"  const MASK = {rows_json};",
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
        "  function clamp01(value) {",
        "    value = Number.isFinite(value) ? value : 0;",
        "    return value < 0 ? 0 : value > 1 ? 1 : value;",
        "  }",
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
        "    const wrapped = ((t % 1) + 1) % 1;",
        "    const scaled = wrapped * TEXT_RAMP.length;",
        "    const left = Math.floor(scaled) % TEXT_RAMP.length;",
        "    const right = (left + 1) % TEXT_RAMP.length;",
        "    return mixColor(TEXT_RAMP[left], TEXT_RAMP[right], scaled - Math.floor(scaled));",
        "  }",
        "",
        "  function scaleColor(color, strength) {",
        "    return [color[0] * strength, color[1] * strength, color[2] * strength];",
        "  }",
        "",
        "  function isLit(x, y) {",
        "    if (x < 0 || x >= STRIP_W || y < 0 || y >= H) return false;",
        "    return MASK[y].charCodeAt(x) === 49;",
        "  }",
        "",
        "  function sampleBackground(x, y, phase) {",
        "    const nx = W <= 1 ? 0 : x / (W - 1);",
        "    const ny = H <= 1 ? 0 : y / (H - 1);",
        "    const sweep = 0.5 + 0.5 * Math.sin(phase * Math.PI * 2.0 + nx * 2.7 - ny * 1.6);",
        "    const band = 0.5 + 0.5 * Math.sin(phase * Math.PI * 3.0 + nx * 1.2 + ny * 2.2);",
        "    let color = mixColor(BG_DARK, BG_MID, 0.10 + ny * 0.28);",
        "    color = mixColor(color, BG_LIGHT, 0.02 + sweep * 0.05 + band * 0.03);",
        "    if ((x * 5 + y * 3 + Math.floor(phase * 17.0)) % 19 === 0) {",
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
        "    const shimmer = 0.5 + 0.5 * Math.sin(phase * Math.PI * 2.0 + nx * 4.0 - ny * 2.1);",
        "    const edgeStrength = neighbors >= 4 ? 0.0 : neighbors === 3 ? 0.18 : neighbors === 2 ? 0.40 : 0.62;",
        "    let fill = sampleRamp(nx * 0.36 + ny * 0.24 + shimmer * 0.10);",
        "    fill = mixColor(fill, sampleRamp(0.82 + nx * 0.08), 0.18 + (1.0 - ny) * 0.08);",
        "    fill = mixColor(fill, HALO, 0.08 + shimmer * 0.08);",
        "    const edge = mixColor(TEXT_EDGE, ACCENT, 0.12 + nx * 0.10 + shimmer * 0.06);",
        "    return mixColor(fill, edge, edgeStrength);",
        "  }",
        "",
        "  audio = audio || {};",
        "  const energy = clamp01(audio.energy);",
        "  const bass = clamp01(audio.bass);",
        "  const mid = clamp01(audio.mid);",
        "  const high = clamp01(audio.high);",
        "  const onset = clamp01(audio.onset);",
        "",
        "  if (!renderFrame._state) {",
        "    renderFrame._state = { scroll: 0, pulse: 0, phase: 0, textVariantIndex: Math.floor(Math.random() * TEXT_RAMP.length) };",
        "  }",
        "  const state = renderFrame._state;",
        "  const loopSpan = STRIP_W + W + GAP;",
        "  const speed = 0.42 + energy * 0.34 + bass * 0.16 + onset * 0.22;",
        "  state.scroll = (state.scroll + speed) % loopSpan;",
        "  state.phase += 0.18 + high * 0.06;",
        "  state.pulse = Math.max(state.pulse * 0.74, onset);",
        "",
        "  const scrollX = Math.floor(state.scroll);",
        "  const bodyLevel = 0.54 + energy * 0.24 + bass * 0.08;",
        "  const shimmerLevel = 0.05 + high * 0.12;",
        "  const flashLevel = state.pulse * 0.28;",
        "  const frame = new Array(H);",
        "",
        "  for (let y = 0; y < H; y++) {",
        "    const row = new Array(W);",
        "    for (let x = 0; x < W; x++) {",
        "      const sourceX = scrollX + x - W;",
        "      const lit = isLit(sourceX, y);",
        "      const neighbors =",
        "        (isLit(sourceX - 1, y) ? 1 : 0) +",
        "        (isLit(sourceX + 1, y) ? 1 : 0) +",
        "        (isLit(sourceX, y - 1) ? 1 : 0) +",
        "        (isLit(sourceX, y + 1) ? 1 : 0);",
        "",
        "      let color = sampleBackground(x, y, state.phase);",
        "      if (lit) {",
        "        const wave = 0.92 + 0.08 * Math.sin(state.phase + x * 0.35 + y * 0.26 + mid * Math.PI);",
        "        let textColor = sampleTextColor(x, y, neighbors, state.phase);",
        "        textColor = scaleColor(textColor, (bodyLevel + shimmerLevel + flashLevel) * wave);",
        "        color = textColor;",
        "      } else if (neighbors > 0) {",
        "        const halo = (0.02 + high * 0.03 + onset * 0.02) * (neighbors / 4);",
        "        const glow = scaleColor(mixColor(ACCENT, HALO, 0.55), halo);",
        "        color = [",
        "          clamp255(color[0] + glow[0]),",
        "          clamp255(color[1] + glow[1]),",
        "          clamp255(color[2] + glow[2]),",
        "        ];",
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


def build_local_marquee_scroll_reveal_note(
    *,
    text: str,
    background_style: BackgroundStylePreset,
    font_style: FontStylePreset,
    text_effect: TextEffectPreset,
    loop_length_frames: int,
) -> str:
    return "\n".join(
        [
            "[LOCAL]",
            "generator: deterministic marquee scroll reveal",
            f"text: {text}",
            "motion: full text strip scrolls horizontally across the 29x16 board with a clean loop gap",
            "board: 29x16",
            f"loop_length_frames: {loop_length_frames}",
            f"background_style: {background_style.name}",
            f"font_style: {font_style.name}",
            f"text_effect: {text_effect.name}",
            "reason: marquee scroll now uses the same palette-driven atmosphere as other local styles instead of a flat dark fill",
        ]
    )


__all__ = [
    "build_local_marquee_scroll_reveal_function_code",
    "build_local_marquee_scroll_reveal_note",
]


