# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : router.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 11:11
"""

from fastapi import APIRouter

from backend.app.cloud.api.v1.billing import router as billing_router
from backend.app.cloud.api.v1.terminal import router as terminal_router
from backend.app.cloud.api.v1.resource import router as resource_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH, tags=['Cloud API'])

v1.include_router(resource_router, prefix='/resource', tags=['资源管理'])
v1.include_router(terminal_router, prefix='/terminal', tags=['终端能力'])
v1.include_router(billing_router, prefix='/billing', tags=['计费能力'])
