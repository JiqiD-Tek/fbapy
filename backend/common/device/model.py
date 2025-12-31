# -*- coding: UTF-8 -*-
"""
@Project : jiqid-py
@File    : model.py
@Author  : guhua@jiqid.com
@Date    : 2025/07/18 14:03
"""

import uuid
from enum import Enum, auto
from datetime import datetime, time
from dataclasses import dataclass, field
from typing import Optional, Union, List, Dict, TypeVar, Tuple
from functools import lru_cache

# Type variable for generic enum handling
E = TypeVar('E', bound=Enum)


# ---------- Enum Definitions ----------

class StrEnum(str, Enum):
    """Base class for string-based enums to ensure consistent string representation."""

    def __str__(self) -> str:
        return self.value


class DeviceType(StrEnum):
    """Device component types."""
    LIGHT = "light"
    SCREEN = "screen"
    BLUETOOTH = "bluetooth"
    VOLUME = "volume"
    PLAYBACK = "playback"
    MODE = "mode"
    MICROPHONE = "microphone"


class ActionType(StrEnum):
    """Device action types."""
    ON = "on"
    OFF = "off"
    ADJUST = "adjust"
    PAUSE = "pause"
    CONTINUE = "continue"
    NEXT = "next"
    PREV = "prev"
    JUMP = "jump"
    SET = "set"
    MUTE = "mute"
    UNMUTE = "unmute"
    RECORD = "record"
    STOP_RECORD = "stop_record"


class ModeType(StrEnum):
    """Operating mode types."""
    SLEEP = "sleep"
    CHILD = "child"
    SINGLE_LOOP = "single_loop"
    LIST_LOOP = "list_loop"
    SHUFFLE = "shuffle"
    VOICE_COMMAND = "voice_command"
    KARAOKE = "karaoke"
    MEETING = "meeting"


class ConnectionType(Enum):
    """Network connection types."""
    WIFI = auto()
    ETHERNET = auto()
    CELLULAR = auto()


class PlaybackState(Enum):
    """Media playback states."""
    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()
    BUFFERING = auto()


class RepeatMode(Enum):
    """Playback repeat modes."""
    NONE = auto()
    ONE = auto()
    ALL = auto()


class AlarmType(Enum):
    """Alarm schedule types."""
    PERIODIC = auto()
    NON_PERIODIC = auto()

    @property
    def is_repeating(self) -> bool:
        return self == AlarmType.PERIODIC


# ---------- Dataclass Definitions ----------

@dataclass(frozen=True, slots=True)
class AudioTrack:
    """Immutable audio track information."""
    song_id: int
    album_id: int
    singer_id: int
    song_name: str
    album_name: str
    duration: int
    cover_url: str
    store_url: str

    def __post_init__(self) -> None:
        """Validate non-negative IDs and non-empty strings."""
        if any(v < 0 for v in (self.song_id, self.album_id, self.singer_id)):
            raise ValueError("IDs must be non-negative")
        if self.duration < 0:
            raise ValueError("Duration must be non-negative")
        if not all((self.song_name, self.album_name, self.cover_url, self.store_url)):
            raise ValueError("String fields must be non-empty")


@dataclass(frozen=True, slots=True)
class Alarm:
    """Immutable alarm structure."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    alarm_type: AlarmType = AlarmType.NON_PERIODIC
    trigger: Union[datetime, time] = field(default_factory=lambda: datetime.now())
    repeat: List[int] = field(default_factory=list)
    label: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate alarm configuration."""
        if not self.id:
            raise ValueError("Alarm ID must be non-empty")
        if self.alarm_type == AlarmType.PERIODIC and not isinstance(self.trigger, time):
            raise ValueError("Periodic alarms require time trigger")
        if self.alarm_type == AlarmType.NON_PERIODIC and not isinstance(self.trigger, datetime):
            raise ValueError("Non-periodic alarms require datetime trigger")
        if any(day < 0 or day > 6 for day in self.repeat):
            raise ValueError("Repeat days must be 0-6 (Monday-Sunday)")


@dataclass(slots=True)
class DeviceState:
    """Immutable snapshot of smart speaker state."""
    # Device identification
    device_id: str
    ip: str = "192.168.1.1"
    firmware_version: str = "1.0.0"

    # Voice interaction
    conversation_id: str = ""

    # Audio control
    volume: int = 50
    is_muted: bool = False
    playback_state: PlaybackState = PlaybackState.STOPPED
    current_track: Optional[AudioTrack] = None
    playlist: List[int] = field(default_factory=list)
    repeat_mode: RepeatMode = RepeatMode.NONE
    shuffle_on: bool = False

    # Network status
    connection_type: ConnectionType = ConnectionType.WIFI
    wifi_signal: int = 0

    # Device sensors
    battery: int = 100
    is_charging: bool = False

    # Alarm functionality
    alarms: List[Alarm] = field(default_factory=lambda: [])

    # Range constraints for validation
    _ranges: Dict[str, Tuple[int, int]] = field(
        default_factory=lambda: {
            "volume": (0, 100),
            "wifi_signal": (0, 4),
            "battery": (0, 100),
        }
    )

    def __post_init__(self) -> None:
        """Validate device_clients state fields."""
        if not self.device_id:
            raise ValueError("device_id must be non-empty")
        if not self.ip:
            raise ValueError("ip must be non-empty")
        if not self.firmware_version:
            raise ValueError("firmware_version must be non-empty")
        for field_name, (min_val, max_val) in self._ranges.items():
            value = getattr(self, field_name)
            if not min_val <= value <= max_val:
                raise ValueError(f"{field_name} must be between {min_val} and {max_val}, got {value}")

    @lru_cache(maxsize=32)
    def _get_field_range(self, field_name: str) -> Tuple[int, int]:
        """Cached retrieval of field range constraints."""
        return self._ranges[field_name]
