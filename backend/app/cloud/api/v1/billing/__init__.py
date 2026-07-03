# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : __init__.py.py
@Author  : guhua@jiqid.com
@Date    : 2026/07/01 15:29
"""

from fastapi import APIRouter

from backend.app.cloud.api.v1.billing.debit import router as debit_router
from backend.app.cloud.api.v1.billing.session import router as session_router

router = APIRouter()

router.include_router(session_router, prefix='/session', tags=['计费会话'])
router.include_router(debit_router, prefix='/usage', tags=['计费扣费'])
