# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : huoshan.py
@Author  : OpenAI
@Date    : 2026/04/13
"""

from fastapi import APIRouter, Path

from backend.app.cloud.schema.resource.huoshan import (
    HuoshanStoryGenerateParam,
    HuoshanStoryGenerateResult,
    HuoshanStorySynthesisParam,
    HuoshanStorySynthesisResult,
    HuoshanVoiceListParam,
    HuoshanVoiceOrderParam,
    HuoshanVoiceOrderResponse,
    HuoshanVoiceRenewParam,
    HuoshanVoiceRenewResponse,
    HuoshanVoiceStatus,
)
from backend.app.cloud.service.resource.huoshan.service import huoshan_voice_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.database.db import CurrentSession

router = APIRouter()


@router.post(
    '/voices/all',
    summary='Query all Huoshan voice clone statuses as a flat list',
    # dependencies=[DependsJwtAuth],
    response_model_by_alias=False,
)
async def list_all_huoshan_voice_statuses(
    obj: HuoshanVoiceListParam,
) -> ResponseSchemaModel[list[HuoshanVoiceStatus]]:
    data = await huoshan_voice_service.list_all_voice_statuses(obj)
    return response_base.success(data=data)


@router.post(
    '/voices/orders',
    summary='Create Huoshan voice clone orders',
    # dependencies=[DependsJwtAuth],
    response_model_by_alias=False,
)
async def order_huoshan_voices(
    obj: HuoshanVoiceOrderParam,
) -> ResponseSchemaModel[HuoshanVoiceOrderResponse]:
    data = await huoshan_voice_service.order_voices(obj)
    return response_base.success(data=data)


@router.post(
    '/voices/renewals',
    summary='Renew Huoshan voice clones',
    # dependencies=[DependsJwtAuth],
    response_model_by_alias=False,
)
async def renew_huoshan_voices(
    obj: HuoshanVoiceRenewParam,
) -> ResponseSchemaModel[HuoshanVoiceRenewResponse]:
    data = await huoshan_voice_service.renew_voices(obj)
    return response_base.success(data=data)


@router.post(
    '/stories/generate',
    summary='Generate a story by topic with Huoshan large model',
    # dependencies=[DependsJwtAuth],
    response_model_by_alias=False,
)
async def generate_huoshan_story(
    obj: HuoshanStoryGenerateParam,
) -> ResponseSchemaModel[HuoshanStoryGenerateResult]:
    data = await huoshan_voice_service.submit_story_generation(obj)
    return response_base.success(data=data)


@router.get(
    '/stories/generate/{task_id}',
    summary='Query Huoshan story generation task status',
    # dependencies=[DependsJwtAuth],
    response_model_by_alias=False,
)
async def get_huoshan_story_generation(
    task_id: str = Path(description='Story generation task ID'),
) -> ResponseSchemaModel[HuoshanStoryGenerateResult]:
    data = await huoshan_voice_service.get_story_generation(task_id=task_id)
    return response_base.success(data=data)


@router.post(
    '/stories/synthesis',
    summary='Submit Huoshan story synthesis task',
    # dependencies=[DependsJwtAuth],
    response_model_by_alias=False,
)
async def synthesize_huoshan_story(
    db: CurrentSession,
    obj: HuoshanStorySynthesisParam,
) -> ResponseSchemaModel[HuoshanStorySynthesisResult]:
    data = await huoshan_voice_service.synthesize_story(db=db, obj=obj)
    return response_base.success(data=data)


@router.get(
    '/stories/synthesis/{task_id}',
    summary='Query Huoshan story synthesis task status',
    # dependencies=[DependsJwtAuth],
    response_model_by_alias=False,
)
async def get_huoshan_story_synthesis(
    task_id: str = Path(description='Huoshan task ID'),
) -> ResponseSchemaModel[HuoshanStorySynthesisResult]:
    data = await huoshan_voice_service.get_story_synthesis(task_id=task_id)
    return response_base.success(data=data)
