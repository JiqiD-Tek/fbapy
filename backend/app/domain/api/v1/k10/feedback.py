# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : feedback.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 11:21
"""
import uuid
from typing import Annotated
from fastapi import APIRouter, Path, Query

from backend.app.domain.service.feedback import feedback_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth

from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.app.domain.schema.feedback import GetFeedbackDetail, CreateFeedbackParam, UpdateFeedbackParam, \
    DeleteFeedbackParam

router = APIRouter()


@router.get('/{pk}', summary='获取日志详情', dependencies=[DependsJwtAuth])
async def get_feedback(
        db: CurrentSession, pk: Annotated[int, Path(description='日志 ID')]
) -> ResponseSchemaModel[GetFeedbackDetail]:
    data = feedback_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '',
    summary='分页获取所有反馈',
    dependencies=[
        DependsJwtAuth,
        DependsPagination,
    ],
)
async def get_feedback_paginated(
        db: CurrentSession,
        name: Annotated[str | None, Query(description='名称')] = None,
        device_id: Annotated[int | None, Query(description='设备ID')] = None,
        user_id: Annotated[int | None, Query(description='用户ID')] = None,
        status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetFeedbackDetail]]:
    page_data = await feedback_service.get_list(db=db, name=name, device_id=device_id, user_id=user_id, status=status)
    return response_base.success(data=page_data)


@router.post(
    '',
    summary='创建日志（设备主动上报日志反馈、云端主动拉取设备日志）',
    dependencies=[
        DependsJwtAuth,
    ],
)
async def create_feedback(
        db: CurrentSessionTransaction,
        obj: CreateFeedbackParam,
) -> ResponseSchemaModel[GetFeedbackDetail]:
    if obj.status == 0:
        obj.file_url = f"https://media.jiqid.com/K10/feedback/log/{uuid.uuid4().hex}.log"  # 云端日志文件地址

    feedback = await feedback_service.create(db=db, obj=obj)

    if obj.status == 'cloud':
        pass  # TODO mqtt

    return response_base.success(data=feedback)


@router.put(
    '/{pk}',
    summary='更新日志',
    dependencies=[
        DependsJwtAuth,
    ],
)
async def update_feedback(
        db: CurrentSessionTransaction,
        pk: Annotated[int, Path(description='反馈 ID')],
        obj: UpdateFeedbackParam,
) -> ResponseModel:
    count = await feedback_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/{pk}',
    summary='删除日志',
    dependencies=[
        DependsJwtAuth,
    ],
)
async def delete_feedback(
        db: CurrentSessionTransaction, obj: DeleteFeedbackParam) -> ResponseModel:
    count = await feedback_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()
