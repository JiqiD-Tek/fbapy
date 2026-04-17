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
