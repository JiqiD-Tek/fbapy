from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from backend.app.cloud.service.resource.providers.led.ledword.text_board import render_text_board
from backend.app.cloud.service.resource.providers.led.ledword.core import BOARD_HEIGHT, BOARD_WIDTH
from backend.app.cloud.service.resource.providers.led.ledword.styles import BackgroundStylePreset, FontStylePreset, TextEffectPreset

from .profile import (
    FLIPBOARD_REVEAL_EFFECT_NAMES,
    extract_flipboard_pages,
    resolve_flipboard_reveal_profile,
    resolve_local_flipboard_palette,
)

def build_local_flipboard_reveal_function_code(
    *,
    text: str,
    background_style: BackgroundStylePreset,
    text_effect: TextEffectPreset,
    font_path: Path,
    seed: Optional[int],
) -> tuple[int, str]:
    page_units = extract_flipboard_pages(text)
    if not page_units:
        raise ValueError("flipboard reveal requires at least one visible page")

    page_rows = [
        render_text_board(
            unit,
            font_path=font_path,
        ).rows
        for unit in page_units
    ]
    if not page_rows:
        raise ValueError("flipboard reveal produced no board pages")

    profile = resolve_flipboard_reveal_profile(
        text=text,
        page_units=page_units,
        seed=seed,
    )
    palette = resolve_local_flipboard_palette(background_style)
    blank_rows = ["0" * BOARD_WIDTH for _ in range(BOARD_HEIGHT)]
    state_rows = [blank_rows] + page_rows + [blank_rows]
    states_json = json.dumps(state_rows, ensure_ascii=False)
    units_json = json.dumps(page_units, ensure_ascii=False)
    effect_name_json = json.dumps(text_effect.name)
    orientation_json = json.dumps(profile["orientation"])
    order_json = json.dumps(profile["order"])
    bg_dark_json = json.dumps(palette["bg_dark"])
    bg_mid_json = json.dumps(palette["bg_mid"])
    bg_light_json = json.dumps(palette["bg_light"])
    accent_json = json.dumps(palette["accent"])
    text_main_json = json.dumps(palette["text_main"])
    text_alt_json = json.dumps(palette["text_alt"])
    text_edge_json = json.dumps(palette["text_edge"])
    halo_json = json.dumps(palette["halo"])
    text_ramp_json = json.dumps(palette["text_ramp"])
    flip_highlight_json = json.dumps(palette["flip_highlight"])
    flip_shadow_json = json.dumps(palette["flip_shadow"])

    segment_count = int(profile["segment_count"])
    collapse_frames = int(profile["collapse_frames"])
    expand_frames = int(profile["expand_frames"])
    hold_frames = int(profile["hold_frames"])
    idle_frames = int(profile["idle_frames"])
    frames_per_segment = collapse_frames + expand_frames
    transition_frames = frames_per_segment * segment_count
    frames_per_block = hold_frames + transition_frames + idle_frames
    transition_count = len(state_rows) - 1
    loop_length_frames = frames_per_block * transition_count

    lines = [
        "function renderFrame(audio) {",
        f"  const W = {BOARD_WIDTH};",
        f"  const H = {BOARD_HEIGHT};",
        f"  const EFFECT = {effect_name_json};",
        f"  const STATES = {states_json};",
        f"  const PAGE_UNITS = {units_json};",
        f"  const ORIENTATION = {orientation_json};",
        f"  const ORDER = {order_json};",
        f"  const SEGMENT_COUNT = {segment_count};",
        f"  const COLLAPSE_FRAMES = {collapse_frames};",
        f"  const EXPAND_FRAMES = {expand_frames};",
        f"  const HOLD_FRAMES = {hold_frames};",
        f"  const IDLE_FRAMES = {idle_frames};",
        f"  const FRAMES_PER_SEGMENT = {frames_per_segment};",
        f"  const TRANSITION_FRAMES = {transition_frames};",
        f"  const FRAMES_PER_BLOCK = {frames_per_block};",
        f"  const BLOCK_COUNT = {transition_count};",
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
        f"  const FLIP_HIGHLIGHT = {flip_highlight_json};",
        f"  const FLIP_SHADOW = {flip_shadow_json};",
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
        "  function stateLit(stateIndex, x, y) {",
        "    if (stateIndex < 0 || stateIndex >= STATES.length) return false;",
        "    if (x < 0 || x >= W || y < 0 || y >= H) return false;",
        "    return STATES[stateIndex][y].charCodeAt(x) === 49;",
        "  }",
        "",
        "  function stateNeighborCount(stateIndex, x, y) {",
        "    return",
        "      (stateLit(stateIndex, x - 1, y) ? 1 : 0) +",
        "      (stateLit(stateIndex, x + 1, y) ? 1 : 0) +",
        "      (stateLit(stateIndex, x, y - 1) ? 1 : 0) +",
        "      (stateLit(stateIndex, x, y + 1) ? 1 : 0);",
        "  }",
        "",
        "  function sampleBackground(x, y, phase) {",
        "    const nx = W <= 1 ? 0 : x / (W - 1);",
        "    const ny = H <= 1 ? 0 : y / (H - 1);",
        "    const panelSweep = 0.5 + 0.5 * Math.sin(phase * Math.PI * 1.7 + nx * 2.4 - ny * 1.2);",
        "    const gridBand = ((ORIENTATION === \"columns\" ? x : y) % 2 === 0) ? 0.04 : 0.0;",
        "    let color = mixColor(BG_DARK, BG_MID, 0.16 + ny * 0.34);",
        "    color = mixColor(color, BG_LIGHT, 0.03 + panelSweep * 0.06 + gridBand);",
        "    if ((x + y + Math.floor(phase * 9.0)) % 7 === 0) {",
        "      color = mixColor(color, ACCENT, 0.03);",
        "    }",
        "    return color;",
        "  }",
        "",
        "  function sampleTextColor(stateIndex, x, y, neighbors, phase) {",
        "    const nx = W <= 1 ? 0.5 : x / (W - 1);",
        "    const ny = H <= 1 ? 0.5 : y / (H - 1);",
        "    let edgeStrength = neighbors >= 4 ? 0.0 : neighbors === 3 ? 0.20 : neighbors === 2 ? 0.42 : 0.64;",
        "    let fill = sampleRamp(nx * 0.34 + ny * 0.20 + stateIndex * 0.08);",
        "    const rib = 0.5 + 0.5 * Math.sin(phase * Math.PI * 2.0 + nx * 4.0 + stateIndex * 0.6);",
        "    fill = mixColor(fill, sampleRamp(0.54 + rib * 0.18), 0.20 + (1.0 - nx) * 0.06);",
        "    fill = mixColor(fill, HALO, 0.05 + rib * 0.10);",
        "    const edge = mixColor(TEXT_EDGE, ACCENT, 0.14 + nx * 0.10 + rib * 0.06);",
        "    return mixColor(fill, edge, edgeStrength);",
        "  }",
        "",
        "  function segmentIndexForCell(x, y) {",
        "    const axisSize = ORIENTATION === \"columns\" ? W : H;",
        "    const position = ORIENTATION === \"columns\" ? x : y;",
        "    const rawIndex = Math.floor(position * SEGMENT_COUNT / axisSize);",
        "    const clamped = rawIndex < 0 ? 0 : rawIndex >= SEGMENT_COUNT ? SEGMENT_COUNT - 1 : rawIndex;",
        "    return ORDER === \"forward\" ? clamped : (SEGMENT_COUNT - 1 - clamped);",
        "  }",
        "",
        "  function flipStateForSegment(localFrame, segmentIndex) {",
        "    const startFrame = segmentIndex * FRAMES_PER_SEGMENT;",
        "    const segmentFrame = localFrame - startFrame;",
        "    if (segmentFrame < 0) return { stage: 0, progress: 0.0, flash: 0.0 };",
        "    if (segmentFrame < COLLAPSE_FRAMES) {",
        "      const t = COLLAPSE_FRAMES <= 1 ? 1.0 : segmentFrame / (COLLAPSE_FRAMES - 1);",
        "      return { stage: 1, progress: t, flash: 1.0 - t * 0.35 };",
        "    }",
        "    if (segmentFrame < COLLAPSE_FRAMES + EXPAND_FRAMES) {",
        "      const t = EXPAND_FRAMES <= 1 ? 1.0 : (segmentFrame - COLLAPSE_FRAMES) / (EXPAND_FRAMES - 1);",
        "      return { stage: 2, progress: t, flash: 0.65 - t * 0.35 };",
        "    }",
        "    return { stage: 3, progress: 1.0, flash: 0.0 };",
        "  }",
        "",
        "  function visibilityScale(stage, progress, distance) {",
        "    const compression = 1.0 - progress;",
        "    const threshold = 0.5 * compression * distance;",
        "    return threshold >= 1.0 ? 0.0 : 1.0 - threshold;",
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
        "  const blockIndex = Math.min(BLOCK_COUNT - 1, Math.floor(frameIndex / FRAMES_PER_BLOCK));",
        "  const nextStateIndex = blockIndex + 1;",
        "  const blockFrame = frameIndex % FRAMES_PER_BLOCK;",
        "  const holdDone = Math.max(0, blockFrame - HOLD_FRAMES);",
        "  const inTransition = blockFrame >= HOLD_FRAMES && blockFrame < HOLD_FRAMES + TRANSITION_FRAMES;",
        "  const inIdle = blockFrame >= HOLD_FRAMES + TRANSITION_FRAMES;",
        "",
        "  const frame = new Array(H);",
        "  for (let y = 0; y < H; y++) {",
        "    const row = new Array(W);",
        "    for (let x = 0; x < W; x++) {",
        "      let color = sampleBackground(x, y, phase);",
        "      const segmentIndex = segmentIndexForCell(x, y);",
        "      const flip = inTransition",
        "        ? flipStateForSegment(holdDone, segmentIndex)",
        "        : { stage: 0, progress: 0.0, flash: 0.0 };",
        "      const litOld = stateLit(blockIndex, x, y);",
        "      const litNew = stateLit(nextStateIndex, x, y);",
        "      const coord = ORIENTATION === \"columns\" ? y : x;",
        "      const center = ORIENTATION === \"columns\" ? (H - 1) / 2.0 : (W - 1) / 2.0;",
        "      const distance = Math.abs(coord - center) / Math.max(1.0, center + 0.0001);",
        "",
        "      let lit = blockFrame < HOLD_FRAMES ? litOld : (inIdle ? litNew : litOld);",
        "      let stateForColor = blockFrame < HOLD_FRAMES ? blockIndex : (inIdle ? nextStateIndex : blockIndex);",
        "      let scale = 1.0;",
        "      if (flip.stage === 1) {",
        "        lit = litOld;",
        "        stateForColor = blockIndex;",
        "        scale = visibilityScale(flip.stage, flip.progress, distance);",
        "      } else if (flip.stage === 2) {",
        "        lit = litNew;",
        "        stateForColor = nextStateIndex;",
        "        scale = visibilityScale(flip.stage, 1.0 - flip.progress, distance);",
        "      } else if (flip.stage === 3) {",
        "        lit = litNew;",
        "        stateForColor = nextStateIndex;",
        "        scale = 1.0;",
        "      } else if (inIdle) {",
        "        lit = litNew;",
        "        stateForColor = nextStateIndex;",
        "        scale = 1.0;",
        "      }",
        "",
        "      if (lit && scale > 0.0) {",
        "        const neighbors = stateNeighborCount(stateForColor, x, y);",
        "        let textColor = sampleTextColor(stateForColor, x, y, neighbors, phase);",
        "        textColor = mixColor(textColor, FLIP_HIGHLIGHT, flip.flash * 0.42);",
        "        textColor = mixColor(textColor, FLIP_SHADOW, (1.0 - scale) * 0.38);",
        "        textColor = [textColor[0] * scale, textColor[1] * scale, textColor[2] * scale];",
        "        color = textColor;",
        "      } else if (inTransition && (litOld || litNew)) {",
        "        const flashColor = mixColor(FLIP_SHADOW, FLIP_HIGHLIGHT, flip.flash);",
        "        color = mixColor(color, flashColor, 0.10 + flip.flash * 0.18);",
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
def build_local_flipboard_reveal_note(
    *,
    text: str,
    background_style: BackgroundStylePreset,
    font_style: FontStylePreset,
    text_effect: TextEffectPreset,
    loop_length_frames: int,
    seed: Optional[int],
) -> str:
    page_units = extract_flipboard_pages(text)
    profile = resolve_flipboard_reveal_profile(
        text=text,
        page_units=page_units,
        seed=seed,
    )
    return "\n".join(
        [
            "[LOCAL]",
            "generator: deterministic flipboard reveal",
            f"text: {text}",
            f"motion: segmented {profile['orientation']} flipboard switch with {profile['order']} progression",
            f"board: {BOARD_WIDTH}x{BOARD_HEIGHT}",
            f"pages: {len(page_units)}",
            f"loop_length_frames: {loop_length_frames}",
            f"background_style: {background_style.name}",
            f"font_style: {font_style.name}",
            f"text_effect: {text_effect.name}",
            "reason: flipboard reveal uses a dedicated segmented page-switch generator so mechanical flip timing stays isolated from other effects",
        ]
    )
__all__ = [
    "FLIPBOARD_REVEAL_EFFECT_NAMES",
    "build_local_flipboard_reveal_function_code",
    "build_local_flipboard_reveal_note",
    "extract_flipboard_pages",
    "resolve_flipboard_reveal_profile",
    "resolve_local_flipboard_palette",
]


