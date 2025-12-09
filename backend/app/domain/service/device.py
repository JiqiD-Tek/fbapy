# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : device.py
@Author  : guhua@jiqid.com
@Date    : 2025/12/09 13:50
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domain.crud.crud_device import device_dao
from backend.app.domain.model import Device
from backend.app.domain.schema.device import (
    CreateDeviceParam,
    UpdateDeviceParam,
    DeleteDeviceParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data


class DeviceService:
    """设备服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> Device:
        """ 获取设备详情 """
        device = await device_dao.get(db, pk)
        if not device:
            raise errors.NotFoundError(msg="设备不存在")
        return device

    @staticmethod
    async def get_all(*, db: AsyncSession) -> Sequence[Device]:
        """ 获取所有设备 """
        devices = await device_dao.get_all(db)
        return devices

    @staticmethod
    async def get_list(
            *,
            db: AsyncSession,
            did: str | None = None,
            sn: str | None = None,
            mac: str | None = None,
            model: str | None = None,
            user_id: int | None = None,
    ) -> dict[str, Any]:
        """ 获取设备列表（支持分页和查询条件） """
        device_select = await device_dao.get_select(
            did=did,
            sn=sn,
            mac=mac,
            model=model,
            user_id=user_id,
        )
        return await paging_data(db, device_select)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateDeviceParam) -> int:
        """ 更新设备 """
        # 检查是否存在
        device = await device_dao.get(db, pk)
        if not device:
            raise errors.NotFoundError(msg="设备不存在")

        # 更新字段
        count = await device_dao.update(db, pk, obj)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteDeviceParam) -> int:
        """ 批量删除设备 """
        count = await device_dao.delete(db, obj.pks)
        return count


device_service: DeviceService = DeviceService()
