# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : feedback.py
@Author  : OpenAI
@Date    : 2025/11/25 14:47
"""

from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class FeedbackSchemaBase(SchemaBase):
    device_did: str = Field(description='设备did')
    category: str | None = Field(None, description='反馈类型')
    content: str | None = Field(None, description='反馈内容')
    pic_url: str | None = Field(None, description='反馈图片地址')
    file_url: str | None = Field(None, description='反馈文件地址')
    contact: str | None = Field(None, description='联系方式')
    comment: str | None = Field(None, description='处理备注')
    status: int | None = Field(default=0, description='状态(0：不需要日志上传 1：需要日志上传)')


class CreateFeedbackParam(FeedbackSchemaBase):
    pass


class UpdateFeedbackParam(SchemaBase):
    category: str | None = Field(None, description='反馈类型')
    content: str | None = Field(None, description='反馈内容')
    pic_url: str | None = Field(None, description='反馈图片地址')
    file_url: str | None = Field(None, description='反馈文件地址')
    contact: str | None = Field(None, description='联系方式')
    comment: str | None = Field(None, description='处理备注')
    status: int | None = Field(None, description='状态(0：不需要日志上传 1：需要日志上传)')


class DeleteFeedbackParam(SchemaBase):
    pks: list[int] = Field(description='反馈 ID 列表')


class GetFeedbackDetail(FeedbackSchemaBase):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='反馈 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
