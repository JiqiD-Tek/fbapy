from __future__ import annotations

from typing import Any

from pydantic import Field

from backend.app.cloud.service.led.domain import SemanticDesign
from backend.common.schema import SchemaBase


class GenerateSemanticDesignParam(SchemaBase):
    description: str = Field(..., min_length=1, description='Short or detailed LED effect request')


class GenerateFunctionCodeParam(SchemaBase):
    semantic_design: dict[str, Any] = Field(..., description='Semantic design payload')

    def parse_design(self) -> SemanticDesign:
        return SemanticDesign.from_dict(self.semantic_design)


class GenerateLedAnimationParam(SchemaBase):
    description: str = Field(..., min_length=1, description='Short or detailed LED effect request')


__all__ = [
    'GenerateFunctionCodeParam',
    'GenerateLedAnimationParam',
    'GenerateSemanticDesignParam',
]
