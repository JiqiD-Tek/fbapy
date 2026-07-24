from __future__ import annotations

from pydantic import AliasChoices, Field

from backend.common.schema import SchemaBase


class LedGenerationRequestBase(SchemaBase):
    text: str = Field(
        min_length=1,
        validation_alias=AliasChoices('text', 'description'),
        description='Text to preview as LED animation',
    )
    design_type: str | None = Field(None, description='Optional explicit design type')
    font_style: str | None = Field(None, description='Optional explicit font style')
    background_style: str | None = Field(None, description='Optional explicit background style')
    style_seed: int | None = Field(None, description='Optional seed for reproducible style decisions')


class GenerateLedAnimationParam(LedGenerationRequestBase):
    pass


__all__ = [
    'GenerateLedAnimationParam',
]
