# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : feedback.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 11:21
"""

from typing import Annotated, Optional
from fastapi import APIRouter, Path, Query, Depends, Body

from backend.common.mqtt_broker import get_mqtt, MQTTBroker
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth

from backend.app.iot.service.feedback import feedback_service
from backend.app.iot.service.messaging import MessagingService
from backend.app.iot.service.storage import storage_service

from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.app.iot.schema.feedback import GetFeedbackDetail, CreateFeedbackParam, UpdateFeedbackParam, \
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
        did: Annotated[str | None, Query(description='设备did')] = None,
        status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetFeedbackDetail]]:
    page_data = await feedback_service.get_list(db=db, name=name, did=did, status=status)
    return response_base.success(data=page_data)


@router.post(
    '',
    summary='创建日志（设备主动上报日志反馈、云端主动拉取设备日志）',
    # dependencies=[DependsJwtAuth, ],
)
async def create_feedback(
        db: CurrentSessionTransaction,
        mqtt_client: MQTTBroker = Depends(get_mqtt),
        did: str = Body(..., description='设备did'),
        status: int = Body(default=0, description='状态(0：不需要日志上传 1：需要日志上传)'),
        category: Optional[str] = Body(None, description='反馈类型'),
        content: Optional[str] = Body(None, description='反馈内容'),
        pic_url: Optional[str] = Body(None, description='反馈图片地址'),
        file_url: Optional[str] = Body(None, description='反馈文件地址'),
        contact: Optional[str] = Body(None, description='联系方式'),
        comment: Optional[str] = Body(None, description='处理备注'),

) -> ResponseSchemaModel[GetFeedbackDetail]:
    obj = CreateFeedbackParam(
        did=did, category=category, content=content, pic_url=pic_url,
        file_url=file_url, contact=contact, comment=comment, status=status,
    )
    feedback = await feedback_service.create(db=db, obj=obj)

    if status == 1:
        messaging_service = MessagingService(mqtt_client=mqtt_client, did=did)
        await messaging_service.send_request_log(feedback_id=feedback.id)

    return response_base.success(data=feedback)


@router.put(
    '/{pk}',
    summary='更新日志',
    # dependencies=[DependsJwtAuth, ],
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
