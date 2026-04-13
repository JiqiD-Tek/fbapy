# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : huoshan.py
@Author  : OpenAI
@Date    : 2026/04/13
"""

from fastapi import APIRouter

from backend.app.cloud.schema.huoshan import (
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
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()


@router.post(
    '/voices/all',
    summary='Query all Huoshan voice clone statuses as a flat list',
    response_model_by_alias=False,
)
async def list_all_huoshan_voice_statuses(
    obj: HuoshanVoiceListParam,
) -> ResponseSchemaModel[list[HuoshanVoiceStatus]]:
    query = obj.model_copy(update={'state': obj.state or 'Success'}, deep=True)
    data = await huoshan_voice_service.list_all_voice_statuses(query)
    return response_base.success(data=data)


@router.post(
    '/voices/orders',
    summary='Create Huoshan voice clone orders',
    dependencies=[DependsJwtAuth],
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
    dependencies=[DependsJwtAuth],
    response_model_by_alias=False,
)
async def renew_huoshan_voices(
    obj: HuoshanVoiceRenewParam,
) -> ResponseSchemaModel[HuoshanVoiceRenewResponse]:
    data = await huoshan_voice_service.renew_voices(obj)
    return response_base.success(data=data)


@router.post(
    '/stories/synthesis',
    summary='Synthesize story audio with Huoshan voice clone and upload to OSS',
    dependencies=[DependsJwtAuth],
    response_model_by_alias=False,
)
async def synthesize_huoshan_story(
    db: CurrentSession,
    obj: HuoshanStorySynthesisParam,
) -> ResponseSchemaModel[HuoshanStorySynthesisResult]:
    data = await huoshan_voice_service.synthesize_story(db=db, obj=obj)
    return response_base.success(data=data)
