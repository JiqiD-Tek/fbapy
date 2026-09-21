# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : toy.py
@Author  : OpenAI
@Date    : 2026/07/06
"""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.cloud.schema.device.toy import (
    CreateToyParam,
    CreateToyNfcParam,
    BatchCreateToyNfcParam,
    CreateToySeriesParam,
    GenerateToySystemPromptParam,
    GenerateToySystemPromptResult,
    GetToyDetail,
    GetToySeriesDetail,
    ToyNfcInfo,
    UpdateToyParam,
    UpdateToyNfcParam,
    UpdateToySeriesParam,
)
from backend.app.cloud.service.toy_service import toy_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/series', summary='分页获取玩偶系列列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_toy_series_paginated(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='玩偶系列名称')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetToySeriesDetail]]:
    page_data = await toy_service.get_toy_series_list(
        db=db,
        name=name,
        status=status,
    )
    page_data['items'] = [GetToySeriesDetail.model_validate(item) for item in page_data['items']]
    return response_base.success(data=page_data)


@router.get('/series/{pk}', summary='获取玩偶系列详情', dependencies=[DependsJwtAuth])
async def get_toy_series(
    db: CurrentSession,
    pk: Annotated[int, Path(description='玩偶系列 ID')],
) -> ResponseSchemaModel[GetToySeriesDetail]:
    series = await toy_service.get_toy_series(db=db, pk=pk)
    return response_base.success(data=GetToySeriesDetail.model_validate(series))


@router.post('/series', summary='创建玩偶系列', dependencies=[DependsJwtAuth])
async def create_toy_series(
    db: CurrentSessionTransaction,
    obj: CreateToySeriesParam,
) -> ResponseSchemaModel[GetToySeriesDetail]:
    series = await toy_service.create_toy_series(db=db, obj=obj)
    return response_base.success(data=GetToySeriesDetail.model_validate(series))


@router.put('/series/{pk}', summary='更新玩偶系列', dependencies=[DependsJwtAuth])
async def update_toy_series(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='玩偶系列 ID')],
    obj: UpdateToySeriesParam,
) -> ResponseModel:
    count = await toy_service.update_toy_series(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/series/{pk}', summary='删除玩偶系列', dependencies=[DependsJwtAuth])
async def delete_toy_series(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='玩偶系列 ID')],
) -> ResponseModel:
    count = await toy_service.delete_toy_series(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.post('/system-prompt', summary='生成玩偶系统提示词', dependencies=[DependsJwtAuth])
async def generate_toy_system_prompt(
    obj: GenerateToySystemPromptParam,
) -> ResponseSchemaModel[GenerateToySystemPromptResult]:
    data = await toy_service.generate_system_prompt(obj)
    return response_base.success(data=data)


@router.get('', summary='分页获取玩偶列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_toy_paginated(
    db: CurrentSession,
    series_id: Annotated[int | None, Query(description='玩偶系列 ID')] = None,
    name: Annotated[str | None, Query(description='玩偶名称')] = None,
    nfc_code: Annotated[str | None, Query(description='NFC 编码')] = None,
    voice_language: Annotated[str | None, Query(description='音色语言，如 zh-CN、en-US、zh-TW')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetToyDetail]]:
    page_data = await toy_service.get_toy_list(
        db=db,
        series_id=series_id,
        name=name,
        nfc_code=nfc_code,
        voice_language=voice_language,
        status=status,
    )
    page_data['items'] = [GetToyDetail.model_validate(item) for item in page_data['items']]
    return response_base.success(data=page_data)


@router.get('/nfc-codes', summary='分页获取玩偶 NFC 绑定列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_toy_nfc_paginated(
    db: CurrentSession,
    toy_id: Annotated[int | None, Query(description='玩偶 ID')] = None,
    nfc_code: Annotated[str | None, Query(description='NFC 编码')] = None,
    status: Annotated[int | None, Query(description='状态：0 禁用，1 启用')] = None,
) -> ResponseSchemaModel[PageData[ToyNfcInfo]]:
    page_data = await toy_service.get_toy_nfc_list(
        db=db,
        toy_id=toy_id,
        nfc_code=nfc_code,
        status=status,
    )
    page_data['items'] = [ToyNfcInfo.model_validate(item) for item in page_data['items']]
    return response_base.success(data=page_data)


@router.post('/nfc-codes', summary='创建玩偶 NFC 绑定', dependencies=[DependsJwtAuth])
async def create_toy_nfc(
    db: CurrentSessionTransaction,
    obj: CreateToyNfcParam,
) -> ResponseSchemaModel[ToyNfcInfo]:
    binding = await toy_service.create_toy_nfc(db=db, obj=obj)
    return response_base.success(data=ToyNfcInfo.model_validate(binding))


@router.post('/nfc-codes/batch', summary='批量创建玩偶 NFC 绑定', dependencies=[DependsJwtAuth])
async def batch_create_toy_nfc(
    db: CurrentSessionTransaction,
    obj: BatchCreateToyNfcParam,
) -> ResponseSchemaModel[list[ToyNfcInfo]]:
    bindings = await toy_service.batch_create_toy_nfc(db=db, obj=obj)
    return response_base.success(data=[ToyNfcInfo.model_validate(item) for item in bindings])


@router.get('/nfc-codes/{pk}', summary='获取玩偶 NFC 绑定详情', dependencies=[DependsJwtAuth])
async def get_toy_nfc(
    db: CurrentSession,
    pk: Annotated[int, Path(description='NFC 绑定 ID')],
) -> ResponseSchemaModel[ToyNfcInfo]:
    binding = await toy_service.get_toy_nfc(db=db, pk=pk)
    return response_base.success(data=ToyNfcInfo.model_validate(binding))


@router.put('/nfc-codes/{pk}', summary='更新玩偶 NFC 绑定', dependencies=[DependsJwtAuth])
async def update_toy_nfc(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='NFC 绑定 ID')],
    obj: UpdateToyNfcParam,
) -> ResponseModel:
    count = await toy_service.update_toy_nfc(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/nfc-codes/{pk}', summary='删除玩偶 NFC 绑定', dependencies=[DependsJwtAuth])
async def delete_toy_nfc(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='NFC 绑定 ID')],
) -> ResponseModel:
    count = await toy_service.delete_toy_nfc(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.post('', summary='创建玩偶', dependencies=[DependsJwtAuth])
async def create_toy(
    db: CurrentSessionTransaction,
    obj: CreateToyParam,
) -> ResponseSchemaModel[GetToyDetail]:
    toy = await toy_service.create_toy(db=db, obj=obj)
    return response_base.success(data=GetToyDetail.model_validate(toy))


@router.get('/{pk}', summary='获取玩偶详情', dependencies=[DependsJwtAuth])
async def get_toy(
    db: CurrentSession,
    pk: Annotated[int, Path(description='玩偶 ID')],
) -> ResponseSchemaModel[GetToyDetail]:
    toy = await toy_service.get_toy(db=db, pk=pk)
    return response_base.success(data=GetToyDetail.model_validate(toy))


@router.put('/{pk}', summary='更新玩偶', dependencies=[DependsJwtAuth])
async def update_toy(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='玩偶 ID')],
    obj: UpdateToyParam,
) -> ResponseModel:
    count = await toy_service.update_toy(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除玩偶', dependencies=[DependsJwtAuth])
async def delete_toy(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='玩偶 ID')],
) -> ResponseModel:
    count = await toy_service.delete_toy(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
