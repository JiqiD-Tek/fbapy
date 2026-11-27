from __future__ import annotations

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class GetDeviceStateDetail(SchemaBase):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    did: str = Field(description='设备 ID')
    model: str = Field(description='设备型号')
    timestamp: int = Field(description='状态更新时间')
    online: int | None = Field(None, description='设备在线状态')
    battery: int | None = Field(None, description='设备电量')
    volume: int | None = Field(None, description='音量')
    light: int | None = Field(None, description='灯光')
    storage: dict | None = Field(None, description='设备存储总量')
    sleep: dict | None = Field(None, description='睡眠模式')
    repeat_mode: int | None = Field(None, description='重复播放模式')
