# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : app_service.py
@Author  : guhua@jiqid.com
@Date    : 2025/12/09 13:52
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.crud_app import app_dao
from backend.app.cloud.model import App
from backend.app.cloud.schema.app import (
    CreateAppParam,
    UpdateAppParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data


class AppService:
    """应用服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> App:
        """获取应用详情"""
        app = await app_dao.get(db, pk)
        if not app:
            raise errors.NotFoundError(msg='应用不存在')
        return app

    @staticmethod
    async def get_all(*, db: AsyncSession) -> Sequence[App]:
        """获取所有应用"""
        return await app_dao.get_all(db)

    @staticmethod
    async def get_upgrade(
        *,
        db: AsyncSession,
        package_name: str,
        market_code: str | None,
        version_code: int,
    ) -> App | None:
        """Get the next enabled application version for a client."""
        package_name = package_name.strip()
        if not package_name:
            raise errors.RequestError(msg='应用包名不能为空')
        if version_code < 0:
            raise errors.RequestError(msg='当前应用版本代码不正确')
        if market_code is not None:
            market_code = AppService._normalize_market_code(market_code)
        return await app_dao.get_upgrade_app(
            db,
            package_name=package_name,
            market_code=market_code,
            version_code=version_code,
        )

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        name: str | None = None,
        package_name: str | None = None,
        market_code: str | None = None,
        status: int | None = None,
    ) -> dict[str, Any]:
        """获取应用列表（支持分页和查询条件）"""
        app_select = await app_dao.get_select(
            name=name,
            package_name=package_name,
            market_code=market_code,
            status=status,
        )
        return await paging_data(db, app_select)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateAppParam) -> App:
        """创建应用"""
        if obj.market_code is not None:
            obj = obj.model_copy(update={'market_code': AppService._normalize_market_code(obj.market_code)})
        return await app_dao.create(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateAppParam) -> int:
        """更新应用"""
        await AppService.get(db=db, pk=pk)
        if obj.market_code is not None:
            obj = obj.model_copy(update={'market_code': AppService._normalize_market_code(obj.market_code)})
        return await app_dao.update(db, pk, obj)

    @staticmethod
    def _normalize_market_code(market_code: str) -> str | None:
        normalized = market_code.strip().lower()
        return None if normalized in {'', 'global'} else normalized

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """批量删除应用"""
        return await app_dao.delete(db, pk)


app_service: AppService = AppService()
