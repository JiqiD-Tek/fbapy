# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : app.py
@Author  : guhua@jiqid.com
@Date    : 2025/12/09 13:52
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domain.crud.crud_app import app_dao
from backend.app.domain.model import App
from backend.app.domain.schema.app import (
    CreateAppParam,
    UpdateAppParam,
    DeleteAppParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data


class AppService:
    """应用服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> App:
        """ 获取应用详情 """
        app = await app_dao.get(db, pk)
        if not app:
            raise errors.NotFoundError(msg="应用不存在")
        return app

    @staticmethod
    async def get_all(*, db: AsyncSession) -> Sequence[App]:
        """ 获取所有应用 """
        apps = await app_dao.get_all(db)
        return apps

    @staticmethod
    async def get_list(
            *,
            db: AsyncSession,
            name: str | None = None,
            package_name: str | None = None,
            status: int | None = None,
    ) -> dict[str, Any]:
        """ 获取应用列表（支持分页和查询条件） """
        app_select = await app_dao.get_select(
            name=name,
            package_name=package_name,
            status=status,
        )
        return await paging_data(db, app_select)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateAppParam) -> None:
        """ 创建应用 """
        await app_dao.create(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateAppParam) -> int:
        """ 更新应用 """
        app = await app_dao.get(db, pk)
        if not app:
            raise errors.NotFoundError(msg="应用不存在")

        count = await app_dao.update(db, pk, obj)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteAppParam) -> int:
        """ 批量删除应用 """
        count = await app_dao.delete(db, obj.pks)
        return count


app_service: AppService = AppService()
