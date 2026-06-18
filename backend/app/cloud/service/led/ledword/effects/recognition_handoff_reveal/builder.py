from __future__ import annotations

import json
import random
import unicodedata
from typing import List, Sequence

from backend.app.cloud.service.led.ledword.text_board import render_text_board, render_text_board_with_font_size
from backend.app.cloud.service.led.ledword.common import (
    derive_seed,
    is_cjk_character,
    is_latin_character,
    mix_rgb,
    recognition_handoff_units,
    resolve_local_palette,
)
from backend.app.cloud.service.led.ledword.core import BOARD_HEIGHT, BOARD_WIDTH
from backend.app.cloud.service.led.ledword.effects._shared.centered_reveal_runtime import (
    LocalEffectContext,
    LocalEffectResult,
    LocalEffectSpec,
)


MIN_VISIBLE_CHARS = 2
STANDARD_HOLD_FRAMES = 28
LOOP_RESTART_HOLD_FRAMES = 60
TRANSITION_NAMES = (
    "particle_scatter_gather",
    "energy_inhale_burst",
    "continuous_scan_replace",
    "linear_compress_stretch",
    "wave_carry_replace",
    "flash_break_stamp",
    "column_flip_replace",
)
TRANSITION_FRAMES = (50, 50, 80, 50, 50, 50, 50)


def build_recognition_handoff_reveal_spec() -> LocalEffectSpec:
    return LocalEffectSpec(
        name="recognition_handoff_reveal",
        supports=_supports_recognition_handoff_reveal,
        build=build_recognition_handoff_reveal,
    )


def build_recognition_handoff_reveal(context: LocalEffectContext) -> LocalEffectResult:
    units = recognition_handoff_units(context.text)
    if len(units) < MIN_VISIBLE_CHARS:
        raise ValueError(
            "recognition_handoff_reveal requires at least {0} display units; got {1}".format(
                MIN_VISIBLE_CHARS,
                len(units),
            )
        )

    unit_anchor_texts = [_display_anchor_text(unit) for unit in units]
    initial_renders = [
        render_text_board(
            unit,
            font_path=context.font_path,
            anchor_text=unit_anchor_texts[index],
        )
        for index, unit in enumerate(units)
    ]
    shared_font_size = min(rendered.font_size for rendered in initial_renders)
    shared_threshold = _shared_threshold_for_units(units, initial_renders)
    rendered_units = [
        render_text_board_with_font_size(
            unit,
            font_path=context.font_path,
            font_size=shared_font_size,
            threshold=shared_threshold,
            anchor_text=unit_anchor_texts[index],
        )
        for index, unit in enumerate(units)
    ]
    masks = [rendered.rows for rendered in rendered_units]
    unit_points = [_rows_to_points(rows) for rows in masks]

    rng_seed = derive_seed(context.seed, 7601)
    if rng_seed is None:
        rng_seed = (
            sum(ord(char) for char in context.text)
            + len(context.text_effect.name) * 131
            + len(context.background_style.name) * 17
        )
    transition_order_seed = derive_seed(context.seed, 8621)
    if transition_order_seed is None:
        transition_order_seed = random.SystemRandom().randrange(1, 1 << 31)

    center_orders = [
        _order_points_from_center(points, rng=random.Random(rng_seed + 97 * index + 1))
        for index, points in enumerate(unit_points)
    ]
    axis_orders = [_sort_points(points, mode="center_x") for points in unit_points]
    boxes = [_bounding_box(points) for points in unit_points]
    transition_template_order = _build_transition_template_order(
        len(units),
        rng_seed=transition_order_seed,
    )

    transition_specs: List[List[int]] = []
    pair_maps: List[List[List[int]]] = []
    for index in range(len(units)):
        from_index = index
        to_index = (index + 1) % len(units)
        template_index = transition_template_order[index]
        pair_rng = random.Random(rng_seed + 271 * index + 17)
        pair_maps.append(
            _build_transition_pairs(
                unit_points[from_index],
                unit_points[to_index],
                rng=pair_rng,
                source_mode="y_then_x",
                target_mode="y_then_x",
            )
        )
        transition_specs.append(
            [
                template_index,
                from_index,
                to_index,
                TRANSITION_FRAMES[template_index],
            ]
        )

    loop_length_frames = (
        max(0, len(units) - 1) * STANDARD_HOLD_FRAMES
        + LOOP_RESTART_HOLD_FRAMES
        + sum(transition[3] for transition in transition_specs)
    )

    palette = _build_contrast_palette(resolve_local_palette(context.background_style.name))
    units_json = json.dumps(units, ensure_ascii=False)
    masks_json = json.dumps(masks, ensure_ascii=False)
    points_json = json.dumps(unit_points, ensure_ascii=False)
    center_orders_json = json.dumps(center_orders, ensure_ascii=False)
    axis_orders_json = json.dumps(axis_orders, ensure_ascii=False)
    boxes_json = json.dumps(boxes, ensure_ascii=False)
    pair_maps_json = json.dumps(pair_maps, ensure_ascii=False)
    transition_specs_json = json.dumps(transition_specs, ensure_ascii=False)
    transition_names_json = json.dumps(TRANSITION_NAMES, ensure_ascii=False)
    bg_dark_json = json.dumps(palette["bg_dark"])
    bg_mid_json = json.dumps(palette["bg_mid"])
    bg_light_json = json.dumps(palette["bg_light"])
    accent_json = json.dumps(palette["accent"])
    text_main_json = json.dumps(palette["text_main"])
    text_alt_json = json.dumps(palette["text_alt"])
    text_edge_json = json.dumps(palette["text_edge"])
    halo_json = json.dumps(palette["halo"])
    text_ramp_json = json.dumps(palette["text_ramp"])

    function_code = f"""function renderFrame(audio) {{
  const W = {BOARD_WIDTH};
  const H = {BOARD_HEIGHT};
  const CENTER_X = (W - 1) / 2.0;
  const CENTER_Y = (H - 1) / 2.0;
  const UNITS = {units_json};
  const MASKS = {masks_json};
  const POINTS = {points_json};
  const CENTER_ORDERS = {center_orders_json};
  const AXIS_ORDERS = {axis_orders_json};
  const BOXES = {boxes_json};
  const PAIR_MAPS = {pair_maps_json};
  const TRANSITIONS = {transition_specs_json};
  const TRANSITION_NAMES = {transition_names_json};
  const LATIN_WORD_MODE = {json.dumps(_units_are_latin_word_group(units))};
  const STANDARD_HOLD_FRAMES = {STANDARD_HOLD_FRAMES};
  const LOOP_RESTART_HOLD_FRAMES = {LOOP_RESTART_HOLD_FRAMES};
  const LOOP_FRAMES = {loop_length_frames};
  const BG_DARK = {bg_dark_json};
  const BG_MID = {bg_mid_json};
  const BG_LIGHT = {bg_light_json};
  const ACCENT = {accent_json};
  const TEXT_MAIN = {text_main_json};
  const TEXT_ALT = {text_alt_json};
  const TEXT_EDGE = {text_edge_json};
  const HALO = {halo_json};
  const TEXT_RAMP = {text_ramp_json};

  function clamp255(value) {{
    value = Math.round(value);
    return value < 0 ? 0 : value > 255 ? 255 : value;
  }}

  function clamp01(value) {{
    return value < 0 ? 0 : value > 1 ? 1 : value;
  }}

  function easeOutCubic(value) {{
    value = clamp01(value);
    return 1 - Math.pow(1 - value, 3);
  }}

  function easeInCubic(value) {{
    value = clamp01(value);
    return value * value * value;
  }}

  function easeInOutCubic(value) {{
    value = clamp01(value);
    if (value < 0.5) {{
      return 4 * value * value * value;
    }}
    return 1 - Math.pow(-2 * value + 2, 3) / 2;
  }}

  function mix(a, b, t) {{
    return a + (b - a) * t;
  }}

  function mixColor(a, b, t) {{
    return [mix(a[0], b[0], t), mix(a[1], b[1], t), mix(a[2], b[2], t)];
  }}

  function sampleRamp(t) {{
    const index = state && Number.isInteger(state.textVariantIndex) ? state.textVariantIndex % TEXT_RAMP.length : 0;
    return TEXT_RAMP[index];
  }}

  function plot(frame, x, y, color, alpha) {{
    if (alpha <= 0) return;
    x = Math.round(x);
    y = Math.round(y);
    if (x < 0 || x >= W || y < 0 || y >= H) return;
    const base = frame[y][x];
    frame[y][x] = [
      clamp255(mix(base[0], color[0], alpha)),
      clamp255(mix(base[1], color[1], alpha)),
      clamp255(mix(base[2], color[2], alpha)),
    ];
  }}

  function maskLit(maskIndex, x, y) {{
    if (maskIndex < 0 || maskIndex >= MASKS.length) return false;
    if (x < 0 || x >= W || y < 0 || y >= H) return false;
    return MASKS[maskIndex][y].charCodeAt(x) === 49;
  }}

  function neighborCount(maskIndex, x, y) {{
    return (
      (maskLit(maskIndex, x - 1, y) ? 1 : 0) +
      (maskLit(maskIndex, x + 1, y) ? 1 : 0) +
      (maskLit(maskIndex, x, y - 1) ? 1 : 0) +
      (maskLit(maskIndex, x, y + 1) ? 1 : 0)
    );
  }}

  function stableNoise(valueA, valueB, salt) {{
    const raw = Math.sin(valueA * 12.9898 + valueB * 78.233 + salt * 37.719) * 43758.5453;
    return raw - Math.floor(raw);
  }}

  function sampleBackground(x, y, phase) {{
    const nx = W <= 1 ? 0 : x / (W - 1);
    const ny = H <= 1 ? 0 : y / (H - 1);
    const sweep = 0.5 + 0.5 * Math.sin(phase * Math.PI * 2.0 + nx * 3.0 - ny * 1.6);
    const scan = 0.5 + 0.5 * Math.sin(phase * Math.PI * 5.0 + ny * 10.5);
    let color = mixColor(BG_DARK, BG_MID, 0.07 + ny * 0.22);
    color = mixColor(color, BG_LIGHT, 0.02 + sweep * 0.035);
    color = mixColor(color, ACCENT, 0.006 + scan * 0.012);
    return color;
  }}

  function sampleGlyphColor(maskIndex, x, y, phase, accentMix) {{
    const nx = W <= 1 ? 0.5 : x / (W - 1);
    const ny = H <= 1 ? 0.5 : y / (H - 1);
    const shimmer = 0.5 + 0.5 * Math.sin(phase * Math.PI * 2.0 + nx * 4.1 - ny * 2.2);
    const crossGlow = 0.5 + 0.5 * Math.sin(phase * Math.PI * 1.5 + nx * 2.6 + ny * 3.4);
    const neighbors = neighborCount(maskIndex, x, y);
    const edgeStrength = neighbors >= 4 ? 0.0 : neighbors === 3 ? 0.12 : neighbors === 2 ? 0.28 : 0.42;
    let fill = sampleRamp(nx * 0.38 + ny * 0.18 + accentMix * 0.20 + shimmer * 0.08);
    fill = mixColor(fill, sampleRamp(0.62 + crossGlow * 0.20), 0.16 + accentMix * 0.10);
    fill = mixColor(fill, HALO, 0.22 + accentMix * 0.10 + shimmer * 0.04);
    fill = mixColor(fill, [255, 255, 255], LATIN_WORD_MODE ? 0.12 : 0.08);
    let edge = mixColor(TEXT_EDGE, ACCENT, 0.08 + nx * 0.12 + accentMix * 0.14 + crossGlow * 0.04);
    return mixColor(fill, edge, edgeStrength);
  }}

  function applyBackgroundFlash(frame, amount) {{
    if (amount <= 0) return;
    const flashColor = mixColor(BG_LIGHT, HALO, 0.52);
    for (let y = 0; y < H; y++) {{
      for (let x = 0; x < W; x++) {{
        const base = frame[y][x];
        frame[y][x] = [
          clamp255(mix(base[0], flashColor[0], amount)),
          clamp255(mix(base[1], flashColor[1], amount)),
          clamp255(mix(base[2], flashColor[2], amount)),
        ];
      }}
    }}
  }}

  function drawGlow(frame, x, y, color, alpha) {{
    plot(frame, x, y, color, alpha);
    const bleed = LATIN_WORD_MODE ? 0.10 : 0.22;
    plot(frame, x - 1, y, color, alpha * bleed);
    plot(frame, x + 1, y, color, alpha * bleed);
    plot(frame, x, y - 1, color, alpha * bleed);
    plot(frame, x, y + 1, color, alpha * bleed);
  }}

  function drawStableMask(frame, maskIndex, alpha, phase, accentMix) {{
    const points = POINTS[maskIndex];
    const bodyAlpha = LATIN_WORD_MODE ? Math.max(alpha, 0.98) : Math.max(alpha, 0.94);
    for (let index = 0; index < points.length; index++) {{
      const point = points[index];
      const x = point[0];
      const y = point[1];
      const color = sampleGlyphColor(maskIndex, x, y, phase, accentMix);
      plot(frame, x, y, color, bodyAlpha);
      if (neighborCount(maskIndex, x, y) < 4) {{
        const haloColor = mixColor(ACCENT, HALO, 0.56);
        const edgeHalo = LATIN_WORD_MODE ? 0.03 : 0.08;
        plot(frame, x - 1, y, haloColor, bodyAlpha * edgeHalo);
        plot(frame, x + 1, y, haloColor, bodyAlpha * edgeHalo);
        plot(frame, x, y - 1, haloColor, bodyAlpha * edgeHalo);
        plot(frame, x, y + 1, haloColor, bodyAlpha * edgeHalo);
      }}
    }}
  }}

  function drawVerticalLine(frame, x, color, alpha) {{
    for (let y = 0; y < H; y++) {{
      plot(frame, x, y, color, alpha);
      plot(frame, x - 1, y, color, alpha * 0.18);
      plot(frame, x + 1, y, color, alpha * 0.18);
    }}
  }}

  function normalizeBox(box) {{
    const x0 = Math.max(0, Math.min(W - 1, Math.round(Math.min(box[0], box[2]))));
    const y0 = Math.max(0, Math.min(H - 1, Math.round(Math.min(box[1], box[3]))));
    const x1 = Math.max(x0, Math.min(W - 1, Math.round(Math.max(box[0], box[2]))));
    const y1 = Math.max(y0, Math.min(H - 1, Math.round(Math.max(box[1], box[3]))));
    return [x0, y0, x1, y1];
  }}

  function mixBoxes(boxA, boxB, t) {{
    return normalizeBox([
      mix(boxA[0], boxB[0], t),
      mix(boxA[1], boxB[1], t),
      mix(boxA[2], boxB[2], t),
      mix(boxA[3], boxB[3], t),
    ]);
  }}

  function drawBoxOutline(frame, box, color, alpha) {{
    box = normalizeBox(box);
    for (let x = box[0]; x <= box[2]; x++) {{
      plot(frame, x, box[1], color, alpha);
      plot(frame, x, box[3], color, alpha);
    }}
    for (let y = box[1]; y <= box[3]; y++) {{
      plot(frame, box[0], y, color, alpha);
      plot(frame, box[2], y, color, alpha);
    }}
  }}

  function remapPointToBox(point, sourceBox, targetBox) {{
    const sxSpan = Math.max(1, sourceBox[2] - sourceBox[0]);
    const sySpan = Math.max(1, sourceBox[3] - sourceBox[1]);
    const txSpan = Math.max(1, targetBox[2] - targetBox[0]);
    const tySpan = Math.max(1, targetBox[3] - targetBox[1]);
    const nx = (point[0] - sourceBox[0]) / sxSpan;
    const ny = (point[1] - sourceBox[1]) / sySpan;
    return [
      targetBox[0] + nx * txSpan,
      targetBox[1] + ny * tySpan,
    ];
  }}

  function drawBoxMappedMask(frame, maskIndex, sourceBox, targetBox, alpha, phase, accentMix) {{
    const points = POINTS[maskIndex];
    for (let index = 0; index < points.length; index++) {{
      const point = points[index];
      const mapped = remapPointToBox(point, sourceBox, targetBox);
      const color = sampleGlyphColor(maskIndex, point[0], point[1], phase, accentMix);
      plot(frame, mapped[0], mapped[1], color, alpha);
    }}
  }}

  function drawScaledMask(frame, maskIndex, scale, alpha, phase, accentMix) {{
    const points = POINTS[maskIndex];
    for (let index = 0; index < points.length; index++) {{
      const point = points[index];
      const px = CENTER_X + (point[0] - CENTER_X) * scale;
      const py = CENTER_Y + (point[1] - CENTER_Y) * scale;
      const color = sampleGlyphColor(maskIndex, point[0], point[1], phase, accentMix);
      plot(frame, px, py, color, alpha);
    }}
  }}

  function drawParticleScatterGather(frame, transitionIndex, fromIndex, toIndex, frameInSection, sectionFrames, phase) {{
    const progress = easeInOutCubic(sectionFrames <= 1 ? 1 : frameInSection / (sectionFrames - 1));
    const pairs = PAIR_MAPS[transitionIndex];
    for (let index = 0; index < pairs.length; index++) {{
      const pair = pairs[index];
      const sx = pair[0];
      const sy = pair[1];
      const tx = pair[2];
      const ty = pair[3];
      let dx = sx - CENTER_X;
      let dy = sy - CENTER_Y;
      const length = Math.max(0.001, Math.sqrt(dx * dx + dy * dy));
      dx /= length;
      dy /= length;
      const orbit = stableNoise(index + sx, sy, 11) * Math.PI * 2.0;
      const scatterDistance = 2.5 + stableNoise(index, tx + ty, 19) * 4.5;
      const scatterX = sx + dx * scatterDistance + Math.cos(orbit + phase * 0.6) * 0.9;
      const scatterY = sy + dy * (scatterDistance * 0.65) + Math.sin(orbit + phase * 0.8) * 0.8;
      let px = sx;
      let py = sy;
      let alpha = 0.76;
      if (progress < 0.42) {{
        const local = easeOutCubic(progress / 0.42);
        px = mix(sx, scatterX, local);
        py = mix(sy, scatterY, local);
        alpha = 0.22 + (1.0 - local) * 0.54;
      }} else if (progress < 0.66) {{
        const local = (progress - 0.42) / 0.24;
        px = scatterX + Math.sin(frameInSection * 0.55 + index) * (0.7 + local * 0.2);
        py = scatterY + Math.cos(frameInSection * 0.45 + index * 1.7) * (0.5 + local * 0.1);
        alpha = 0.20 + (0.5 + 0.5 * Math.sin(frameInSection * 0.9 + orbit)) * 0.26;
      }} else {{
        const local = easeOutCubic((progress - 0.66) / 0.34);
        const jitter = 1.0 - local;
        px = mix(scatterX, tx, local) + ((((index + frameInSection) % 3) - 1) * jitter);
        py = mix(scatterY, ty, local) + ((((index * 2 + frameInSection) % 3) - 1) * jitter);
        alpha = 0.40 + local * 0.60;
      }}
      const useTarget = progress >= 0.66;
      const color = mixColor(
        sampleGlyphColor(useTarget ? toIndex : fromIndex, useTarget ? tx : sx, useTarget ? ty : sy, phase, 0.18 + progress * 0.18),
        ACCENT,
        useTarget ? (0.12 + progress * 0.12) : (0.16 + progress * 0.18)
      );
      plot(frame, px, py, color, alpha);
    }}
    const sparkleCount = Math.max(4, Math.floor((1.0 - Math.abs(progress - 0.5) * 2.0) * 10));
    for (let index = 0; index < sparkleCount; index++) {{
      const px = stableNoise(frameInSection + index, progress, 29) * (W - 1);
      const py = stableNoise(progress, frameInSection + index, 41) * (H - 1);
      const glow = mixColor(ACCENT, HALO, stableNoise(px, py, 37));
      drawGlow(frame, px, py, glow, 0.05 + (0.5 - Math.abs(progress - 0.5)) * 0.18);
    }}
  }}

  function drawEnergyInhaleBurst(frame, transitionIndex, fromIndex, toIndex, frameInSection, sectionFrames, phase) {{
    const progress = easeInOutCubic(sectionFrames <= 1 ? 1 : frameInSection / (sectionFrames - 1));
    const inhale = clamp01(progress / 0.38);
    const burst = clamp01((progress - 0.58) / 0.42);
    const sourcePoints = POINTS[fromIndex];
    const revealPoints = CENTER_ORDERS[toIndex];
    if (progress < 0.62) {{
      for (let index = 0; index < sourcePoints.length; index++) {{
        const point = sourcePoints[index];
        const order = sourcePoints.length <= 1 ? 0 : index / (sourcePoints.length - 1);
        if (inhale < order * 0.18) {{
          plot(frame, point[0], point[1], sampleGlyphColor(fromIndex, point[0], point[1], phase, 0.16), 0.56);
          continue;
        }}
        const local = clamp01((inhale - order * 0.18) / 0.82);
        const px = mix(point[0], CENTER_X, easeInCubic(local));
        const py = mix(point[1], CENTER_Y, easeInCubic(local));
        const color = mixColor(sampleGlyphColor(fromIndex, point[0], point[1], phase, 0.18 + local * 0.10), HALO, 0.14 + local * 0.18);
        plot(frame, px, py, color, 0.24 + (1.0 - local) * 0.54);
      }}
    }}
    const charge = clamp01((progress - 0.38) / 0.20);
    const blink = 0.55 + 0.45 * Math.sin((frameInSection + phase * 7.0) * 1.3);
    const centerColor = mixColor(HALO, ACCENT, 0.26 + blink * 0.32);
    drawGlow(frame, CENTER_X, CENTER_Y, centerColor, 0.18 + inhale * 0.36 + charge * 0.22);
    if (progress >= 0.52) {{
      for (let index = 0; index < revealPoints.length; index++) {{
        const point = revealPoints[index];
        const threshold = revealPoints.length <= 1 ? 0 : index / (revealPoints.length - 1);
        if (burst < threshold) continue;
      const local = clamp01((burst - threshold) / Math.max(0.001, 1.0 - threshold));
      const px = mix(CENTER_X, point[0], easeOutCubic(local));
      const py = mix(CENTER_Y, point[1], easeOutCubic(local));
      const haloMix = LATIN_WORD_MODE ? (0.04 + (1.0 - local) * 0.05) : (0.10 + (1.0 - local) * 0.10);
      const color = mixColor(sampleGlyphColor(toIndex, point[0], point[1], phase, 0.18 + local * 0.16), HALO, haloMix);
      plot(frame, px, py, color, 0.42 + local * 0.58);
      }}
    }}
  }}

  function drawContinuousScanReplace(frame, transitionIndex, fromIndex, toIndex, frameInSection, sectionFrames, phase) {{
    const progress = easeInOutCubic(sectionFrames <= 1 ? 1 : frameInSection / (sectionFrames - 1));
    const erasePhase = clamp01(progress / 0.5);
    const revealPhase = clamp01((progress - 0.5) / 0.5);
    const eraseBeamX = mix(-4, W + 3, erasePhase);
    const revealBeamX = mix(W + 3, -4, revealPhase);
    const oldPoints = POINTS[fromIndex];
    const newPoints = POINTS[toIndex];
    for (let index = 0; index < oldPoints.length; index++) {{
      const point = oldPoints[index];
      if (progress < 0.5) {{
        if (point[0] <= eraseBeamX + 0.4) continue;
        const color = sampleGlyphColor(fromIndex, point[0], point[1], phase, 0.14 + erasePhase * 0.08);
        plot(frame, point[0], point[1], color, 0.94 - erasePhase * 0.20);
      }}
    }}
    for (let index = 0; index < newPoints.length; index++) {{
      const point = newPoints[index];
      if (progress < 0.5) continue;
      if (point[0] <= revealBeamX - 0.4) continue;
      const color = mixColor(
        sampleGlyphColor(toIndex, point[0], point[1], phase, 0.18 + revealPhase * 0.12),
        HALO,
        LATIN_WORD_MODE ? 0.03 : 0.08
      );
      plot(frame, point[0], point[1], color, 0.46 + revealPhase * 0.54);
    }}
    for (let y = 0; y < H; y++) {{
      const beamColor = mixColor(ACCENT, HALO, 0.50);
      const beamX = progress < 0.5 ? eraseBeamX : revealBeamX;
      plot(frame, beamX, y, beamColor, 0.24);
      plot(frame, beamX - 1, y, beamColor, 0.10);
      plot(frame, beamX + 1, y, beamColor, 0.10);
    }}
  }}

  function drawLinearCompressStretch(frame, transitionIndex, fromIndex, toIndex, frameInSection, sectionFrames, phase) {{
    const progress = easeInOutCubic(sectionFrames <= 1 ? 1 : frameInSection / (sectionFrames - 1));
    const compress = clamp01(progress / 0.46);
    const stretch = clamp01((progress - 0.62) / 0.38);
    const sourcePoints = POINTS[fromIndex];
    const targetPoints = AXIS_ORDERS[toIndex];
    const centerLineColor = mixColor(HALO, ACCENT, 0.42 + compress * 0.10);
    if (progress < 0.62) {{
      for (let index = 0; index < sourcePoints.length; index++) {{
        const point = sourcePoints[index];
        const px = mix(point[0], CENTER_X, easeInOutCubic(compress));
        const color = mixColor(sampleGlyphColor(fromIndex, point[0], point[1], phase, 0.18 + compress * 0.12), HALO, 0.12 + compress * 0.12);
        plot(frame, px, point[1], color, 0.22 + (1.0 - compress) * 0.58);
      }}
      drawGlow(frame, CENTER_X, CENTER_Y, centerLineColor, 0.04 + compress * 0.10);
      return;
    }}
    drawGlow(frame, CENTER_X, CENTER_Y, centerLineColor, 0.05 + (1.0 - stretch) * 0.08);
    for (let index = 0; index < targetPoints.length; index++) {{
      const point = targetPoints[index];
      const threshold = targetPoints.length <= 1 ? 0 : index / (targetPoints.length - 1);
      if (stretch < threshold * 0.86) continue;
      const local = clamp01((stretch - threshold * 0.86) / Math.max(0.001, 1.0 - threshold * 0.86));
      const px = mix(CENTER_X, point[0], easeOutCubic(local));
      const py = point[1] + Math.sin(index + frameInSection * 0.6) * (1.0 - local) * 0.45;
      const haloMix = LATIN_WORD_MODE ? (0.04 + (1.0 - local) * 0.05) : (0.10 + (1.0 - local) * 0.10);
      const color = mixColor(sampleGlyphColor(toIndex, point[0], point[1], phase, 0.18 + local * 0.14), HALO, haloMix);
      plot(frame, px, py, color, 0.40 + local * 0.60);
    }}
  }}

  function drawWaveCarryReplace(frame, transitionIndex, fromIndex, toIndex, frameInSection, sectionFrames, phase) {{
    const progress = easeInOutCubic(sectionFrames <= 1 ? 1 : frameInSection / (sectionFrames - 1));
    const baseY = mix(H + 3, -3, progress);
    const amplitude = 1.3;
    const band = 1.1;
    const oldPoints = POINTS[fromIndex];
    const newPoints = POINTS[toIndex];
    for (let index = 0; index < oldPoints.length; index++) {{
      const point = oldPoints[index];
      const waveY = baseY + Math.sin(point[0] * 0.62 + phase * 8.0) * amplitude;
      const distance = waveY - point[1];
      if (distance <= band) continue;
      const alpha = clamp01(distance / (band + 2.6)) * (0.88 - progress * 0.10);
      const color = sampleGlyphColor(fromIndex, point[0], point[1], phase, 0.16 + progress * 0.08);
      plot(frame, point[0], point[1], color, Math.max(0.42, alpha));
    }}
    for (let index = 0; index < newPoints.length; index++) {{
      const point = newPoints[index];
      const waveY = baseY + Math.sin(point[0] * 0.62 + phase * 8.0) * amplitude;
      const distance = waveY - point[1];
      if (distance >= -band) continue;
      const alpha = clamp01((-distance - band) / 2.8) * (0.28 + progress * 0.68);
      const color = mixColor(
        sampleGlyphColor(toIndex, point[0], point[1], phase, 0.16 + progress * 0.16),
        HALO,
        LATIN_WORD_MODE ? 0.04 : 0.10
      );
      plot(frame, point[0], point[1], color, alpha);
    }}
    for (let x = 0; x < W; x++) {{
      const waveY = baseY + Math.sin(x * 0.62 + phase * 8.0) * amplitude;
      const beamColor = mixColor(ACCENT, HALO, 0.48);
      plot(frame, x, waveY, beamColor, 0.18);
      plot(frame, x, waveY - 1, beamColor, 0.08);
      plot(frame, x, waveY + 1, beamColor, 0.08);
    }}
  }}

  function drawFlashBreakStamp(frame, transitionIndex, fromIndex, toIndex, frameInSection, sectionFrames, phase) {{
    const progress = clamp01(sectionFrames <= 1 ? 1 : frameInSection / (sectionFrames - 1));
    const flash = clamp01(progress / 0.20);
    const snap = clamp01((progress - 0.18) / 0.16);
    const stamp = clamp01((progress - 0.48) / 0.52);
    if (progress < 0.44) {{
      applyBackgroundFlash(frame, 0.16 + flash * 0.34);
      const oldPoints = POINTS[fromIndex];
      for (let index = 0; index < oldPoints.length; index++) {{
        const point = oldPoints[index];
        const drop = stableNoise(point[0] + frameInSection, point[1], 43) < snap * 1.08;
        if (drop) continue;
        const color = mixColor(HALO, sampleGlyphColor(fromIndex, point[0], point[1], phase, 0.18), 0.36);
        plot(frame, point[0], point[1], color, 0.74);
      }}
    }}
    const centerPulse = progress < 0.48 ? 0.22 + (0.48 - progress) * 0.46 : 0.18 + (1.0 - stamp) * 0.10;
    drawGlow(frame, CENTER_X, CENTER_Y, mixColor(HALO, ACCENT, 0.44), centerPulse);
    if (progress >= 0.48) {{
      let scale = 1.0;
      if (stamp < 0.72) {{
        scale = mix(0.38, 1.14, easeOutCubic(stamp / 0.72));
      }} else {{
        scale = mix(1.14, 1.0, easeInOutCubic((stamp - 0.72) / 0.28));
      }}
      drawScaledMask(frame, toIndex, scale, 0.18 + stamp * 0.82, phase, 0.16 + stamp * 0.18);
    }}
  }}

  function drawContainerBoxSwitch(frame, transitionIndex, fromIndex, toIndex, frameInSection, sectionFrames, phase) {{
    const progress = easeInOutCubic(sectionFrames <= 1 ? 1 : frameInSection / (sectionFrames - 1));
    const fromBox = BOXES[fromIndex];
    const toBox = BOXES[toIndex];
    const closedBox = normalizeBox([CENTER_X - 1, CENTER_Y - 1, CENTER_X + 1, CENTER_Y + 1]);
    const boxColor = mixColor(ACCENT, HALO, 0.48);
    if (progress < 0.62) {{
      const closePhase = easeInOutCubic(progress / 0.62);
      const currentBox = mixBoxes(fromBox, closedBox, closePhase);
      drawBoxOutline(frame, currentBox, boxColor, 0.22 + (1.0 - closePhase) * 0.42);
      drawBoxMappedMask(frame, fromIndex, fromBox, currentBox, 0.18 + (1.0 - closePhase) * 0.68, phase, 0.16 + closePhase * 0.10);
      return;
    }}
    const openPhase = easeOutCubic((progress - 0.62) / 0.38);
    const currentBox = mixBoxes(closedBox, toBox, openPhase);
    drawBoxOutline(frame, currentBox, boxColor, 0.24 + (1.0 - openPhase) * 0.18);
    drawBoxMappedMask(frame, toIndex, toBox, currentBox, 0.16 + openPhase * 0.84, phase, 0.16 + openPhase * 0.16);
    drawGlow(frame, CENTER_X, CENTER_Y, mixColor(HALO, ACCENT, 0.34), 0.08 + (1.0 - openPhase) * 0.14);
  }}

  function drawColumnFlipReplace(frame, transitionIndex, fromIndex, toIndex, frameInSection, sectionFrames, phase) {{
    const progress = clamp01(sectionFrames <= 1 ? 1 : frameInSection / (sectionFrames - 1));
    const oldPoints = POINTS[fromIndex];
    const newPoints = POINTS[toIndex];
    const left = Math.min(BOXES[fromIndex][0], BOXES[toIndex][0]);
    const right = Math.max(BOXES[fromIndex][2], BOXES[toIndex][2]);
    const span = Math.max(1, right - left);
    for (let index = 0; index < oldPoints.length; index++) {{
      const point = oldPoints[index];
      const columnOffset = (point[0] - left) / span;
      const local = clamp01((progress - columnOffset * 0.48) / 0.52);
      if (local >= 0.5) continue;
      const fold = 1.0 - local / 0.5;
      const py = CENTER_Y + (point[1] - CENTER_Y) * (0.16 + fold * 0.84);
      const color = sampleGlyphColor(fromIndex, point[0], point[1], phase, 0.14 + local * 0.10);
      plot(frame, point[0], py, color, 0.16 + fold * 0.72);
    }}
    for (let index = 0; index < newPoints.length; index++) {{
      const point = newPoints[index];
      const columnOffset = (point[0] - left) / span;
      const local = clamp01((progress - columnOffset * 0.48) / 0.52);
      if (local <= 0.5) continue;
      const reveal = (local - 0.5) / 0.5;
      const py = CENTER_Y + (point[1] - CENTER_Y) * (0.16 + reveal * 0.84);
      const color = mixColor(
        sampleGlyphColor(toIndex, point[0], point[1], phase, 0.18 + reveal * 0.12),
        HALO,
        LATIN_WORD_MODE ? 0.03 : 0.08
      );
      plot(frame, point[0], py, color, 0.40 + reveal * 0.60);
    }}
    for (let x = left; x <= right; x++) {{
      const columnOffset = (x - left) / span;
      const local = clamp01((progress - columnOffset * 0.48) / 0.52);
      if (Math.abs(local - 0.5) > 0.14) continue;
      const seamAlpha = 0.24 - Math.abs(local - 0.5) * 1.2;
      drawVerticalLine(frame, x, mixColor(ACCENT, HALO, 0.54), Math.max(0, seamAlpha));
    }}
  }}

  function renderTransition(frame, transitionIndex, templateIndex, fromIndex, toIndex, frameInSection, sectionFrames, phase) {{
    switch (templateIndex) {{
      case 0:
        drawParticleScatterGather(frame, transitionIndex, fromIndex, toIndex, frameInSection, sectionFrames, phase);
        return;
      case 1:
        drawEnergyInhaleBurst(frame, transitionIndex, fromIndex, toIndex, frameInSection, sectionFrames, phase);
        return;
      case 2:
        drawContinuousScanReplace(frame, transitionIndex, fromIndex, toIndex, frameInSection, sectionFrames, phase);
        return;
      case 3:
        drawLinearCompressStretch(frame, transitionIndex, fromIndex, toIndex, frameInSection, sectionFrames, phase);
        return;
      case 4:
        drawWaveCarryReplace(frame, transitionIndex, fromIndex, toIndex, frameInSection, sectionFrames, phase);
        return;
      case 5:
        drawFlashBreakStamp(frame, transitionIndex, fromIndex, toIndex, frameInSection, sectionFrames, phase);
        return;
      case 6:
        drawColumnFlipReplace(frame, transitionIndex, fromIndex, toIndex, frameInSection, sectionFrames, phase);
        return;
      default:
        drawColumnFlipReplace(frame, transitionIndex, fromIndex, toIndex, frameInSection, sectionFrames, phase);
        return;
    }}
  }}

  if (!renderFrame._state) {{
    renderFrame._state = {{ frame: 0, textVariantIndex: Math.floor(Math.random() * TEXT_RAMP.length) }};
  }}

  const state = renderFrame._state;
  const frameIndex = state.frame;
  state.frame = (state.frame + 1) % LOOP_FRAMES;
  const phase = LOOP_FRAMES <= 1 ? 0.0 : frameIndex / Math.max(1, LOOP_FRAMES - 1);

  const frame = new Array(H);
  for (let y = 0; y < H; y++) {{
    const row = new Array(W);
    for (let x = 0; x < W; x++) {{
      const bg = sampleBackground(x, y, phase);
      row[x] = [clamp255(bg[0]), clamp255(bg[1]), clamp255(bg[2])];
    }}
    frame[y] = row;
  }}

  let cursor = 0;
  for (let index = 0; index < TRANSITIONS.length; index++) {{
    const transition = TRANSITIONS[index];
    const templateIndex = transition[0];
    const fromIndex = transition[1];
    const toIndex = transition[2];
    const sectionFrames = transition[3];
    const holdFrames = index === TRANSITIONS.length - 1 ? LOOP_RESTART_HOLD_FRAMES : STANDARD_HOLD_FRAMES;
    if (frameIndex < cursor + holdFrames) {{
      drawStableMask(frame, fromIndex, 1.0, phase, 0.10);
      return frame;
    }}
    cursor += holdFrames;
    if (frameIndex < cursor + sectionFrames) {{
      renderTransition(frame, index, templateIndex, fromIndex, toIndex, frameIndex - cursor, sectionFrames, phase);
      return frame;
    }}
    cursor += sectionFrames;
  }}

  drawStableMask(frame, 0, 1.0, phase, 0.10);
  return frame;
}}
"""

    template_preview = ", ".join(TRANSITION_NAMES[transition[0]] for transition in transition_specs)
    transition_seed_label = str(context.seed) if context.seed is not None else "auto"
    note = "\n".join(
        [
            "[LOCAL]",
            "generator: seed-shuffled recognition handoff reveal",
            f"text: {context.text}",
            "motion: adjacent characters hand off through seven template transitions including particle full-shatter then regroup, energy inhale burst, bidirectional scan replace, stretch morph, wave carry, flash stamp, and column flip",
            "timing: each character holds longer before handoff, and the final character pauses noticeably longer before the loop restarts",
            f"units: {' | '.join(units)}",
            f"board: {BOARD_WIDTH}x{BOARD_HEIGHT}",
            f"loop_length_frames: {loop_length_frames}",
            f"shared_font_size: {shared_font_size}",
            f"shared_threshold: {shared_threshold}",
            f"standard_hold_frames: {STANDARD_HOLD_FRAMES}",
            f"loop_restart_hold_frames: {LOOP_RESTART_HOLD_FRAMES}",
            f"transition_order_seed: {transition_seed_label}",
            f"transition_templates: {template_preview}",
            f"background_style: {context.background_style.name}",
            f"font_style: {context.font_style.name}",
            f"text_effect: {context.text_effect.name}",
            "constraint: this effect requires at least 2 display units, shuffles the seven template transitions per loop while keeping seeded runs reproducible, and keeps punctuation attached to the neighboring unit while centering the main glyph",
        ]
    )
    return LocalEffectResult(
        loop_length_frames=loop_length_frames,
        function_code=function_code.rstrip() + "\n",
        note=note,
    )


def _supports_recognition_handoff_reveal(context: LocalEffectContext) -> bool:
    count = len(recognition_handoff_units(context.text))
    return count >= MIN_VISIBLE_CHARS


def _display_anchor_text(unit: str) -> str:
    normalized = str(unit or "").strip()
    if len(normalized) <= 1:
        return normalized

    start = 0
    end = len(normalized)
    while start < end - 1 and _is_punctuation_affix_char(normalized[start]):
        start += 1
    while end > start + 1 and _is_punctuation_affix_char(normalized[end - 1]):
        end -= 1

    anchored = normalized[start:end].strip()
    return anchored or normalized


def _is_punctuation_affix_char(char: str) -> bool:
    if not char or char.isspace():
        return False
    if is_cjk_character(char) or is_latin_character(char) or char.isdigit():
        return False
    return unicodedata.category(char).startswith("P")


def _shared_threshold_for_units(
    units: Sequence[str],
    rendered_units: Sequence[object],
) -> int:
    if not rendered_units:
        return 72
    thresholds = [max(0, min(255, int(getattr(rendered, "threshold", 72)))) for rendered in rendered_units]
    if _units_are_latin_word_group(units):
        return max(64, min(112, int(round(sum(thresholds) / float(len(thresholds)))) + 8))
    return min(thresholds)


def _units_are_latin_word_group(units: Sequence[str]) -> bool:
    if len(units) < 2:
        return False
    has_latin_signal = False
    for unit in units:
        if not unit:
            return False
        for char in unit:
            if is_cjk_character(char):
                return False
            if is_latin_character(char) or char.isdigit():
                has_latin_signal = True
    return has_latin_signal


def _rows_to_points(rows: Sequence[str]) -> List[List[int]]:
    points: List[List[int]] = []
    for y, row in enumerate(rows):
        for x, value in enumerate(row):
            if value == "1":
                points.append([x, y])
    return points


def _bounding_box(points: Sequence[Sequence[int]]) -> List[int]:
    if not points:
        center_x = int(round((BOARD_WIDTH - 1) / 2.0))
        center_y = int(round((BOARD_HEIGHT - 1) / 2.0))
        return [center_x, center_y, center_x, center_y]
    min_x = min(int(point[0]) for point in points)
    min_y = min(int(point[1]) for point in points)
    max_x = max(int(point[0]) for point in points)
    max_y = max(int(point[1]) for point in points)
    return [
        max(0, min_x - 1),
        max(0, min_y - 1),
        min(BOARD_WIDTH - 1, max_x + 1),
        min(BOARD_HEIGHT - 1, max_y + 1),
    ]


def _sort_points(points: Sequence[Sequence[int]], *, mode: str) -> List[List[int]]:
    center_x = (BOARD_WIDTH - 1) / 2.0
    if mode == "x_then_y":
        return sorted(
            ([int(point[0]), int(point[1])] for point in points),
            key=lambda point: (point[0], point[1]),
        )
    if mode == "center_x":
        return sorted(
            ([int(point[0]), int(point[1])] for point in points),
            key=lambda point: (abs(point[0] - center_x), point[1], point[0]),
        )
    if mode == "diag":
        return sorted(
            ([int(point[0]), int(point[1])] for point in points),
            key=lambda point: (point[0] + point[1], point[1], point[0]),
        )
    return sorted(
        ([int(point[0]), int(point[1])] for point in points),
        key=lambda point: (point[1], point[0]),
    )


def _order_points_from_center(points: Sequence[Sequence[int]], *, rng: random.Random) -> List[List[int]]:
    center_x = (BOARD_WIDTH - 1) / 2.0
    center_y = (BOARD_HEIGHT - 1) / 2.0
    ranked = []
    for point in points:
        x = int(point[0])
        y = int(point[1])
        distance = (x - center_x) * (x - center_x) + (y - center_y) * (y - center_y)
        ranked.append((distance, rng.random(), y, x, [x, y]))
    ranked.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
    return [item[4] for item in ranked]


def _build_transition_template_order(transition_count: int, *, rng_seed: int) -> List[int]:
    order: List[int] = []
    template_indices = list(range(len(TRANSITION_NAMES)))
    rng = random.Random(rng_seed)
    while len(order) < transition_count:
        chunk = list(template_indices)
        rng.shuffle(chunk)
        if order and chunk and chunk[0] == order[-1]:
            for swap_index in range(1, len(chunk)):
                if chunk[swap_index] != order[-1]:
                    chunk[0], chunk[swap_index] = chunk[swap_index], chunk[0]
                    break
        order.extend(chunk[: transition_count - len(order)])
    return order


def _build_transition_pairs(
    source_points: Sequence[Sequence[int]],
    target_points: Sequence[Sequence[int]],
    *,
    rng: random.Random,
    source_mode: str,
    target_mode: str,
) -> List[List[int]]:
    if not source_points or not target_points:
        return []
    ordered_source = _sort_points(source_points, mode=source_mode)
    ordered_target = _sort_points(target_points, mode=target_mode)
    count = max(len(ordered_source), len(ordered_target))
    pairs: List[List[int]] = []
    for index in range(count):
        sx, sy = ordered_source[index % len(ordered_source)]
        tx, ty = ordered_target[index % len(ordered_target)]
        if rng.random() < 0.25:
            tx, ty = ordered_target[(index * 3 + 1) % len(ordered_target)]
        pairs.append([sx, sy, tx, ty])
    return pairs


def _build_contrast_palette(base_palette: dict[str, List[int]]) -> dict[str, List[int]]:
    bg_dark = mix_rgb(base_palette["bg_dark"], [0, 0, 0], 0.28)
    bg_mid = mix_rgb(base_palette["bg_mid"], bg_dark, 0.34)
    bg_light = mix_rgb(base_palette["bg_light"], base_palette["bg_mid"], 0.22)
    accent = mix_rgb(base_palette["accent"], [255, 255, 255], 0.10)
    text_main = mix_rgb(base_palette["text_main"], [255, 255, 255], 0.22)
    text_alt = mix_rgb(base_palette["text_alt"], [255, 255, 255], 0.16)
    text_edge = mix_rgb(base_palette["text_edge"], bg_dark, 0.22)
    halo = mix_rgb(base_palette["halo"], [255, 255, 255], 0.16)
    base_ramp = base_palette.get("text_ramp")
    if base_ramp:
        text_ramp = [mix_rgb(color, [255, 255, 255], 0.10) for color in base_ramp]
    else:
        text_ramp = [
            text_main,
            mix_rgb(text_main, accent, 0.42),
            mix_rgb(text_main, text_alt, 0.58),
            text_alt,
            mix_rgb(text_alt, halo, 0.40),
            mix_rgb(accent, halo, 0.58),
            halo,
        ]
    return {
        "bg_dark": bg_dark,
        "bg_mid": bg_mid,
        "bg_light": bg_light,
        "accent": accent,
        "text_main": text_main,
        "text_alt": text_alt,
        "text_edge": text_edge,
        "halo": halo,
        "text_ramp": text_ramp,
    }


__all__ = [
    "build_recognition_handoff_reveal",
    "build_recognition_handoff_reveal_spec",
]


