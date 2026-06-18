from __future__ import annotations

from dataclasses import dataclass

from backend.app.cloud.service.led.ledword.common import derive_seed
from backend.app.cloud.service.led.ledword.effects import LocalEffectContext, resolve_local_effect
from backend.app.cloud.service.led.ledword.styles import (
    DEFAULT_BACKGROUND_STYLE,
    DEFAULT_FONT_STYLE,
    FontStylePreset,
    resolve_background_style,
    resolve_font_style,
    resolve_text_effect,
    text_effect_design_type_for_effect,
)


@dataclass(frozen=True)
class LedWordGeneration:
    background_style: str
    font_style: FontStylePreset
    text_effect: str
    loop_length_frames: int
    prompt: str
    function_code: str

    @property
    def design_display_name(self) -> str:
        design_type = text_effect_design_type_for_effect(self.text_effect)
        return '' if design_type is None else design_type.display_name


def generate_ledword(
    text: str,
    *,
    text_effect: str,
    background_style: str = DEFAULT_BACKGROUND_STYLE,
    font_style: str = DEFAULT_FONT_STYLE,
    style_seed: int | None = None,
) -> LedWordGeneration:
    normalized_text = str(text or '').replace('\ufeff', '').strip()
    if not normalized_text:
        raise ValueError('text must not be empty')

    resolved_background_style = resolve_background_style(
        background_style,
        seed=derive_seed(style_seed, 101),
    )
    resolved_font_style = _resolve_generation_font_style(
        font_style=font_style,
        text=normalized_text,
        style_seed=style_seed,
    )
    resolved_text_effect = resolve_text_effect(text_effect, text=normalized_text)

    local_effect_context = LocalEffectContext(
        text=normalized_text,
        background_style=resolved_background_style,
        font_style=resolved_font_style,
        text_effect=resolved_text_effect,
        font_path=resolved_font_style.font_path,
        seed=style_seed,
    )
    local_effect_spec = resolve_local_effect(local_effect_context)
    if local_effect_spec is None:
        raise ValueError(f'text effect is not implemented locally: {resolved_text_effect.name}')

    local_result = local_effect_spec.build(local_effect_context)
    return LedWordGeneration(
        background_style=resolved_background_style.name,
        font_style=resolved_font_style,
        text_effect=resolved_text_effect.name,
        loop_length_frames=local_result.loop_length_frames,
        prompt=local_result.note,
        function_code=local_result.function_code,
    )


def _resolve_generation_font_style(
    *,
    font_style: str,
    text: str,
    style_seed: int | None,
) -> FontStylePreset:
    return resolve_font_style(
        font_style,
        text=text,
        seed=derive_seed(style_seed, 211),
    )


__all__ = [
    'LedWordGeneration',
    'generate_ledword',
]
