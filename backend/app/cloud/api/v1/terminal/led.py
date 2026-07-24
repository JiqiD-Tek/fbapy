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

from backend.app.cloud.service.resource.providers.led import led_service
from backend.app.cloud.service.resource.providers.led.schema import GenerateLedAnimationParam
from backend.common.response.response_schema import ResponseSchemaModel, response_base

router = APIRouter()

@router.post('/generations', summary='生成文字灯效代码')
async def generate_led_animation(
    obj: GenerateLedAnimationParam,
) -> ResponseSchemaModel[dict[str, Any]]:
    data = await led_service.generate_animation(
        text=obj.text,
        design_type=obj.design_type,
        font_style=obj.font_style,
        background_style=obj.background_style,
        style_seed=obj.style_seed,
    )
    return response_base.success(data=data)
