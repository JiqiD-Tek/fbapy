# -*- coding: UTF-8 -*-
"""
Script resource API.
"""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.cloud.schema.resource.script import (
    CreateScriptParam,
    GetScriptDetail,
    ScriptAICreateParam,
    ScriptLine,
    UpdateScriptParam,
)
from backend.app.cloud.service.resource.script_service import cloud_script_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='Get script detail', dependencies=[DependsJwtAuth])
async def get_script(
    db: CurrentSession,
    pk: Annotated[int, Path(description='Script ID')],
) -> ResponseSchemaModel[GetScriptDetail]:
    data = await cloud_script_service.get_script(db=db, pk=pk)
    return response_base.success(data=GetScriptDetail.model_validate(data))


@router.get('', summary='Get script list', dependencies=[DependsJwtAuth, DependsPagination])
async def get_script_paginated(
    db: CurrentSession,
    title: Annotated[str | None, Query(description='Title')] = None,
    author: Annotated[str | None, Query(description='Author')] = None,
    status: Annotated[int | None, Query(description='Status')] = None,
    toy_ids: Annotated[list[int] | None, Query(description='Contains all specified toy IDs')] = None,
    exact_toy_ids: Annotated[list[int] | None, Query(description='Exactly matches the specified toy ID set')] = None,
) -> ResponseSchemaModel[PageData[GetScriptDetail]]:
    page_data = await cloud_script_service.get_script_list(
        db=db,
        title=title,
        author=author,
        status=status,
        toy_ids=toy_ids,
        exact_toy_ids=exact_toy_ids,
    )
    page_data['items'] = [GetScriptDetail.model_validate(item) for item in page_data['items']]
    return response_base.success(data=page_data)


@router.post('/ai-create', summary='AI create script content', dependencies=[DependsJwtAuth])
async def ai_create_script(
    obj: ScriptAICreateParam,
) -> ResponseSchemaModel[list[ScriptLine]]:
    data = await cloud_script_service.ai_create_script_content(obj=obj)
    return response_base.success(data=data)


@router.post('', summary='Create script', dependencies=[DependsJwtAuth])
async def create_script(
    db: CurrentSessionTransaction,
    obj: CreateScriptParam,
) -> ResponseSchemaModel[GetScriptDetail]:
    script = await cloud_script_service.create_script(db=db, obj=obj)
    return response_base.success(data=GetScriptDetail.model_validate(script))


@router.put('/{pk}', summary='Update script', dependencies=[DependsJwtAuth])
async def update_script(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='Script ID')],
    obj: UpdateScriptParam,
) -> ResponseModel:
    count = await cloud_script_service.update_script(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='Delete script', dependencies=[DependsJwtAuth])
async def delete_script(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='Script ID')],
) -> ResponseModel:
    count = await cloud_script_service.delete_script(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
