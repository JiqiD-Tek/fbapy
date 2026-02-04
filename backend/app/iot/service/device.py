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

from backend.app.iot.crud.device.crud_device import device_dao
from backend.app.iot.crud.device.crud_device_usage import device_usage_dao
from backend.app.iot.model import Device
from backend.app.iot.schema.device.device import (
    UpdateDeviceParam,
    DeleteDeviceParam,
)
from backend.app.iot.schema.device.device_usage import CreateDeviceUsageParam, UsageStatus, UpdateDeviceUsageParam
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.common.response.response_code import CustomErrorCode
from backend.common.security.auth import identity_verifier
from backend.utils.timezone import timezone


class DeviceService:
    """设备服务类"""
    MAX_ALLOW_QUOTA = 600  # 最大允许时长

    async def allocate_quota(self, db: AsyncSession, mac: str, did: str) -> int:
        """为设备分配可用配额并创建使用记录"""
        # 1. 先结算历史使用，拿到最新余额
        quota = await self.end_usage(db, mac, did)
        if quota <= 0:
            raise errors.CustomError(error=CustomErrorCode.DEVICE_QUOTA_NOT_ENOUGH)

        # 2. 计算本次可申请配额
        alloc_quota = min(quota, self.MAX_ALLOW_QUOTA)
        if alloc_quota <= 0:
            raise errors.CustomError(error=CustomErrorCode.DEVICE_QUOTA_NOT_ENOUGH)

        # 3. 创建使用记录
        now = timezone.now()
        usage = CreateDeviceUsageParam.model_construct(
            did=did,
            apply_quota=alloc_quota,
            start_time=now,
        )

        await device_usage_dao.create(db, usage)

        return alloc_quota

    async def end_usage(self, db: AsyncSession, mac: str, did: str) -> int:
        """结束设备使用并结算配额"""
        # 1. 权限校验
        credentials = identity_verifier.derive_credentials(mac=mac)
        if did != credentials.get("did"):
            raise errors.CustomError(error=CustomErrorCode.DEVICE_ILLEGAL)

        # 2. 获取设备
        device = await self.get_by_did(db=db, did=did)

        # 3. 获取所有进行中的使用记录
        active_usages = await device_usage_dao.get_by_did_status(db, did, UsageStatus.ACTIVE)
        if not active_usages:
            return device.quota

        now = timezone.now()
        total_consumed = 0

        # 4. 结算每条 usage
        for usage in active_usages:
            duration_seconds = int((now - usage.start_time).total_seconds())
            actual_quota = min(usage.apply_quota, max(duration_seconds, 0))

            await device_usage_dao.update(
                db,
                pk=usage.id,
                obj=UpdateDeviceUsageParam(
                    actual_quota=actual_quota,
                    end_time=now,
                    status=UsageStatus.COMPLETED,
                    remark="",
                ),
            )

            total_consumed += actual_quota

        # 5. 扣减余额（防止扣成负数）
        new_quota = max(device.quota - total_consumed, 0)
        await device_dao.update_model(
            db,
            device.id,
            {"quota": new_quota},
        )

        return new_quota

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
