from datetime import date
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, StringConstraints, model_validator

from backend.common.schema import SchemaBase

DeviceUsageEventType = Literal['CHAT', 'STORY']


class UpdateDeviceUsageParam(SchemaBase):
    """上报原始用量，由服务端换算为统一使用量。"""

    model_config = ConfigDict(extra='forbid')

    event_type: DeviceUsageEventType = Field(description='事件来源：CHAT 对话，STORY 故事创作')
    event_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)] = Field(
        description='事件幂等标识，同一事件重试使用同一标识',
    )
    asr_characters: int = Field(ge=0, description='本次语音识别文本的字符数，同时估算大模型输入量')
    tts_characters: int = Field(ge=0, description='本次语音合成文本的字符数，同时估算大模型输出量')

    @model_validator(mode='after')
    def validate_usage(self) -> 'UpdateDeviceUsageParam':
        if self.asr_characters == 0 and self.tts_characters == 0:
            raise ValueError('语音识别和语音合成字符数不能同时为零')
        return self


class DeviceUsageQuotaResult(SchemaBase):
    """设备当天共享额度和累计使用量。"""

    did: str = Field(description='设备 DID')
    usage_date: date = Field(description='业务日期')
    daily_quota: int | None = Field(ge=0, description='每日共享额度，NULL 表示不限制')
    quantity: int = Field(ge=0, description='当天累计使用量，统一用量单位')
    remaining_quantity: int | None = Field(ge=0, description='当天剩余使用量，NULL 表示不限制')
