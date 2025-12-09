# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : feedback.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 14:47
"""
from datetime import datetime
from typing import Optional

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class FeedbackSchemaBase(SchemaBase):
    """反馈基础模型"""

    device_id: int = Field(description='设备ID')
    user_id: int = Field(description='用户ID')

    name: Optional[str] = Field(None, description='反馈名称')
    pic_url: Optional[str] = Field(None, description='反馈图片地址')
    file_url: Optional[str] = Field(None, description='反馈文件地址')
    content: Optional[str] = Field(None, description='反馈内容')
    comment: Optional[str] = Field(None, description='处理备注')
    status: Optional[int] = Field(default=0, description='状态(0初始化 1设备处理失败 2设备处理完成 3后台处理完成)')


class CreateFeedbackParam(FeedbackSchemaBase):
    """创建反馈参数"""


class UpdateFeedbackParam(SchemaBase):
    """更新反馈参数"""

    pic_url: Optional[str] = Field(None, description='反馈图片地址')
    file_url: Optional[str] = Field(None, description='反馈文件地址')
    content: Optional[str] = Field(None, description='反馈内容')


class DeleteFeedbackParam(SchemaBase):
    """删除反馈参数"""

    pks: list[int] = Field(description='反馈 ID 列表')


class GetFeedbackDetail(FeedbackSchemaBase):
    """反馈详情"""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='反馈 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: Optional[datetime] = Field(None, description='更新时间')
