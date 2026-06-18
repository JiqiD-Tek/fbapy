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
from .profile import build_star_gather_spec_for_points


def build_local_star_gather_reveal_function_code(
    *,
    text: str,
    background_style: BackgroundStylePreset,
    text_effect: TextEffectPreset,
    font_path: Path,
    seed: Optional[int],
) -> tuple[int, str]:
    visible_units = extract_visible_units(text)
    if not visible_units:
        raise ValueError("star gather reveal requires at least one visible character")

    char_points = [
        build_ordered_pixel_points_for_unit(
            unit,
            font_path=font_path,
            order_mode="center_out",
            unit_index=unit_index,
            seed=seed,
        )
        for unit_index, unit in enumerate(visible_units)
    ]
    if not all(points for points in char_points):
        raise ValueError("star gather reveal produced an empty character sprite")

    gather_specs = [
        build_star_gather_spec_for_points(
            points,
            unit_index=unit_index,
            seed=seed,
        )
        for unit_index, points in enumerate(char_points)
    ]

    palette = resolve_local_four_way_palette(background_style)
    units_json = json.dumps(visible_units, ensure_ascii=False)
    gather_specs_json = json.dumps(gather_specs, ensure_ascii=False)
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

    gather_frames = 28
    hold_frames = 12
    fade_frames = 10
    gap_frames = 4
    frames_per_char = gather_frames + hold_frames + fade_frames + gap_frames
    loop_length_frames = frames_per_char * len(visible_units)

    lines = [
        "function renderFrame(audio) {",
        f"  const W = {BOARD_WIDTH};",
        f"  const H = {BOARD_HEIGHT};",
        f"  const EFFECT = {effect_name_json};",
        f"  const UNITS = {units_json};",
        f"  const GATHER_SPECS = {gather_specs_json};",
        f"  const GATHER_FRAMES = {gather_frames};",
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
        "  function sampleSpectrum(t) {",
        "    const angle = (((t % 1) + 1) % 1) * Math.PI * 2.0;",
        "    return [",
        "      128 + 127 * Math.sin(angle),",
        "      128 + 127 * Math.sin(angle + 2.09439510239),",
        "      128 + 127 * Math.sin(angle + 4.18879020479),",
        "    ];",
        "  }",
        "",
        "  function sampleBackground(x, y, phase) {",
        "    const nx = W <= 1 ? 0 : x / (W - 1);",
        "    const ny = H <= 1 ? 0 : y / (H - 1);",
        "    const sweep = 0.5 + 0.5 * Math.sin(phase * Math.PI * 2.0 + nx * 2.4 - ny * 1.3);",
        "    const starBand = 0.5 + 0.5 * Math.sin(phase * Math.PI * 3.0 + nx * 5.0 + ny * 2.4);",
        "    let color = mixColor(BG_DARK, BG_MID, 0.10 + ny * 0.26);",
        "    color = mixColor(color, BG_LIGHT, 0.02 + sweep * 0.05 + starBand * 0.02);",
        "    if ((x * 3 + y * 5 + Math.floor(phase * 17.0)) % 19 === 0) {",
        "      color = mixColor(color, ACCENT, 0.04);",
        "    }",
        "    return color;",
        "  }",
        "",
        "  function sampleTextColor(x, y, twinkle, unitIndex) {",
        "    const nx = W <= 1 ? 0.5 : x / (W - 1);",
        "    const ny = H <= 1 ? 0.5 : y / (H - 1);",
        "    const drift = 0.5 + 0.5 * Math.sin(nx * 5.1 + ny * 2.0 + unitIndex * 0.8);",
        "    let base = sampleRamp(nx * 0.44 + ny * 0.24 + unitIndex * 0.09 + drift * 0.08);",
        "    if (EFFECT === \"star_gather_reveal\") {",
        "      const sparkle = sampleRamp(0.58 + drift * 0.22 + twinkle * 0.08);",
        "      base = mixColor(base, sparkle, 0.12 + twinkle * 0.08);",
        "      base = mixColor(base, HALO, 0.08 + twinkle * 0.14);",
        "    }",
        "    return base;",
        "  }",
        "",
        "  function plot(frame, x, y, color) {",
        "    if (x < 0 || x >= W || y < 0 || y >= H) return;",
        "    frame[y][x] = [",
        "      clamp255(color[0]),",
        "      clamp255(color[1]),",
        "      clamp255(color[2]),",
        "    ];",
        "  }",
        "",
        "  function addGlow(frame, x, y, color, strength) {",
        "    const neighbors = [[x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1]];",
        "    for (let i = 0; i < neighbors.length; i++) {",
        "      const nx = neighbors[i][0];",
        "      const ny = neighbors[i][1];",
        "      if (nx < 0 || nx >= W || ny < 0 || ny >= H) continue;",
        "      frame[ny][nx] = [",
        "        clamp255(frame[ny][nx][0] + color[0] * strength),",
        "        clamp255(frame[ny][nx][1] + color[1] * strength),",
        "        clamp255(frame[ny][nx][2] + color[2] * strength),",
        "      ];",
        "    }",
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
        "  const spec = GATHER_SPECS[charIndex] || [];",
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
        "  let gatherProgress = 0.0;",
        "  let textAlpha = 1.0;",
        "  let sparkleTrim = 0.0;",
        "  if (localFrame < GATHER_FRAMES) {",
        "    gatherProgress = localFrame / GATHER_FRAMES;",
        "  } else if (localFrame < GATHER_FRAMES + HOLD_FRAMES) {",
        "    gatherProgress = 1.0;",
        "    sparkleTrim = (localFrame - GATHER_FRAMES) / HOLD_FRAMES;",
        "  } else if (localFrame < GATHER_FRAMES + HOLD_FRAMES + FADE_FRAMES) {",
        "    gatherProgress = 1.0;",
        "    sparkleTrim = 1.0;",
        "    textAlpha = 1.0 - (localFrame - GATHER_FRAMES - HOLD_FRAMES) / FADE_FRAMES;",
        "  } else {",
        "    gatherProgress = 0.0;",
        "    sparkleTrim = 0.0;",
        "    textAlpha = 0.0;",
        "  }",
        "",
        "  if (textAlpha <= 0.0 || spec.length === 0) {",
        "    return frame;",
        "  }",
        "",
        "  const lingerCutoff = Math.floor((1.0 - sparkleTrim) * spec.length);",
        "  for (let i = 0; i < spec.length; i++) {",
        "    const item = spec[i];",
        "    const targetX = item[0];",
        "    const targetY = item[1];",
        "    const startX = item[2];",
        "    const startY = item[3];",
        "    const sparkle = item[4];",
        "    const twinklePhase = item[5];",
        "    const cx = Math.round(startX + (targetX - startX) * gatherProgress);",
        "    const cy = Math.round(startY + (targetY - startY) * gatherProgress);",
        "    const proximity = gatherProgress;",
        "    const twinkle = 0.5 + 0.5 * Math.sin(phase * Math.PI * 8.0 + twinklePhase);",
        "    let color = sampleTextColor(targetX, targetY, twinkle, charIndex);",
        "    if (sparkle > 0 && i >= lingerCutoff) {",
        "      color = mixColor(color, sampleSpectrum(twinklePhase / 6.28318), 0.24);",
        "    }",
        "    color = scaleColor(color, textAlpha * (0.50 + 0.50 * proximity + twinkle * 0.12));",
        "    plot(frame, cx, cy, color);",
        "    addGlow(frame, cx, cy, mixColor(ACCENT, HALO, 0.60), textAlpha * (0.05 + twinkle * 0.06));",
        "    if (gatherProgress >= 0.999) {",
        "      plot(frame, targetX, targetY, color);",
        "    }",
        "  }",
        "",
        "  return frame;",
        "}",
    ]
    return loop_length_frames, "\n".join(lines) + "\n"
def build_local_star_gather_reveal_note(
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
            "generator: deterministic star gather reveal",
            f"text: {text}",
            "motion: sparse sparkles appear, converge into text, hold briefly, then clear excess sparkles",
            f"board: {BOARD_WIDTH}x{BOARD_HEIGHT}",
            f"visible_units: {len(visible_units)}",
            f"loop_length_frames: {loop_length_frames}",
            f"background_style: {background_style.name}",
            f"font_style: {font_style.name}",
            f"text_effect: {text_effect.name}",
            "reason: star_gather_reveal uses a dedicated local particle-to-text convergence animation so its timing and sparkle behavior stay isolated from other effects",
        ]
    )
__all__ = [
    "build_local_star_gather_reveal_function_code",
    "build_local_star_gather_reveal_note",
    "build_star_gather_spec_for_points",
]

