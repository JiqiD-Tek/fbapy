# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : firmware_service.py
@Author  : OpenAI
@Date    : 2026/03/26
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.crud_firmware import firmware_dao
from backend.app.cloud.model import Firmware
from backend.app.cloud.schema.firmware import CreateFirmwareParam, UpdateFirmwareParam
from backend.common.exception import errors
from backend.common.pagination import paging_data


class FirmwareService:
    """固件服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> Firmware:
        firmware = await firmware_dao.get(db, pk)
        if not firmware:
            raise errors.NotFoundError(msg='固件不存在')
        return firmware

    @staticmethod
    async def get_all(*, db: AsyncSession) -> Sequence[Firmware]:
        return await firmware_dao.get_all(db)

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
        firmware_select = await firmware_dao.get_select(
            name=name,
            version=version,
            device_model=device_model,
            status=status,
            is_latest=is_latest,
        )
        return await paging_data(db, firmware_select)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateFirmwareParam) -> Firmware:
        return await firmware_dao.create(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateFirmwareParam) -> int:
        firmware = await firmware_dao.get(db, pk)
        if not firmware:
            raise errors.NotFoundError(msg='固件不存在')

        payload = obj.model_dump(exclude_unset=True)
        if not payload:
            raise errors.RequestError(msg='更新内容不能为空')

        return await firmware_dao.update(db, pk, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        firmware = await firmware_dao.get(db, pk)
        if not firmware:
            raise errors.NotFoundError(msg='固件不存在')

        return await firmware_dao.delete(db, pk)


firmware_service: FirmwareService = FirmwareService()
