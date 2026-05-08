# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : report.py
@Author  : guhua@jiqid.com
@Date    : 2026/04/27 09:36
"""

from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.app.cloud.schema.resource.report import UsageReport, UsageReportPreview
from backend.app.cloud.service.resource.report_service import report_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()


@router.get(
    '/preview',
    summary='获取数据预览',
    dependencies=[DependsJwtAuth]
)
async def get_usage_preview(
        request: Request,
        db: CurrentSession,
        baby_id: Annotated[int, Query(description='宝宝 ID')],
) -> ResponseSchemaModel[UsageReportPreview]:
    data = await report_service.get_usage_preview(
        db=db,
        user_id=request.user.id,
        baby_id=baby_id,
    )
    return response_base.success(data=data)


@router.get(
    '/usage',
    summary='获取使用报告',
    dependencies=[DependsJwtAuth]
)
async def get_usage_report(
        request: Request,
        db: CurrentSession,
        baby_id: Annotated[int, Query(description='宝宝 ID')],
) -> ResponseSchemaModel[UsageReport]:
    data = await report_service.get_usage_report(
        db=db,
        user_id=request.user.id,
        baby_id=baby_id,
    )
    return response_base.success(data=data)
