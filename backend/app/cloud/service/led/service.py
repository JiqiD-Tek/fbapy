from __future__ import annotations

from typing import Any

from backend.app.cloud.service.led.ledword.service import generate_ledword
from backend.app.cloud.service.led.ledword.styles import supported_font_styles, text_effect_length_limit_for_text
from backend.app.cloud.service.led.selector import (
    recommended_design_types_for_text,
    resolve_generation_selection,
    supported_design_types_for_text,
)
from backend.common.exception import errors


class LedService:
    async def generate_animation(
        self,
        *,
        text: str,
        design_type: str | None = None,
        font_style: str | None = None,
        background_style: str | None = None,
        style_seed: int | None = None,
    ) -> dict[str, Any]:
        selection = resolve_generation_selection(
            text=text,
            design_type=design_type,
            font_style=font_style,
            background_style=background_style,
            style_seed=style_seed,
        )
        generation = self._generate(selection, style_seed=style_seed)
        display_unit_limit = text_effect_length_limit_for_text(
            selection.text_effect,
            text=selection.profile.text,
        )
        return {
            'text': selection.profile.text,
            'text_profile': selection.profile.to_dict(),
            'design_type': selection.design_type,
            'design_display_name': generation.design_display_name or selection.design_type,
            'text_effect_name': selection.text_effect,
            'font_style': generation.font_style.name,
            'background_style': generation.background_style,
            'loop_length_frames': generation.loop_length_frames,
            'function_code': generation.function_code,
            'prompt': generation.prompt,
            'display_unit_limit': display_unit_limit,
            'supported_design_types': supported_design_types_for_text(selection.profile.text),
            'recommended_design_types': recommended_design_types_for_text(selection.profile.text),
            'supported_font_styles': supported_font_styles(),
            'text_effect': generation.design_display_name or selection.design_type,
            'js_length_limit': display_unit_limit,
        }

    @staticmethod
    def _generate(selection, *, style_seed: int | None) -> Any:
        try:
            return generate_ledword(
                selection.profile.text,
                text_effect=selection.text_effect,
                font_style=selection.font_style,
                background_style=selection.background_style,
                style_seed=style_seed,
            )
        except FileNotFoundError as exc:
            raise errors.ServerError(msg=str(exc)) from exc
        except RuntimeError as exc:
            raise errors.ServerError(msg=str(exc)) from exc
        except ValueError as exc:
            raise errors.RequestError(msg=str(exc)) from exc


led_service = LedService()

__all__ = ['LedService', 'led_service']
