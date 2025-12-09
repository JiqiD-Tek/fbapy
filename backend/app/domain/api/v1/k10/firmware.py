# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : firmware.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 11:20
"""

from typing import Annotated
from fastapi import APIRouter, Path, Query

from backend.app.domain.service.firmware import firmware_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseSchemaModel, ResponseModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

from backend.app.domain.schema.firmware import (
    GetFirmwareDetail,
    CreateFirmwareParam,
    UpdateFirmwareParam,
    DeleteFirmwareParam,
)

router = APIRouter()


# =============================
# 获取固件详情
# =============================
@router.get(
    "/{pk}",
    summary="获取固件详情",
    dependencies=[DependsJwtAuth],
)
async def get_firmware(
        db: CurrentSession,
        pk: Annotated[int, Path(description="固件 ID")],
) -> ResponseSchemaModel[GetFirmwareDetail]:
    data = firmware_service.get(db=db, pk=pk)
    return response_base.success(data=data)


# =============================
# 分页查询固件列表
# =============================
@router.get(
    "",
    summary="分页获取固件列表",
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_firmware_list(
        db: CurrentSession,
        name: Annotated[str | None, Query(description="固件名称")] = None,
        version: Annotated[str | None, Query(description="固件版本")] = None,
        device_model: Annotated[str | None, Query(description="适配设备型号")] = None,
        status: Annotated[int | None, Query(description="状态")] = None,
        is_latest: Annotated[bool | None, Query(description="是否最新")] = None,
) -> ResponseSchemaModel[PageData[GetFirmwareDetail]]:
    page_data = await firmware_service.get_list(
        db=db,
        name=name,
        version=version,
        device_model=device_model,
        status=status,
        is_latest=is_latest,
    )
    return response_base.success(data=page_data)


# =============================
# 创建固件
# =============================
@router.post(
    "",
    summary="创建固件",
    dependencies=[DependsJwtAuth],
)
async def create_firmware(
        db: CurrentSessionTransaction,
        obj: CreateFirmwareParam,
) -> ResponseSchemaModel[GetFirmwareDetail]:
    data = await firmware_service.create(db=db, obj=obj)
    return response_base.success(data=data)


# =============================
# 更新固件
# =============================
@router.put(
    "/{pk}",
    summary="更新固件",
    dependencies=[DependsJwtAuth],
)
async def update_firmware(
        db: CurrentSessionTransaction,
        pk: Annotated[int, Path(description="固件 ID")],
        obj: UpdateFirmwareParam,
) -> ResponseModel:
    count = await firmware_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


# =============================
# 删除固件
# =============================
@router.delete(
    "/{pk}",
    summary="删除固件",
    dependencies=[DependsJwtAuth],
)
async def delete_firmware(
        db: CurrentSessionTransaction,
        obj: DeleteFirmwareParam,
) -> ResponseModel:
    count = await firmware_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()
