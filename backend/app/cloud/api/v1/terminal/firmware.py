# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : firmware.py
@Author  : OpenAI
@Date    : 2026/03/26
"""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.cloud.schema.firmware import (
    BatchSetFirmwareWhitelistParam,
    CreateFirmwareParam,
    FirmwareReleaseScope,
    GetFirmwareDetail,
    GetFirmwareWhitelistDetail,
    UpdateFirmwareParam,
    UpdateFirmwareWhitelistParam,
)
from backend.app.cloud.schema.user import DeviceAuthParam
from backend.app.cloud.service.firmware_service import firmware_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.auth import DependsDeviceAuth
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/upgrade', summary='获取可升级固件版本')
async def get_upgrade_firmware(
    db: CurrentSession,
    version_code: Annotated[int, Query(description='当前固件版本代码')],
    auth_ctx: DeviceAuthParam = DependsDeviceAuth,
) -> ResponseSchemaModel[GetFirmwareDetail | None]:
    data = await firmware_service.get_upgrade(
        db=db,
        device_did=auth_ctx.did,
        device_model=auth_ctx.model,
        version_code=version_code,
    )
    return response_base.success(data=data)


@router.get('/whitelist', summary='分页获取固件白名单', dependencies=[DependsJwtAuth, DependsPagination])
async def get_firmware_whitelist_list(
    db: CurrentSession,
    firmware_id: Annotated[int | None, Query(description='固件 ID')] = None,
    device_did: Annotated[str | None, Query(description='设备 DID')] = None,
    enabled: Annotated[bool | None, Query(description='是否启用')] = None,
) -> ResponseSchemaModel[PageData[GetFirmwareWhitelistDetail]]:
    page_data = await firmware_service.get_whitelist_list(
        db=db,
        firmware_id=firmware_id,
        device_did=device_did,
        enabled=enabled,
    )
    return response_base.success(data=page_data)


@router.post('/whitelist', summary='批量设置固件白名单', dependencies=[DependsJwtAuth])
async def set_firmware_whitelist(
    db: CurrentSessionTransaction,
    obj: BatchSetFirmwareWhitelistParam,
) -> ResponseSchemaModel[list[GetFirmwareWhitelistDetail]]:
    data = await firmware_service.set_whitelist(db=db, obj=obj)
    return response_base.success(data=data)


@router.put('/whitelist/{pk}', summary='更新固件白名单', dependencies=[DependsJwtAuth])
async def update_firmware_whitelist(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='白名单 ID')],
    obj: UpdateFirmwareWhitelistParam,
) -> ResponseModel:
    count = await firmware_service.update_whitelist(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/whitelist/{pk}', summary='删除固件白名单', dependencies=[DependsJwtAuth])
async def delete_firmware_whitelist(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='白名单 ID')],
) -> ResponseModel:
    count = await firmware_service.delete_whitelist(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.get('/{pk}', summary='获取固件详情', dependencies=[DependsJwtAuth])
async def get_firmware(
    db: CurrentSession,
    pk: Annotated[int, Path(description='固件 ID')],
) -> ResponseSchemaModel[GetFirmwareDetail]:
    data = await firmware_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='分页获取固件列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_firmware_list(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='固件名称')] = None,
    version: Annotated[str | None, Query(description='固件版本')] = None,
    device_model: Annotated[str | None, Query(description='适配设备型号')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
    is_latest: Annotated[bool | None, Query(description='是否最新')] = None,
    release_scope: Annotated[FirmwareReleaseScope | None, Query(description='发布范围')] = None,
) -> ResponseSchemaModel[PageData[GetFirmwareDetail]]:
    page_data = await firmware_service.get_list(
        db=db,
        name=name,
        version=version,
        device_model=device_model,
        status=status,
        is_latest=is_latest,
        release_scope=release_scope,
    )
    return response_base.success(data=page_data)


@router.post('', summary='创建固件', dependencies=[DependsJwtAuth])
async def create_firmware(
    db: CurrentSessionTransaction,
    obj: CreateFirmwareParam,
) -> ResponseSchemaModel[GetFirmwareDetail]:
    data = await firmware_service.create(db=db, obj=obj)
    return response_base.success(data=data)


@router.put('/{pk}', summary='更新固件', dependencies=[DependsJwtAuth])
async def update_firmware(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='固件 ID')],
    obj: UpdateFirmwareParam,
) -> ResponseModel:
    count = await firmware_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除固件', dependencies=[DependsJwtAuth])
async def delete_firmware(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='固件 ID')],
) -> ResponseModel:
    count = await firmware_service.delete(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
