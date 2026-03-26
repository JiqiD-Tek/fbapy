# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : feedback.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 11:21
"""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Path, Query

from backend.app.cloud.schema.feedback import (
    CreateFeedbackParam,
    GetFeedbackDetail,
    UpdateFeedbackParam,
)
from backend.app.cloud.schema.user import DeviceAuthParam
from backend.app.cloud.service.device.messaging import MessagingService
from backend.app.cloud.service.feedback_service import feedback_service
from backend.common.exception import errors
from backend.common.mqtt_broker import MQTTBroker, get_mqtt
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.auth import device_or_jwt_auth_verify
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

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
)
async def create_feedback(
    db: CurrentSessionTransaction,
    mqtt_client: Annotated[MQTTBroker, Depends(get_mqtt)],
    auth_ctx: Annotated[Any, Depends(device_or_jwt_auth_verify)],
    did: Annotated[str, Body(description='设备did')],
    status: Annotated[int, Body(description='状态(0：不需要日志上传 1：需要日志上传)')] = 0,
    category: Annotated[str | None, Body(description='反馈类型')] = None,
    content: Annotated[str | None, Body(description='反馈内容')] = None,
    pic_url: Annotated[str | None, Body(description='反馈图片地址')] = None,
    file_url: Annotated[str | None, Body(description='反馈文件地址')] = None,
    contact: Annotated[str | None, Body(description='联系方式')] = None,
    comment: Annotated[str | None, Body(description='处理备注')] = None,
) -> ResponseSchemaModel[GetFeedbackDetail]:
    if isinstance(auth_ctx, DeviceAuthParam) and did != auth_ctx.did:
        raise errors.RequestError(msg='设备 did 不匹配')

    obj = CreateFeedbackParam(
        did=did,
        category=category,
        content=content,
        pic_url=pic_url,
        file_url=file_url,
        contact=contact,
        comment=comment,
        status=status,
    )
    feedback = await feedback_service.create(db=db, obj=obj)

    if status == 1:
        messaging_service = MessagingService(mqtt_client=mqtt_client, did=did)
        await messaging_service.send_request_log(feedback_id=feedback.id)

    return response_base.success(data=feedback)


@router.put(
    '/{pk}',
    summary='更新日志',
)
async def update_feedback(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='反馈 ID')],
    obj: UpdateFeedbackParam,
    auth_ctx: Annotated[Any, Depends(device_or_jwt_auth_verify)],
) -> ResponseModel:
    if isinstance(auth_ctx, DeviceAuthParam):
        feedback = await feedback_service.get(db=db, pk=pk)
        if feedback.did != auth_ctx.did:
            raise errors.RequestError(msg='无权更新其他设备的反馈')

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
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='反馈 ID')],
) -> ResponseModel:
    count = await feedback_service.delete(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
