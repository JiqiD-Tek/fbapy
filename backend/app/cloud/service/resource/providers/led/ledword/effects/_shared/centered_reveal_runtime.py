from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from backend.app.cloud.service.resource.providers.led.ledword.text_board import render_text_board
from backend.app.cloud.service.resource.providers.led.ledword.common import resolve_local_palette, visible_chars
from backend.app.cloud.service.resource.providers.led.ledword.core import BOARD_HEIGHT, BOARD_WIDTH
from backend.app.cloud.service.resource.providers.led.ledword.styles import (
    BackgroundStylePreset,
    FontStylePreset,
    TextEffectPreset,
    supports_text_effect_for_text,
)


@dataclass(frozen=True)
class LocalEffectContext:
    text: str
    background_style: BackgroundStylePreset
    font_style: FontStylePreset
    text_effect: TextEffectPreset
    font_path: Path
    seed: Optional[int]


@dataclass(frozen=True)
class LocalEffectResult:
    loop_length_frames: int
    function_code: str
    note: str


SupportsFunc = Callable[[LocalEffectContext], bool]
BuildFunc = Callable[[LocalEffectContext], LocalEffectResult]


@dataclass(frozen=True)
class LocalEffectSpec:
    name: str
    supports: SupportsFunc
    build: BuildFunc


@dataclass(frozen=True)
class RevealEffectProfile:
    mode: str
    display_motion: str
    reveal_frames: int
    hold_frames: int
    fade_frames: int
    blank_frames: int
    extra_json: Dict[str, object]


LOCAL_EFFECT_REGISTRY: Dict[str, LocalEffectSpec] = {}


def register_local_effect(spec: LocalEffectSpec) -> None:
    LOCAL_EFFECT_REGISTRY[spec.name] = spec


def resolve_local_effect(context: LocalEffectContext) -> Optional[LocalEffectSpec]:
    spec = LOCAL_EFFECT_REGISTRY.get(context.text_effect.name)
    if spec is None:
        return None
    if not spec.supports(context):
        return None
    return spec


def supports_char_limit(context: LocalEffectContext) -> bool:
    visible = visible_chars(context.text)
    return 0 < len(visible) and supports_text_effect_for_text(
        context.text_effect.name,
        context.text,
    )


def supports_centered_board_mask(context: LocalEffectContext) -> bool:
    if not supports_char_limit(context):
        return False
    try:
        board_render = render_text_board(
            context.text,
            font_path=context.font_path,
        )
    except Exception:
        return False
    return (
        board_render.lit_pixels > 0
        and len(board_render.rows) == BOARD_HEIGHT
        and all(len(row) == BOARD_WIDTH for row in board_render.rows)
    )


def render_centered_mask(context: LocalEffectContext) -> tuple[List[str], int]:
    board_render = render_text_board(
        context.text,
        font_path=context.font_path,
    )
    return board_render.rows, board_render.lit_pixels


def build_generic_reveal_effect(
    context: LocalEffectContext,
    *,
    profile: RevealEffectProfile,
) -> LocalEffectResult:
    rows, lit_pixels = render_centered_mask(context)
    palette = resolve_local_palette(context.background_style.name)
    if profile.mode == "inverse_flash":
        return build_inverse_flash_reveal_effect(
            context,
            rows=rows,
            lit_pixels=lit_pixels,
            palette=palette,
            profile=profile,
        )
    effect_name_json = json.dumps(context.text_effect.name)
    mode_json = json.dumps(profile.mode)
    rows_json = json.dumps(rows, ensure_ascii=False)
    extras_json = json.dumps(profile.extra_json, ensure_ascii=False)
    bg_dark_json = json.dumps(palette["bg_dark"])
    bg_mid_json = json.dumps(palette["bg_mid"])
    bg_light_json = json.dumps(palette["bg_light"])
    accent_json = json.dumps(palette["accent"])
    text_main_json = json.dumps(palette["text_main"])
    text_alt_json = json.dumps(palette["text_alt"])
    text_edge_json = json.dumps(palette["text_edge"])
    halo_json = json.dumps(palette["halo"])
    text_ramp_json = json.dumps(palette["text_ramp"])
    loop_length_frames = (
        profile.reveal_frames + profile.hold_frames + profile.fade_frames + profile.blank_frames
    )
    lines = [
        "function renderFrame(audio) {",
        f"  const W = {BOARD_WIDTH};",
        f"  const H = {BOARD_HEIGHT};",
        f"  const MASK = {rows_json};",
        f"  const EFFECT = {effect_name_json};",
        f"  const MODE = {mode_json};",
        f"  const EXTRAS = {extras_json};",
        f"  const REVEAL_FRAMES = {profile.reveal_frames};",
        f"  const HOLD_FRAMES = {profile.hold_frames};",
        f"  const FADE_FRAMES = {profile.fade_frames};",
        f"  const BLANK_FRAMES = {profile.blank_frames};",
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
        "    const colors = TEXT_RAMP && TEXT_RAMP.length ? TEXT_RAMP : [TEXT_MAIN, TEXT_ALT, ACCENT, HALO];",
        "    const index = state && Number.isInteger(state.textVariantIndex) ? state.textVariantIndex % colors.length : 0;",
        "    return colors[index];",
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
        "  function neighborCount(x, y) {",
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
        "    const shimmer = 0.5 + 0.5 * Math.sin(phase * Math.PI * 2.0 + nx * 4.4 - ny * 2.3);",
        "    const centerGlow = Math.max(0, 1.0 - Math.abs(nx - 0.5) * 1.9);",
        "    let edgeStrength = neighbors >= 4 ? 0.0 : neighbors === 3 ? 0.18 : neighbors === 2 ? 0.42 : 0.68;",
        "    let fill = sampleRamp(nx * 0.46 + ny * 0.18 + shimmer * 0.10);",
        "    fill = mixColor(fill, sampleRamp(nx * 0.12 + 0.38), 0.26 + centerGlow * 0.18);",
        "    let edge = mixColor(TEXT_EDGE, ACCENT, 0.16 + nx * 0.12 + shimmer * 0.06);",
        "    if (MODE === \"glitch\") {",
        "      fill = mixColor(fill, HALO, 0.10 + shimmer * 0.04);",
        "      edge = mixColor(edge, HALO, 0.10);",
        "    } else if (MODE === \"inverse_flash\") {",
        "      fill = mixColor(fill, HALO, 0.06 + nx * 0.08);",
        "    } else if (MODE === \"stamp_pop\") {",
        "      fill = mixColor(fill, HALO, 0.10 + Math.max(0, 0.5 - Math.abs(ny - 0.5)) * 0.25);",
        "    }",
        "    fill = mixColor(fill, HALO, 0.04 + shimmer * 0.08);",
        "    return mixColor(fill, edge, edgeStrength);",
        "  }",
        "",
        "  function revealMetric(x, y) {",
        "    const centerX = (W - 1) / 2.0;",
        "    const centerY = (H - 1) / 2.0;",
        "    if (MODE === \"center_burst\") {",
        "      return Math.sqrt((x - centerX) * (x - centerX) + (y - centerY) * (y - centerY));",
        "    }",
        "    if (MODE === \"stretch\") {",
        "      return Math.abs(x - centerX);",
        "    }",
        "    if (MODE === \"raindrop\") {",
        "      return y;",
        "    }",
        "    if (MODE === \"wave\") {",
        "      const direction = String(EXTRAS.direction || \"bottom_to_top\");",
        "      if (direction === \"left_to_right\") return x;",
        "      return H - 1 - y;",
        "    }",
        "    if (MODE === \"outline_scan\") {",
        "      const direction = String(EXTRAS.direction || \"left_to_right\");",
        "      if (direction === \"top_to_bottom\") return y;",
        "      return x;",
        "    }",
        "    return x + y * W;",
        "  }",
        "",
        "  function isOutlinePixel(x, y) {",
        "    if (!isTextLit(x, y)) return false;",
        "    return neighborCount(x, y) < 4;",
        "  }",
        "",
        "  function plot(frame, x, y, color, alpha) {",
        "    if (x < 0 || x >= W || y < 0 || y >= H) return;",
        "    const base = frame[y][x];",
        "    frame[y][x] = [",
        "      clamp255(mix(base[0], color[0], alpha)),",
        "      clamp255(mix(base[1], color[1], alpha)),",
        "      clamp255(mix(base[2], color[2], alpha)),",
        "    ];",
        "  }",
        "",
        "  if (!renderFrame._state) {",
        "    renderFrame._state = { frame: 0, textVariantIndex: Math.floor(Math.random() * TEXT_RAMP.length) };",
        "  }",
        "  const state = renderFrame._state;",
        "  const frameIndex = state.frame;",
        "  state.frame = (state.frame + 1) % LOOP_FRAMES;",
        "  const phase = frameIndex / LOOP_FRAMES;",
        "  let textAlpha = 0.0;",
        "  let revealProgress = 0.0;",
        "  if (frameIndex < REVEAL_FRAMES) {",
        "    revealProgress = REVEAL_FRAMES <= 1 ? 1.0 : frameIndex / Math.max(1, REVEAL_FRAMES - 1);",
        "    textAlpha = 1.0;",
        "  } else if (frameIndex < REVEAL_FRAMES + HOLD_FRAMES) {",
        "    revealProgress = 1.0;",
        "    textAlpha = 1.0;",
        "  } else if (frameIndex < REVEAL_FRAMES + HOLD_FRAMES + FADE_FRAMES) {",
        "    revealProgress = 1.0;",
        "    const fadeFrame = frameIndex - REVEAL_FRAMES - HOLD_FRAMES;",
        "    textAlpha = 1.0 - (FADE_FRAMES <= 1 ? 1.0 : fadeFrame / Math.max(1, FADE_FRAMES - 1));",
        "  }",
        "  const frame = new Array(H);",
        "  for (let y = 0; y < H; y++) {",
        "    const row = new Array(W);",
        "    for (let x = 0; x < W; x++) {",
        "      const bg = sampleBackground(x, y, phase);",
        "      row[x] = [clamp255(bg[0]), clamp255(bg[1]), clamp255(bg[2])];",
        "    }",
        "    frame[y] = row;",
        "  }",
        "  if (textAlpha <= 0.0) {",
        "    return frame;",
        "  }",
        "  const maxDistance = Math.sqrt(W * W + H * H);",
        "  const lineThreshold = mix(0.0, (W - 1) / 2.0 + 1.0, revealProgress);",
        "  const radiusThreshold = mix(0.0, maxDistance, revealProgress);",
        "  const dropThreshold = mix(-3.0, H + 2.0, revealProgress);",
        "  const waveDirection = String(EXTRAS.direction || \"bottom_to_top\");",
        "  const waveHead = waveDirection === \"left_to_right\" ? mix(-3.0, W + 2.0, revealProgress) : mix(H + 2.0, -3.0, revealProgress);",
        "  const waveWidth = Number(EXTRAS.wave_width || 3.0);",
        "  const flashFrames = Number(EXTRAS.flash_frames || 4);",
        "  const glitchStride = Number(EXTRAS.pulse_stride || 13);",
        "  const jitter = Number(EXTRAS.jitter || 2);",
        "  const boxMargin = Number(EXTRAS.box_margin || 1);",
        "  const centerX = (W - 1) / 2.0;",
        "  const centerY = (H - 1) / 2.0;",
        "  const maxBoxHalfW = (W + 1) / 2.0;",
        "  const maxBoxHalfH = (H + 1) / 2.0;",
        "  const boxHalfW = mix(2.0, maxBoxHalfW, revealProgress);",
        "  const boxHalfH = mix(1.0, maxBoxHalfH, revealProgress);",
        "  const stampPulse = MODE === \"stamp_pop\" ? Math.max(0.0, 1.0 - frameIndex / Math.max(1, REVEAL_FRAMES)) : 0.0;",
        "  for (let y = 0; y < H; y++) {",
        "    for (let x = 0; x < W; x++) {",
        "      const lit = isTextLit(x, y);",
        "      const neighbors = neighborCount(x, y);",
        "      if (MODE === \"box_open\") {",
        "        const left = Math.max(0, Math.floor(centerX - boxHalfW));",
        "        const right = Math.min(W - 1, Math.ceil(centerX + boxHalfW));",
        "        const top = Math.max(0, Math.floor(centerY - boxHalfH));",
        "        const bottom = Math.min(H - 1, Math.ceil(centerY + boxHalfH));",
        "        const isFrame = x >= left && x <= right && y >= top && y <= bottom && (x === left || x === right || y === top || y === bottom);",
        "        if (isFrame) {",
        "          const frameColor = mixColor(ACCENT, HALO, 0.40 + revealProgress * 0.28);",
        "          plot(frame, x, y, frameColor, 0.55 + textAlpha * 0.25);",
        "        }",
        "      }",
        "      if (!lit) {",
        "        continue;",
        "      }",
        "      let visible = false;",
        "      let localAlpha = textAlpha;",
        "      let drawX = x;",
        "      let drawY = y;",
        "      if (MODE === \"decode\") {",
        "        const decodeCut = Math.floor((x + y * W + frameIndex * 3) % 5);",
        "        const decodeThreshold = decodeCut / 4.0;",
        "        const decodeSettled = revealProgress >= 1.0 || frameIndex >= REVEAL_FRAMES;",
        "        visible = decodeSettled || revealProgress >= decodeThreshold;",
        "        if (!visible && frameIndex < REVEAL_FRAMES) {",
        "          const shiftX = ((x + frameIndex) % (jitter * 2 + 1)) - jitter;",
        "          const shiftY = ((y + frameIndex * 2) % 3) - 1;",
        "          drawX = x + shiftX;",
        "          drawY = y + shiftY;",
        "          visible = true;",
        "          localAlpha = textAlpha * 0.42;",
        "        }",
        "      } else if (MODE === \"glitch\") {",
        "        visible = true;",
        "        const pulse = frameIndex % glitchStride;",
        "        if (pulse < 2 && ((x + y + frameIndex) % 4 === 0)) {",
        "          drawX = x + ((pulse % 2 === 0) ? 1 : -1);",
        "          localAlpha = textAlpha * 0.85;",
        "        } else if (pulse === 3 && ((x * 3 + y) % 7 === 0)) {",
        "          localAlpha = textAlpha * 0.30;",
        "        }",
        "      } else if (MODE === \"center_burst\") {",
        "        visible = revealMetric(x, y) <= radiusThreshold;",
        "      } else if (MODE === \"outline_scan\") {",
        "        const threshold = waveDirection === \"top_to_bottom\" ? mix(-2.0, H + 1.0, revealProgress) : mix(-2.0, W + 1.0, revealProgress);",
        "        const coord = waveDirection === \"top_to_bottom\" ? y : x;",
        "        visible = coord <= threshold && (isOutlinePixel(x, y) || revealProgress >= Number(EXTRAS.outline_window || 0.4));",
        "      } else if (MODE === \"stamp_pop\") {",
        "        visible = true;",
        "        if (stampPulse > 0.0) {",
        "          const dx = x - centerX;",
        "          const dy = y - centerY;",
        "          drawX = Math.round(centerX + dx * (1.0 + stampPulse * Number(EXTRAS.overshoot || 1.6) * 0.35));",
        "          drawY = Math.round(centerY + dy * (1.0 + stampPulse * Number(EXTRAS.overshoot || 1.6) * 0.22));",
        "          localAlpha = textAlpha * (0.70 + stampPulse * 0.30);",
        "        }",
        "      } else if (MODE === \"raindrop\") {",
        "        visible = y <= dropThreshold;",
        "        if (!visible) {",
        "          const dropY = Math.round(dropThreshold);",
        "          if (dropY >= 0 && dropY < H && x === x) {",
        "            const dropColor = mixColor(ACCENT, HALO, 0.55);",
        "            plot(frame, x, dropY, dropColor, 0.55);",
        "          }",
        "        }",
        "      } else if (MODE === \"wave\") {",
        "        const coord = waveDirection === \"left_to_right\" ? x : y;",
        "        const distance = waveDirection === \"left_to_right\" ? Math.abs(coord - waveHead) : Math.abs(coord - waveHead);",
        "        visible = waveDirection === \"left_to_right\" ? coord <= waveHead : coord >= waveHead;",
        "        localAlpha = textAlpha * Math.max(0.28, 1.0 - distance / Math.max(0.001, waveWidth * 3.2));",
        "      } else if (MODE === \"stretch\") {",
        "        visible = Math.abs(x - centerX) <= lineThreshold;",
        "      } else if (MODE === \"box_open\") {",
        "        const left = Math.max(0, Math.floor(centerX - boxHalfW + boxMargin));",
        "        const right = Math.min(W - 1, Math.ceil(centerX + boxHalfW - boxMargin));",
        "        const top = Math.max(0, Math.floor(centerY - boxHalfH + boxMargin));",
        "        const bottom = Math.min(H - 1, Math.ceil(centerY + boxHalfH - boxMargin));",
        "        visible = x >= left && x <= right && y >= top && y <= bottom;",
        "      } else if (MODE === \"inverse_flash\") {",
        "        const flashActive = frameIndex < flashFrames;",
        "        if (flashActive) {",
        "          const inverseColor = mixColor(BG_LIGHT, HALO, 0.42);",
        "          plot(frame, x, y, inverseColor, 0.70);",
        "          visible = false;",
        "        } else {",
        "          visible = true;",
        "        }",
        "      } else {",
        "        visible = true;",
        "      }",
        "      if (!visible) {",
        "        continue;",
        "      }",
        "      let color = sampleTextColor(x, y, neighbors, phase);",
        "      if (MODE === \"glitch\") {",
        "        const pulse = frameIndex % glitchStride;",
        "        if (pulse < 2 && ((x + y + frameIndex) % 3 === 0)) {",
        "          color = mixColor(color, ACCENT, 0.32);",
        "        }",
        "      }",
        "      if (MODE === \"inverse_flash\" && frameIndex >= flashFrames) {",
        "        color = mixColor(color, HALO, 0.10);",
        "      }",
        "      if (MODE === \"center_burst\") {",
        "        const centerBoost = Math.max(0.0, 1.0 - revealMetric(x, y) / Math.max(1.0, radiusThreshold + 0.001));",
        "        color = mixColor(color, HALO, centerBoost * 0.18);",
        "      }",
        "      plot(frame, drawX, drawY, color, Math.max(0.0, Math.min(1.0, localAlpha)));",
        "      if (neighbors < 4) {",
        "        const haloColor = mixColor(ACCENT, HALO, 0.55);",
        "        plot(frame, drawX - 1, drawY, haloColor, localAlpha * 0.10);",
        "        plot(frame, drawX + 1, drawY, haloColor, localAlpha * 0.10);",
        "        plot(frame, drawX, drawY - 1, haloColor, localAlpha * 0.10);",
        "        plot(frame, drawX, drawY + 1, haloColor, localAlpha * 0.10);",
        "      }",
        "    }",
        "  }",
        "  return frame;",
        "}",
    ]
    note = "\n".join(
        [
            "[LOCAL]",
            "generator: deterministic local reveal",
            f"text: {context.text}",
            f"motion: {profile.display_motion}",
            f"board: {BOARD_WIDTH}x{BOARD_HEIGHT}",
            f"lit_pixels: {lit_pixels}",
            f"loop_length_frames: {loop_length_frames}",
            f"background_style: {context.background_style.name}",
            f"font_style: {context.font_style.name}",
            f"text_effect: {context.text_effect.name}",
            "reason: effect uses the local reveal framework so behavior is isolated per design type and easier to extend",
        ]
    )
    return LocalEffectResult(
        loop_length_frames=loop_length_frames,
        function_code="\n".join(lines) + "\n",
        note=note,
    )


def build_inverse_flash_reveal_effect(
    context: LocalEffectContext,
    *,
    rows: List[str],
    lit_pixels: int,
    palette: Dict[str, List[int]],
    profile: RevealEffectProfile,
) -> LocalEffectResult:
    rows_json = json.dumps(rows, ensure_ascii=False)
    extras_json = json.dumps(profile.extra_json, ensure_ascii=False)
    bg_dark_json = json.dumps(palette["bg_dark"])
    bg_mid_json = json.dumps(palette["bg_mid"])
    bg_light_json = json.dumps(palette["bg_light"])
    accent_json = json.dumps(palette["accent"])
    text_main_json = json.dumps(palette["text_main"])
    text_alt_json = json.dumps(palette["text_alt"])
    text_edge_json = json.dumps(palette["text_edge"])
    halo_json = json.dumps(palette["halo"])
    loop_length_frames = (
        profile.reveal_frames + profile.hold_frames + profile.fade_frames + profile.blank_frames
    )
    function_code = f"""function renderFrame(audio) {{
  const W = {BOARD_WIDTH};
  const H = {BOARD_HEIGHT};
  const MASK = {rows_json};
  const EXTRAS = {extras_json};
  const REVEAL_FRAMES = {profile.reveal_frames};
  const HOLD_FRAMES = {profile.hold_frames};
  const FADE_FRAMES = {profile.fade_frames};
  const BLANK_FRAMES = {profile.blank_frames};
  const LOOP_FRAMES = {loop_length_frames};
  const BG_DARK = {bg_dark_json};
  const BG_MID = {bg_mid_json};
  const BG_LIGHT = {bg_light_json};
  const ACCENT = {accent_json};
  const TEXT_MAIN = {text_main_json};
  const TEXT_ALT = {text_alt_json};
  const TEXT_EDGE = {text_edge_json};
  const HALO = {halo_json};

  function clamp255(value) {{
    value = Math.round(value);
    return value < 0 ? 0 : value > 255 ? 255 : value;
  }}

  function mix(a, b, t) {{
    return a + (b - a) * t;
  }}

  function mixColor(a, b, t) {{
    return [mix(a[0], b[0], t), mix(a[1], b[1], t), mix(a[2], b[2], t)];
  }}

  function isTextLit(x, y) {{
    if (x < 0 || x >= W || y < 0 || y >= H) return false;
    return MASK[y].charCodeAt(x) === 49;
  }}

  function neighborCount(x, y) {{
    return
      (isTextLit(x - 1, y) ? 1 : 0) +
      (isTextLit(x + 1, y) ? 1 : 0) +
      (isTextLit(x, y - 1) ? 1 : 0) +
      (isTextLit(x, y + 1) ? 1 : 0);
  }}

  function sampleBackground(x, y, phase) {{
    const nx = W <= 1 ? 0 : x / (W - 1);
    const ny = H <= 1 ? 0 : y / (H - 1);
    const sweep = 0.5 + 0.5 * Math.sin(phase * Math.PI * 2.0 + nx * 2.6 - ny * 1.4);
    const band = 0.5 + 0.5 * Math.cos(phase * Math.PI * 2.0 - ny * Math.PI * 1.7 + nx * 0.8);
    let color = mixColor(BG_DARK, BG_MID, 0.10 + ny * 0.28);
    color = mixColor(color, BG_LIGHT, 0.03 + sweep * 0.05 + band * 0.03);
    if (((x * 7 + y * 11) % 13) === 0) {{
      color = mixColor(color, ACCENT, 0.04);
    }}
    return color;
  }}

  function sampleFlashColor(x, y, phase) {{
    const nx = W <= 1 ? 0 : x / (W - 1);
    const ny = H <= 1 ? 0 : y / (H - 1);
    const shimmer = 0.5 + 0.5 * Math.sin(phase * Math.PI * 2.0 + nx * 3.1 + ny * 1.7);
    let color = mixColor(BG_LIGHT, HALO, 0.34 + ny * 0.12);
    color = mixColor(color, ACCENT, 0.12 + shimmer * 0.10);
    return color;
  }}

  function sampleFinalTextColor(x, y, neighbors, phase) {{
    const nx = W <= 1 ? 0.5 : x / (W - 1);
    const ny = H <= 1 ? 0.5 : y / (H - 1);
    const shimmer = 0.5 + 0.5 * Math.sin(phase * Math.PI * 2.0 + nx * 4.2 - ny * 2.1);
    const edgeStrength = neighbors >= 4 ? 0.0 : neighbors === 3 ? 0.18 : neighbors === 2 ? 0.40 : 0.62;
    let fill = mixColor(TEXT_MAIN, TEXT_ALT, 0.18 + ny * 0.44);
    fill = mixColor(fill, HALO, 0.08 + shimmer * 0.08);
    const edge = mixColor(TEXT_EDGE, ACCENT, 0.10 + nx * 0.12);
    return mixColor(fill, edge, edgeStrength);
  }}

  function plot(frame, x, y, color, alpha) {{
    if (x < 0 || x >= W || y < 0 || y >= H) return;
    const base = frame[y][x];
    frame[y][x] = [
      clamp255(mix(base[0], color[0], alpha)),
      clamp255(mix(base[1], color[1], alpha)),
      clamp255(mix(base[2], color[2], alpha)),
    ];
  }}

  if (!renderFrame._state) {{
    renderFrame._state = {{ frame: 0 }};
  }}
  const state = renderFrame._state;
  const frameIndex = state.frame;
  state.frame = (state.frame + 1) % LOOP_FRAMES;
  const phase = LOOP_FRAMES <= 1 ? 0.0 : frameIndex / Math.max(1, LOOP_FRAMES - 1);
  const flashFrames = Number(EXTRAS.flash_frames || 4);
  const handoffFrames = Math.max(1, REVEAL_FRAMES - flashFrames);

  let boardFlash = 0.0;
  let revealMix = 0.0;
  let textAlpha = 0.0;
  if (frameIndex < flashFrames) {{
    boardFlash = flashFrames <= 1 ? 1.0 : frameIndex / Math.max(1, flashFrames - 1);
    revealMix = 0.0;
    textAlpha = boardFlash;
  }} else if (frameIndex < REVEAL_FRAMES) {{
    const handoffFrame = frameIndex - flashFrames + 1;
    revealMix = Math.max(0.0, Math.min(1.0, handoffFrame / handoffFrames));
    boardFlash = Math.max(0.0, 1.0 - revealMix);
    textAlpha = 1.0;
  }} else if (frameIndex < REVEAL_FRAMES + HOLD_FRAMES) {{
    revealMix = 1.0;
    textAlpha = 1.0;
  }} else if (frameIndex < REVEAL_FRAMES + HOLD_FRAMES + FADE_FRAMES) {{
    const fadeFrame = frameIndex - REVEAL_FRAMES - HOLD_FRAMES;
    revealMix = 1.0;
    textAlpha = 1.0 - (FADE_FRAMES <= 1 ? 1.0 : fadeFrame / Math.max(1, FADE_FRAMES - 1));
  }} else {{
    revealMix = 1.0;
    textAlpha = 0.0;
  }}

  const frame = new Array(H);
  for (let y = 0; y < H; y++) {{
    const row = new Array(W);
    for (let x = 0; x < W; x++) {{
      let bg = sampleBackground(x, y, phase);
      if (boardFlash > 0.0) {{
        const flashColor = sampleFlashColor(x, y, phase);
        bg = mixColor(bg, flashColor, 0.18 + boardFlash * 0.74);
      }}
      row[x] = [clamp255(bg[0]), clamp255(bg[1]), clamp255(bg[2])];
    }}
    frame[y] = row;
  }}

  if (textAlpha <= 0.0) {{
    return frame;
  }}

  for (let y = 0; y < H; y++) {{
    for (let x = 0; x < W; x++) {{
      if (!isTextLit(x, y)) {{
        continue;
      }}
      const neighbors = neighborCount(x, y);
      const finalText = sampleFinalTextColor(x, y, neighbors, phase);
      const cutoutBase = mixColor(BG_DARK, TEXT_EDGE, 0.14 + (neighbors <= 2 ? 0.10 : 0.04));
      const cutoutPulse = 0.5 + 0.5 * Math.cos(phase * Math.PI * 2.0 + x * 0.25 + y * 0.18);
      const cutoutColor = mixColor(cutoutBase, BG_DARK, 0.18 + cutoutPulse * 0.10);
      const color = mixColor(cutoutColor, finalText, revealMix);
      plot(frame, x, y, color, textAlpha);
      if (revealMix > 0.45 && neighbors < 4) {{
        const haloColor = mixColor(ACCENT, HALO, 0.52);
        const haloAlpha = textAlpha * 0.10 * revealMix;
        plot(frame, x - 1, y, haloColor, haloAlpha);
        plot(frame, x + 1, y, haloColor, haloAlpha);
        plot(frame, x, y - 1, haloColor, haloAlpha);
        plot(frame, x, y + 1, haloColor, haloAlpha);
      }}
    }}
  }}

  return frame;
}}
"""
    note = "\n".join(
        [
            "[LOCAL]",
            "generator: deterministic local inverse flash reveal",
            f"text: {context.text}",
            "motion: full-board inverse flash ramps in, the text appears as a dark cutout, then resolves into the final bright word",
            f"board: {BOARD_WIDTH}x{BOARD_HEIGHT}",
            f"lit_pixels: {lit_pixels}",
            f"loop_length_frames: {loop_length_frames}",
            f"background_style: {context.background_style.name}",
            f"font_style: {context.font_style.name}",
            f"text_effect: {context.text_effect.name}",
            "reason: inverse flash needs a dedicated local timeline so the flash, handoff, and loop closure stay stable",
        ]
    )
    return LocalEffectResult(
        loop_length_frames=loop_length_frames,
        function_code=function_code.rstrip() + "\n",
        note=note,
    )


def build_centered_local_effect_spec(
    *,
    name: str,
    profile_builder: Callable[[LocalEffectContext], RevealEffectProfile],
) -> LocalEffectSpec:
    return LocalEffectSpec(
        name=name,
        supports=supports_centered_board_mask,
        build=lambda context: build_generic_reveal_effect(
            context,
            profile=profile_builder(context),
        ),
    )


__all__ = [
    "LOCAL_EFFECT_REGISTRY",
    "BuildFunc",
    "LocalEffectContext",
    "LocalEffectResult",
    "LocalEffectSpec",
    "RevealEffectProfile",
    "SupportsFunc",
    "build_centered_local_effect_spec",
    "build_generic_reveal_effect",
    "build_inverse_flash_reveal_effect",
    "register_local_effect",
    "render_centered_mask",
    "resolve_local_effect",
    "supports_centered_board_mask",
    "supports_char_limit",
]


