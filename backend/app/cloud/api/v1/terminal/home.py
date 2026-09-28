# -*- coding: UTF-8 -*-
"""首页配置接口。"""

from fastapi import APIRouter

from backend.app.cloud.schema.homepage import HomepageDetail, UpdateHomepageParam
from backend.app.cloud.service.homepage_service import homepage_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.auth import DependsDeviceOrJwtAuth
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('', summary='获取首页配置', dependencies=[DependsDeviceOrJwtAuth])
async def get_homepage(db: CurrentSession) -> ResponseSchemaModel[HomepageDetail]:
    data = await homepage_service.get_config(db=db)
    return response_base.success(data=data)


@router.put('', summary='更新首页配置', dependencies=[DependsJwtAuth])
async def update_homepage(
        db: CurrentSessionTransaction,
        obj: UpdateHomepageParam,
) -> ResponseSchemaModel[HomepageDetail]:
    data = await homepage_service.update_config(db=db, obj=obj)
    return response_base.success(data=data)
