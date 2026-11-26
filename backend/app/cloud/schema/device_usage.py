from datetime import date
from typing import Literal

from pydantic import Field

from backend.common.schema import SchemaBase

DeviceUsageEventType = Literal['CHAT', 'STORY']


class UpdateDeviceUsageParam(SchemaBase):
    event_type: DeviceUsageEventType = Field(description='使用事件类型：CHAT、STORY')
    event_key: str = Field(min_length=1, max_length=256, description='事件幂等标识')
    quantity: int = Field(gt=0, description='本次使用量：CHAT 为秒数，STORY 为次数')


class DeviceUsageQuotaResult(SchemaBase):
    did: str = Field(description='设备 DID')
    usage_date: date = Field(description='业务日期')
    chat_seconds: int = Field(ge=0, description='当天 AI 对话已使用秒数')
    story_count: int = Field(ge=0, description='当天 AI 故事已创建次数')
    chat_seconds_remaining: int | None = Field(description='当天剩余对话秒数，NULL 表示不限制')
    story_count_remaining: int | None = Field(description='当天剩余故事次数，NULL 表示不限制')
