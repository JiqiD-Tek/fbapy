# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : router.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 11:11
"""
from fastapi import APIRouter

from backend.app.domain.api.v1.k10 import router as k10_router

from backend.core.conf import settings

v1 = APIRouter(prefix=f'{settings.FASTAPI_API_V1_PATH}/domain')

v1.include_router(k10_router, tags=['K10业务'])
