from __future__ import annotations

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class GetDeviceStateDetail(SchemaBase):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    did: str = Field(description='device id')
    model: str = Field(description='device model')
    timestamp: int = Field(description='state updated timestamp')
    online: int | None = Field(None, description='device online status')
    battery: int | None = Field(None, description='device battery level')
    volume: int | None = Field(None, description='volume')
    storage: dict | None = Field(None, description='device storage total')
    sleep: dict | None = Field(None, description='sleep mode')
    repeat_mode: int | None = Field(None, description='repeat mode')
