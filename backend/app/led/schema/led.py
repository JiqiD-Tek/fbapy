from __future__ import annotations

from typing import Any

from pydantic import Field

from backend.app.led.schema.domain import SemanticDesign
from backend.common.schema import SchemaBase


class ModelInvocationParam(SchemaBase):
    model: str | None = Field(None, description='Azure deployment override')
    store_openai_response: bool = Field(False, description='Whether to forward store=true to Responses API')


class GenerateSemanticDesignParam(ModelInvocationParam):
    description: str = Field(..., min_length=1, description='Short or detailed LED effect request')


class GenerateFunctionCodeParam(ModelInvocationParam):
    semantic_design: dict[str, Any] = Field(..., description='Semantic design payload')

    def parse_design(self) -> SemanticDesign:
        return SemanticDesign.from_dict(self.semantic_design)


class GenerateLedAnimationParam(ModelInvocationParam):
    description: str = Field(..., min_length=1, description='Short or detailed LED effect request')


class FastGenerateLedAnimationParam(GenerateLedAnimationParam):
    fallback_to_two_stage: bool = Field(True, description='Fallback to two-stage flow on short prompts or validation failures')


__all__ = [
    'FastGenerateLedAnimationParam',
    'GenerateFunctionCodeParam',
    'GenerateLedAnimationParam',
    'GenerateSemanticDesignParam',
    'ModelInvocationParam',
]
