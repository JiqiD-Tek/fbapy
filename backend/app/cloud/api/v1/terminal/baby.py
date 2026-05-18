# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : baby.py
@Author  : OpenAI
@Date    : 2026/04/17
"""

from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.cloud.schema.baby import CreateBabyParam, GetBabyDetail, UpdateBabyParam
from backend.app.cloud.schema.analytics import TSDBAnalyticsDetail, VikingAnalyticsDetail
from backend.app.cloud.service.analytics_service import analytics_service
from backend.app.cloud.service.baby_service import baby_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取宝宝详情', dependencies=[DependsJwtAuth])
async def get_baby(
        request: Request,
        db: CurrentSession,
        pk: Annotated[int, Path(description='宝宝 ID')],
) -> ResponseSchemaModel[GetBabyDetail]:
    data = await baby_service.get(db=db, user_id=request.user.id, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='分页获取宝宝列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_baby_paginated(
        request: Request,
        db: CurrentSession,
        name: Annotated[str | None, Query(description='宝宝姓名')] = None,
        nickname: Annotated[str | None, Query(description='宝宝昵称')] = None,
        sex: Annotated[int | None, Query(description='性别(0未知 1男 2女)')] = None,
        device_id: Annotated[int | None, Query(description='设备 ID')] = None,
) -> ResponseSchemaModel[PageData[GetBabyDetail]]:
    page_data = await baby_service.get_list(
        db=db,
        user_id=request.user.id,
        name=name,
        nickname=nickname,
        sex=sex,
        device_id=device_id,
    )
    return response_base.success(data=page_data)


@router.post('', summary='创建宝宝', dependencies=[DependsJwtAuth])
async def create_baby(
        request: Request,
        db: CurrentSessionTransaction,
        obj: CreateBabyParam,
) -> ResponseSchemaModel[GetBabyDetail]:
    data = await baby_service.create(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.put('/{pk}', summary='更新宝宝', dependencies=[DependsJwtAuth])
async def update_baby(
        request: Request,
        db: CurrentSessionTransaction,
        pk: Annotated[int, Path(description='宝宝 ID')],
        obj: UpdateBabyParam,
) -> ResponseModel:
    count = await baby_service.update(db=db, user_id=request.user.id, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除宝宝', dependencies=[DependsJwtAuth])
async def delete_baby(
        request: Request,
        db: CurrentSessionTransaction,
        pk: Annotated[int, Path(description='宝宝 ID')],
) -> ResponseModel:
    count = await baby_service.delete(db=db, user_id=request.user.id, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.get('/{pk}/viking', summary='获取宝宝的画像数据', dependencies=[DependsJwtAuth])
async def get_viking(
        request: Request,
        db: CurrentSession,
        pk: Annotated[int, Path(description='宝宝 ID')],
        memory_query: Annotated[str | None, Query(description='Viking 语义查询词')] = None,
        memory_event_limit: Annotated[int, Query(description='Viking 事件记忆条数', ge=1, le=100)] = 10,
        memory_profile_limit: Annotated[int, Query(description='Viking 画像记忆条数', ge=1, le=100)] = 10,
        assistant_id: Annotated[str | None, Query(description='按 assistant 隔离的 ID')] = None,
        start_time: Annotated[str | None, Query(description='Viking 查询开始时间，支持 ISO 字符串或毫秒时间戳')] = None,
        end_time: Annotated[str | None, Query(description='Viking 查询结束时间，支持 ISO 字符串或毫秒时间戳')] = None,
) -> ResponseSchemaModel[VikingAnalyticsDetail]:
    data = await analytics_service.query_viking(
        db=db,
        user_id=request.user.id,
        baby_id=pk,
        memory_query=memory_query,
        memory_event_limit=memory_event_limit,
        memory_profile_limit=memory_profile_limit,
        assistant_id=assistant_id,
        start_time=start_time,
        end_time=end_time,
    )
    return response_base.success(data=data)


@router.get('/{pk}/tsdb', summary='获取宝宝的 TSDB 数据', dependencies=[DependsJwtAuth])
async def get_tsdb(
        request: Request,
        db: CurrentSession,
        pk: Annotated[int, Path(description='宝宝 ID')],
        start_time: Annotated[str | None, Query(description='TSDB 查询开始时间')] = None,
        end_time: Annotated[str | None, Query(description='TSDB 查询结束时间')] = None,
        category: Annotated[str | None, Query(description='TSDB 事件分类')] = None,
        service: Annotated[str | None, Query(description='TSDB 服务来源')] = None,
        limit: Annotated[int, Query(description='TSDB 返回条数', ge=1, le=50000)] = 100,
) -> ResponseSchemaModel[TSDBAnalyticsDetail]:
    data = await analytics_service.query_tsdb(
        db=db,
        user_id=request.user.id,
        baby_id=pk,
        start_time=start_time,
        end_time=end_time,
        category=category,
        service=service,
        limit=limit,
    )
    return response_base.success(data=data)
