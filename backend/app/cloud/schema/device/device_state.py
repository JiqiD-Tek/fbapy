from __future__ import annotations

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class GetDeviceStateDetail(SchemaBase):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    did: str = Field(description='device id')
    model: str = Field(description='device model')
    timestamp: float = Field(description='state updated timestamp')
    online: bool | None = Field(None, description='device online status')
    battery: int | float | None = Field(None, description='device battery level')
    volume: int | float | None = Field(None, description='volume')
    storage: int | float | str | None = Field(None, description='device storage space')
    sleep_duration: int | float | None = Field(None, description='sleep duration')
    sleep_song_count: int | None = Field(None, description='sleep song count')
    play_mode: str | None = Field(None, description='play mode')
