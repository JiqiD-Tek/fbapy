# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : router.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 11:11
"""

from fastapi import APIRouter

from backend.app.iot.api.v1.cloud import router as cloud_router
from backend.app.iot.api.v1.k11 import router as k11_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH, tags=['V1'])

v1.include_router(cloud_router, prefix='/cloud', tags=['云端资源'])
v1.include_router(k11_router, prefix='/iot', tags=['硬件IOT'])
