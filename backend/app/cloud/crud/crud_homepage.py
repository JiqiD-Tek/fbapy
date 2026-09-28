# -*- coding: UTF-8 -*-
"""首页配置数据访问。"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model import Homepage
from backend.app.cloud.schema.homepage import HomepageType, UpdateHomepageParam


class CRUDHomepage(CRUDPlus[Homepage]):
    """首页配置数据访问对象。"""

    async def get_by_type(self, db: AsyncSession, config_type: HomepageType) -> Homepage | None:
        stmt = await self.select_order('id', 'asc', config_type=config_type.value)
        result = await db.execute(stmt.limit(1))
        return result.scalars().first()

    async def create_config(
            self,
            db: AsyncSession,
            config_type: HomepageType,
            content: list[Any],
    ) -> Homepage:
        config = Homepage(config_type=config_type.value, content=content)
        db.add(config)
        await db.flush()
        return config

    async def update_config(self, db: AsyncSession, pk: int, content: list[Any]) -> int:
        return await self.update_model_by_column(db, {'content': content}, id=pk)


homepage_dao: CRUDHomepage = CRUDHomepage(Homepage)
