# -*- coding: UTF-8 -*-
"""
Dialogue resource API.
"""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.cloud.schema.user import DeviceAuthParam
from backend.app.cloud.schema.resource.dialogue import (
    CreateDialogueParam,
    GetDialogueDetail,
    GetRandomDialogueDetail,
    UpdateDialogueParam,
)
from backend.app.cloud.service.resource.dialogue_service import cloud_dialogue_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.auth import DependsDeviceAuth
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/random', summary='随机获取对话详情')
async def get_random_dialogue(
    db: CurrentSession,
    auth_ctx: DeviceAuthParam = DependsDeviceAuth,
) -> ResponseSchemaModel[GetDialogueDetail]:
    data = await cloud_dialogue_service.get_random_dialogue(db=db, did=auth_ctx.did)
    return response_base.success(data=GetDialogueDetail.model_validate(data))


@router.get('/{pk}', summary='获取对话详情', dependencies=[DependsJwtAuth])
async def get_dialogue(
    db: CurrentSession,
    pk: Annotated[int, Path(description='对话 ID')],
) -> ResponseSchemaModel[GetDialogueDetail]:
    data = await cloud_dialogue_service.get_dialogue(db=db, pk=pk)
    return response_base.success(data=GetDialogueDetail.model_validate(data))


@router.get('', summary='分页获取对话列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_dialogue_paginated(
    db: CurrentSession,
    title: Annotated[str | None, Query(description='名称')] = None,
    author: Annotated[str | None, Query(description='作者')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetDialogueDetail]]:
    page_data = await cloud_dialogue_service.get_dialogue_list(
        db=db,
        title=title,
        author=author,
        status=status,
    )
    page_data['items'] = [GetDialogueDetail.model_validate(item) for item in page_data['items']]
    return response_base.success(data=page_data)


@router.post('', summary='创建对话', dependencies=[DependsJwtAuth])
async def create_dialogue(
    db: CurrentSessionTransaction,
    obj: CreateDialogueParam,
) -> ResponseSchemaModel[GetDialogueDetail]:
    dialogue = await cloud_dialogue_service.create_dialogue(db=db, obj=obj)
    return response_base.success(data=GetDialogueDetail.model_validate(dialogue))


@router.put('/{pk}', summary='更新对话', dependencies=[DependsJwtAuth])
async def update_dialogue(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='对话 ID')],
    obj: UpdateDialogueParam,
) -> ResponseModel:
    count = await cloud_dialogue_service.update_dialogue(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除对话', dependencies=[DependsJwtAuth])
async def delete_dialogue(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='对话 ID')],
) -> ResponseModel:
    count = await cloud_dialogue_service.delete_dialogue(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
