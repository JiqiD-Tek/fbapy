# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : device.py
@Author  : guhua@jiqid.com
@Date    : 2025/12/09 13:50
"""
from typing import Any
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domain.crud.device.crud_device import device_dao
from backend.app.domain.crud.device.crud_device_usage import device_usage_dao
from backend.app.domain.model import Device
from backend.app.domain.schema.device.device import (
    UpdateDeviceParam,
    DeleteDeviceParam,
)
from backend.app.domain.schema.device.device_usage import CreateDeviceUsageParam, UsageStatus, UpdateDeviceUsageParam
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.common.security.auth import identity_verifier
from backend.utils.timezone import timezone


class DeviceService:
    """设备服务类"""
    MAX_ALLOW_QUOTA = 600  # 最大允许时长

    async def allocate_quota(self, db: AsyncSession, mac: str, did: str) -> int:
        """检查设备权限"""
        # 1.检测设备使用记录，结束使用记录
        balance = await self.end_usage(db, mac, did)
        if balance <= 0:
            raise errors.AuthorizationError(msg='余额不足')

        # 2.添加设备使用记录
        quota = min(balance, self.MAX_ALLOW_QUOTA)  # 申请时长
        param_data = {"did": did, "apply_quota": quota, "start_time": timezone.now()}
        obj = CreateDeviceUsageParam.model_construct(**param_data)
        await device_usage_dao.create(db, obj)
        return quota

    async def end_usage(self, db: AsyncSession, mac: str, did: str) -> int:
        """ 结束设备使用 """
        credentials = identity_verifier.derive_credentials(mac=mac)
        if did != credentials["did"]:
            raise errors.AuthorizationError(msg='权限不足')

        device = await self.get_by_did(db=db, did=did)
        models = await device_usage_dao.get_by_did_status(db, did, UsageStatus.ACTIVE)
        if not models:
            return device.balance

        total_quota = 0
        now = timezone.now()
        for model in models:
            actual_quota = min(model.apply_quota, (now - model.start_time).seconds)
            await device_usage_dao.update(db, pk=model.id, obj=UpdateDeviceUsageParam(
                actual_quota=actual_quota, end_time=now, status=UsageStatus.COMPLETED, remark=""))
            total_quota += actual_quota

        await device_dao.update_model(db, device.id, {'balance': device.balance - total_quota})
        return device.balance - total_quota

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> Device:
        """ 获取设备详情 """
        device = await device_dao.get(db, pk)
        if not device:
            raise errors.NotFoundError(msg="设备不存在")
        return device

    @staticmethod
    async def get_by_did(*, db: AsyncSession, did: str) -> Device:
        """ 获取设备详情 """
        device = await device_dao.get_by_did(db, did)
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
    ) -> dict[str, Any]:
        """ 获取设备列表（支持分页和查询条件） """
        device_select = await device_dao.get_select(
            did=did,
            sn=sn,
            mac=mac,
            model=model,
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
