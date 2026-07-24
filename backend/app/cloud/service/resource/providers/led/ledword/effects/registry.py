from __future__ import annotations

from backend.app.cloud.service.resource.providers.led.ledword.effects._shared.centered_reveal_runtime import (
    LocalEffectContext,
    LocalEffectResult,
    LocalEffectSpec,
    register_local_effect,
)
from backend.app.cloud.service.resource.providers.led.ledword.effects.box_open_reveal import BOX_OPEN_REVEAL_SPEC
from backend.app.cloud.service.resource.providers.led.ledword.effects.center_burst_reveal import CENTER_BURST_REVEAL_SPEC
from backend.app.cloud.service.resource.providers.led.ledword.effects.decode_reveal import DECODE_REVEAL_SPEC
from backend.app.cloud.service.resource.providers.led.ledword.effects.flipboard_reveal import (
    FLIPBOARD_REVEAL_EFFECT_NAMES,
    build_local_flipboard_reveal_function_code,
    build_local_flipboard_reveal_note,
)
from backend.app.cloud.service.resource.providers.led.ledword.effects.glitch_hold import GLITCH_HOLD_SPEC
from backend.app.cloud.service.resource.providers.led.ledword.effects.horizontal_stretch_reveal import HORIZONTAL_STRETCH_REVEAL_SPEC
from backend.app.cloud.service.resource.providers.led.ledword.effects.inverse_flash_reveal import INVERSE_FLASH_REVEAL_SPEC
from backend.app.cloud.service.resource.providers.led.ledword.effects.marquee_scroll_reveal import (
    build_local_marquee_scroll_reveal_function_code,
    build_local_marquee_scroll_reveal_note,
)
from backend.app.cloud.service.resource.providers.led.ledword.effects.outline_scan_reveal import OUTLINE_SCAN_REVEAL_SPEC
from backend.app.cloud.service.resource.providers.led.ledword.effects.pixel_reveal import (
    PIXEL_REVEAL_EFFECT_NAMES,
    build_local_pixel_reveal_function_code,
    build_local_pixel_reveal_note,
)
from backend.app.cloud.service.resource.providers.led.ledword.effects.raindrop_reveal import RAINDROP_REVEAL_SPEC
from backend.app.cloud.service.resource.providers.led.ledword.effects.recognition_handoff_reveal import RECOGNITION_HANDOFF_REVEAL_SPEC
from backend.app.cloud.service.resource.providers.led.ledword.effects.scanline_reveal import (
    SCANLINE_REVEAL_EFFECT_NAMES,
    build_local_scanline_reveal_function_code,
    build_local_scanline_reveal_note,
)
from backend.app.cloud.service.resource.providers.led.ledword.effects.sequential_outline_scan_reveal import SEQUENTIAL_OUTLINE_SCAN_REVEAL_SPEC
from backend.app.cloud.service.resource.providers.led.ledword.effects.stamp_pop_reveal import STAMP_POP_REVEAL_SPEC
from backend.app.cloud.service.resource.providers.led.ledword.effects.star_gather_reveal import (
    build_local_star_gather_reveal_function_code,
    build_local_star_gather_reveal_note,
)
from backend.app.cloud.service.resource.providers.led.ledword.effects.stroke_write_reveal import STROKE_WRITE_REVEAL_SPEC
from backend.app.cloud.service.resource.providers.led.ledword.effects.wave_reveal import WAVE_REVEAL_SPEC
from backend.app.cloud.service.resource.providers.led.ledword.styles import supports_text_effect_for_text


_REGISTERED = False


def _build_pixel_reveal(context: LocalEffectContext) -> LocalEffectResult:
    loop_length_frames, function_code = build_local_pixel_reveal_function_code(
        text=context.text,
        background_style=context.background_style,
        text_effect=context.text_effect,
        font_path=context.font_path,
        seed=context.seed,
    )
    return LocalEffectResult(
        loop_length_frames=loop_length_frames,
        function_code=function_code,
        note=build_local_pixel_reveal_note(
            text=context.text,
            background_style=context.background_style,
            font_style=context.font_style,
            text_effect=context.text_effect,
            loop_length_frames=loop_length_frames,
        ),
    )


def _build_star_gather_reveal(context: LocalEffectContext) -> LocalEffectResult:
    loop_length_frames, function_code = build_local_star_gather_reveal_function_code(
        text=context.text,
        background_style=context.background_style,
        text_effect=context.text_effect,
        font_path=context.font_path,
        seed=context.seed,
    )
    return LocalEffectResult(
        loop_length_frames=loop_length_frames,
        function_code=function_code,
        note=build_local_star_gather_reveal_note(
            text=context.text,
            background_style=context.background_style,
            font_style=context.font_style,
            text_effect=context.text_effect,
            loop_length_frames=loop_length_frames,
        ),
    )


def _build_scanline_reveal(context: LocalEffectContext) -> LocalEffectResult:
    loop_length_frames, function_code = build_local_scanline_reveal_function_code(
        text=context.text,
        background_style=context.background_style,
        text_effect=context.text_effect,
        font_path=context.font_path,
        seed=context.seed,
    )
    return LocalEffectResult(
        loop_length_frames=loop_length_frames,
        function_code=function_code,
        note=build_local_scanline_reveal_note(
            text=context.text,
            background_style=context.background_style,
            font_style=context.font_style,
            text_effect=context.text_effect,
            loop_length_frames=loop_length_frames,
            seed=context.seed,
        ),
    )


def _build_flipboard_reveal(context: LocalEffectContext) -> LocalEffectResult:
    loop_length_frames, function_code = build_local_flipboard_reveal_function_code(
        text=context.text,
        background_style=context.background_style,
        text_effect=context.text_effect,
        font_path=context.font_path,
        seed=context.seed,
    )
    return LocalEffectResult(
        loop_length_frames=loop_length_frames,
        function_code=function_code,
        note=build_local_flipboard_reveal_note(
            text=context.text,
            background_style=context.background_style,
            font_style=context.font_style,
            text_effect=context.text_effect,
            loop_length_frames=loop_length_frames,
            seed=context.seed,
        ),
    )


def _build_marquee_scroll_reveal(context: LocalEffectContext) -> LocalEffectResult:
    loop_length_frames, function_code = build_local_marquee_scroll_reveal_function_code(
        text=context.text,
        background_style=context.background_style,
        font_style=context.font_style,
        text_effect=context.text_effect,
        font_path=context.font_path,
        seed=context.seed,
    )
    return LocalEffectResult(
        loop_length_frames=loop_length_frames,
        function_code=function_code,
        note=build_local_marquee_scroll_reveal_note(
            text=context.text,
            background_style=context.background_style,
            font_style=context.font_style,
            text_effect=context.text_effect,
            loop_length_frames=loop_length_frames,
        ),
    )


def _iter_local_effect_specs() -> tuple[LocalEffectSpec, ...]:
    return (
        LocalEffectSpec(
            name='pixel_reveal',
            supports=lambda context: context.text_effect.name in PIXEL_REVEAL_EFFECT_NAMES
            and supports_text_effect_for_text(context.text_effect.name, context.text),
            build=_build_pixel_reveal,
        ),
        LocalEffectSpec(
            name='sequential_pixel_reveal',
            supports=lambda context: context.text_effect.name in PIXEL_REVEAL_EFFECT_NAMES
            and supports_text_effect_for_text(context.text_effect.name, context.text),
            build=_build_pixel_reveal,
        ),
        LocalEffectSpec(
            name='star_gather_reveal',
            supports=lambda context: supports_text_effect_for_text('star_gather_reveal', context.text),
            build=_build_star_gather_reveal,
        ),
        LocalEffectSpec(
            name='scanline_reveal',
            supports=lambda context: context.text_effect.name in SCANLINE_REVEAL_EFFECT_NAMES
            and supports_text_effect_for_text(context.text_effect.name, context.text),
            build=_build_scanline_reveal,
        ),
        LocalEffectSpec(
            name='flipboard_reveal',
            supports=lambda context: context.text_effect.name in FLIPBOARD_REVEAL_EFFECT_NAMES
            and supports_text_effect_for_text(context.text_effect.name, context.text),
            build=_build_flipboard_reveal,
        ),
        LocalEffectSpec(
            name='marquee_scroll_reveal',
            supports=lambda context: supports_text_effect_for_text('marquee_scroll_reveal', context.text),
            build=_build_marquee_scroll_reveal,
        ),
        DECODE_REVEAL_SPEC,
        GLITCH_HOLD_SPEC,
        CENTER_BURST_REVEAL_SPEC,
        OUTLINE_SCAN_REVEAL_SPEC,
        SEQUENTIAL_OUTLINE_SCAN_REVEAL_SPEC,
        STROKE_WRITE_REVEAL_SPEC,
        STAMP_POP_REVEAL_SPEC,
        RAINDROP_REVEAL_SPEC,
        WAVE_REVEAL_SPEC,
        HORIZONTAL_STRETCH_REVEAL_SPEC,
        BOX_OPEN_REVEAL_SPEC,
        INVERSE_FLASH_REVEAL_SPEC,
        RECOGNITION_HANDOFF_REVEAL_SPEC,
    )


def ensure_local_effects_registered() -> None:
    global _REGISTERED

    if _REGISTERED:
        return
    for spec in _iter_local_effect_specs():
        register_local_effect(spec)
    _REGISTERED = True


__all__ = ['ensure_local_effects_registered']
