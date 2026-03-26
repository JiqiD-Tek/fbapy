# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : led.py
@Author  : guhua@jiqid.com
@Date    : 2026/03/24
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.app.cloud.service.led import led_service
from backend.app.cloud.service.led.schema import GenerateFunctionCodeParam, GenerateLedAnimationParam, GenerateSemanticDesignParam
from backend.common.response.response_schema import ResponseSchemaModel, response_base

router = APIRouter()


@router.post('/designs', summary='生成灯效语义设计')
async def generate_semantic_design(
    obj: GenerateSemanticDesignParam,
) -> ResponseSchemaModel[dict[str, Any]]:
    data = await led_service.generate_semantic_design(description=obj.description)
    return response_base.success(data=data)


@router.post('/functions', summary='生成灯效函数代码')
async def generate_function_code(
    obj: GenerateFunctionCodeParam,
) -> ResponseSchemaModel[dict[str, Any]]:
    data = await led_service.generate_function_from_design(design=obj.parse_design())
    return response_base.success(data=data)


@router.post('/generations', summary='生成灯效代码')
async def generate_led_animation(
    obj: GenerateLedAnimationParam,
) -> ResponseSchemaModel[dict[str, Any]]:
    data = await led_service.generate_animation(description=obj.description)
    return response_base.success(data=data)
