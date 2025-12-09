# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : firmware.py
@Author  : guhua@jiqid.com
@Date    : 2025/12/09 14:01
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domain.crud.crud_firmware import firmware_dao
from backend.app.domain.model import Firmware
from backend.app.domain.schema.firmware import (
    CreateFirmwareParam,
    UpdateFirmwareParam,
    DeleteFirmwareParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data


class FirmwareService:
    """固件服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> Firmware:
        """ 获取固件详情 """
        firmware = await firmware_dao.get(db, pk)
        if not firmware:
            raise errors.NotFoundError(msg="固件不存在")
        return firmware

    @staticmethod
    async def get_all(*, db: AsyncSession) -> Sequence[Firmware]:
        """ 获取所有固件 """
        firmwares = await firmware_dao.get_all(db)
        return firmwares

    @staticmethod
    async def get_list(
            *,
            db: AsyncSession,
            name: str | None = None,
            version: str | None = None,
            device_model: str | None = None,
            status: int | None = None,
            is_latest: bool | None = None,
    ) -> dict[str, Any]:
        """ 获取固件列表（支持分页和查询条件） """
        firmware_select = await firmware_dao.get_select(
            name=name,
            version=version,
            device_model=device_model,
            status=status,
            is_latest=is_latest,
        )
        return await paging_data(db, firmware_select)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateFirmwareParam) -> None:
        """ 创建固件 """
        # 可在此添加版本唯一性、文件MD5校验等
        await firmware_dao.create(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateFirmwareParam) -> int:
        """ 更新固件 """
        firmware = await firmware_dao.get(db, pk)
        if not firmware:
            raise errors.NotFoundError(msg="固件不存在")

        count = await firmware_dao.update(db, pk, obj)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteFirmwareParam) -> int:
        """ 批量删除固件 """
        count = await firmware_dao.delete(db, obj.pks)
        return count


firmware_service: FirmwareService = FirmwareService()
