from __future__ import annotations

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class GetDeviceStateDetail(SchemaBase):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    did: str = Field(description='device id')
    model: str = Field(description='device model')
    timestamp: float = Field(description='state updated timestamp')
    online: bool | None = Field(None, description='device online status')
    power: str | None = Field(None, description='power state')
    volume: int | float | None = Field(None, description='volume')
    mute: bool | None = Field(None, description='mute status')
    player_state: str | None = Field(None, description='player state')
