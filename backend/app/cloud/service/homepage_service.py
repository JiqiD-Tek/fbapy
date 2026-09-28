# -*- coding: UTF-8 -*-
"""首页配置服务。"""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.crud_homepage import homepage_dao
from backend.app.cloud.schema.homepage import HomepageDetail, HomepageType, UpdateHomepageParam


class HomepageService:
    """首页配置服务。"""

    @staticmethod
    async def get_config(*, db: AsyncSession) -> HomepageDetail:
        configs = {
            config_type: await homepage_dao.get_by_type(db, config_type)
            for config_type in HomepageType
        }
        return HomepageDetail(
            banner=configs[HomepageType.banner].content
            if configs[HomepageType.banner] else [],
            newest=configs[HomepageType.newest].content
            if configs[HomepageType.newest] else [],
            featured=configs[HomepageType.featured].content
            if configs[HomepageType.featured] else [],
        )

    @staticmethod
    async def update_config(*, db: AsyncSession, obj: UpdateHomepageParam) -> HomepageDetail:
        values = {
            HomepageType.banner: obj.banner,
            HomepageType.newest: obj.newest,
            HomepageType.featured: obj.featured,
        }
        for config_type, content in values.items():
            config = await homepage_dao.get_by_type(db, config_type)
            if config is None:
                await homepage_dao.create_config(db, config_type, content)
            else:
                await homepage_dao.update_config(db, config.id, content)
        return HomepageDetail.model_validate(obj)


homepage_service: HomepageService = HomepageService()
