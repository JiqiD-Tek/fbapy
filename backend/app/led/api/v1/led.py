from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.app.led.schema.led import (
    FastGenerateLedAnimationParam,
    GenerateFunctionCodeParam,
    GenerateLedAnimationParam,
    GenerateSemanticDesignParam,
)
from backend.app.led.service import led_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base

router = APIRouter()


@router.post('/designs', summary='Generate LED semantic design')
async def generate_semantic_design(
    obj: GenerateSemanticDesignParam,
) -> ResponseSchemaModel[dict[str, Any]]:
    data = await led_service.generate_semantic_design(
        description=obj.description,
        model=obj.model,
        store_response=obj.store_openai_response,
    )
    return response_base.success(data=data)


@router.post('/functions', summary='Generate LED function code')
async def generate_function_code(
    obj: GenerateFunctionCodeParam,
) -> ResponseSchemaModel[dict[str, Any]]:
    data = await led_service.generate_function_from_design(
        design=obj.parse_design(),
        model=obj.model,
        store_response=obj.store_openai_response,
    )
    return response_base.success(data=data)


@router.post('/generations', summary='Generate LED animation with two-stage flow')
async def generate_led_animation(
    obj: GenerateLedAnimationParam,
) -> ResponseSchemaModel[dict[str, Any]]:
    data = await led_service.generate_animation(
        description=obj.description,
        model=obj.model,
        store_response=obj.store_openai_response,
    )
    return response_base.success(data=data)


@router.post('/generations/fast', summary='Generate LED animation with single-pass flow')
async def generate_led_animation_fast(
    obj: FastGenerateLedAnimationParam,
) -> ResponseSchemaModel[dict[str, Any]]:
    data = await led_service.generate_animation_fast(
        description=obj.description,
        model=obj.model,
        store_response=obj.store_openai_response,
        fallback_to_two_stage=obj.fallback_to_two_stage,
    )
    return response_base.success(data=data)
