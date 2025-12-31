# -*- coding: UTF-8 -*-
"""
@Project : jiqid-py
@File    : repository.py
@Author  : guhua@jiqid.com
@Date    : 2025/07/18 14:03
"""

import json

from enum import Enum
from datetime import datetime, time
from dataclasses import fields, asdict, is_dataclass
from typing import Optional, Union, List, Any, Dict, Type, get_origin, get_args, TypeVar, Literal, TypedDict

from backend.common.device.model import (
    ConnectionType, RepeatMode, PlaybackState,
    AlarmType, Alarm,
    AudioTrack,
    DeviceState,
)
from backend.common.log import log
from backend.database.redis import redis_client
from backend.utils.timezone import timezone

T = TypeVar('T')
E = TypeVar('E', bound=Enum)

# 定义存储策略类型
StorageStrategy = Literal["memory", "redis_individual", "redis_json"]


# 定义字段策略配置类型
class FieldStrategyConfig(TypedDict):
    strategy: StorageStrategy
    default: Any
    field_type: Type[Any]


# Field configuration as a single source of truth
FIELD_CONFIG = {
    # Memory fields
    "conversation_id": {"strategy": "memory", "default": None, "field_type": Optional[str]},
    "volume": {"strategy": "memory", "default": 50, "field_type": int},
    "is_muted": {"strategy": "memory", "default": False, "field_type": bool},
    "playback_state": {"strategy": "memory", "default": PlaybackState.STOPPED, "field_type": PlaybackState},
    "current_track": {"strategy": "memory", "default": None, "field_type": Optional[AudioTrack]},
    "shuffle_on": {"strategy": "memory", "default": False, "field_type": bool},
    "battery": {"strategy": "memory", "default": 100, "field_type": int},
    "is_charging": {"strategy": "memory", "default": False, "field_type": bool},
    "wifi_signal": {"strategy": "memory", "default": 0, "field_type": int},
    # Redis individual fields
    "ip": {"strategy": "redis_individual", "default": "", "field_type": str},
    "firmware_version": {"strategy": "redis_individual", "default": "1.0.0", "field_type": str},
    "connection_type": {"strategy": "redis_individual", "default": ConnectionType.WIFI, "field_type": ConnectionType},
    # Redis JSON fields
    "playlist": {"strategy": "redis_json", "default": [], "field_type": List[int]},
    "repeat_mode": {"strategy": "redis_json", "default": RepeatMode.NONE, "field_type": RepeatMode},
    "alarms": {"strategy": "redis_json", "default": [], "field_type": List[Alarm]},
}


class DeviceStateRepository:
    """Smart speaker state repository with layered storage (memory + Redis)."""

    class DeviceStateEncoder(json.JSONEncoder):
        """Custom JSON encoder for dataclass, Enum, datetime, and lists."""

        def default(self, obj):
            if isinstance(obj, Enum):
                return obj.name
            elif isinstance(obj, (datetime, time)):
                return obj.isoformat()
            elif is_dataclass(obj):
                return asdict(obj)
            elif isinstance(obj, list):
                return [self.default(item) for item in obj]
            return super().default(obj)

    def __init__(self, device_id: str):
        if not device_id or not isinstance(device_id, str):
            raise ValueError("device_id must be a non-empty string")

        self.device_id = device_id
        self.prefix = f"device:{device_id}:"
        self._redis_client = redis_client

        # 初始化内存缓存（仅包含内存存储字段）
        self._memory_cache: Dict[str, Any] = {
            field: config["default"]
            for field, config in FIELD_CONFIG.items()
            if config["strategy"] == "memory"
        }
        self._json_cache: Dict[str, Any] = {}  # Cache for Redis JSON data

    async def set_fields(self, **kwargs) -> None:
        """Update fields selectively based on storage strategy."""
        memory_updates = {}
        redis_individual_updates = {}
        redis_json_updates = {}

        # Classify updates by strategy
        for field, value in kwargs.items():
            config = FIELD_CONFIG.get(field)
            if not config:
                log.warning(f"Attempted to update unconfigured field: {field}")
                continue

            strategy = config["strategy"]
            if strategy == "memory":
                memory_updates[field] = value
            elif strategy == "redis_individual":
                redis_individual_updates[field] = value
            elif strategy == "redis_json":
                redis_json_updates[field] = value

        # Update memory cache
        self._memory_cache.update(memory_updates)

        # Early return if no Redis updates
        if not (redis_individual_updates or redis_json_updates):
            return

        # Execute Redis updates in a single pipeline
        async with self._redis_client.pipeline() as pipe:
            # Update individual fields
            for field, value in redis_individual_updates.items():
                await pipe.set(f"{self.prefix}{field}", str(value))

            # Update JSON fields
            if redis_json_updates:
                # Load cached JSON or fetch from Redis
                if not self._json_cache:
                    json_data = await self._redis_client.get(f"{self.prefix}_state_json")
                    self._json_cache = json.loads(json_data) if json_data else {}
                self._json_cache.update(redis_json_updates)
                await pipe.set(
                    f"{self.prefix}_state_json",
                    json.dumps(self._json_cache, cls=self.DeviceStateEncoder)
                )

            await pipe.execute()

    async def get_fields(self, *field_names: str) -> Dict[str, Any]:
        """Fetch multiple field values."""
        result = {}
        redis_individual_fields = []
        redis_json_fields = []

        # Classify requested fields
        for field in field_names:
            config = FIELD_CONFIG.get(field)
            if not config:
                raise ValueError(f"Unconfigured field: {field}")

            strategy = config["strategy"]
            if strategy == "memory":
                result[field] = self._memory_cache.get(field, config["default"])
            elif strategy == "redis_individual":
                redis_individual_fields.append(field)
            elif strategy == "redis_json":
                redis_json_fields.append(field)

        if not (redis_individual_fields or redis_json_fields):
            return result

        # Fetch Redis data in a single pipeline
        async with self._redis_client.pipeline() as pipe:
            # Use MGET for individual fields
            if redis_individual_fields:
                keys = [f"{self.prefix}{field}" for field in redis_individual_fields]
                await pipe.mget(keys)
            # Fetch JSON data if needed
            if redis_json_fields and not self._json_cache:
                await pipe.get(f"{self.prefix}_state_json")
            redis_results = await pipe.execute()

        # Process individual fields
        if redis_individual_fields:
            redis_values = redis_results[0][:len(redis_individual_fields)]
            for i, field in enumerate(redis_individual_fields):
                result[field] = self._parse_field(FIELD_CONFIG[field]["field_type"], redis_values[i])

        # Process JSON fields
        if redis_json_fields:
            if not self._json_cache:
                json_data = redis_results[-1] if redis_individual_fields else redis_results[0]
                self._json_cache = json.loads(json_data) if json_data else {}
            for field in redis_json_fields:
                config = FIELD_CONFIG[field]
                result[field] = self._parse_field(
                    config["field_type"],
                    self._json_cache.get(field, config["default"])
                )

        return result

    async def get_field(self, field_name: str) -> Any:
        """Fetch a single field value."""
        return (await self.get_fields(field_name)).get(field_name)

    async def add_alarm(self, alarm: Alarm) -> None:
        """Add an alarm."""
        alarms = await self.get_valid_alarms()
        alarms.append(alarm)
        await self.set_fields(alarms=alarms)

    async def update_alarm(self, alarm: Alarm) -> None:
        """Update an existing alarm."""
        alarms = await self.get_valid_alarms()
        if not any(a.id == alarm.id for a in alarms):
            raise ValueError(f"Alarm ID {alarm.id} not found")

        updated_alarms = [alarm if a.id == alarm.id else a for a in alarms]
        await self.set_fields(alarms=updated_alarms)

    async def del_alarm(self, alarm_ids: List[str]) -> List[Alarm]:
        """Delete alarms by IDs."""
        if not alarm_ids:
            return []

        alarms = await self.get_valid_alarms()
        alarm_ids_set = set(alarm_ids)
        to_keep, to_remove = [], []
        for alarm in alarms:
            (to_remove if alarm.id in alarm_ids_set else to_keep).append(alarm)

        await self.set_fields(alarms=to_keep)
        return to_remove

    async def get_valid_alarms(self) -> List[Alarm]:
        """Get valid alarms (periodic or future-triggered)."""
        alarms = await self.get_field("alarms") or []
        now = timezone.now()
        return [alarm for alarm in alarms if alarm.alarm_type == AlarmType.PERIODIC or alarm.trigger > now]

    async def loads(self, state: DeviceState) -> None:
        """保存完整状态（分层存储）"""
        state_dict = asdict(state)
        await self.loads_dict(state_dict)

    async def loads_dict(self, state_dict: Dict[str, Any]) -> None:
        """ 解析dict数据 """
        memory_updates = {}
        redis_individual_updates = {}
        redis_json_updates = {}

        for field in fields(DeviceState):
            if field.name not in state_dict:
                continue
            config = FIELD_CONFIG.get(field.name)
            if not config:
                continue
            value = state_dict[field.name]
            if config["strategy"] == "memory":
                memory_updates[field.name] = value
            elif config["strategy"] == "redis_individual":
                redis_individual_updates[field.name] = value
            elif config["strategy"] == "redis_json":
                redis_json_updates[field.name] = value

        self._memory_cache.update(memory_updates)
        if redis_individual_updates or redis_json_updates:
            async with self._redis_client.pipeline() as pipe:
                for field, value in redis_individual_updates.items():
                    await pipe.set(f"{self.prefix}{field}", str(value))
                if redis_json_updates:
                    self._json_cache.update(redis_json_updates)
                    await pipe.set(
                        f"{self.prefix}_state_json",
                        json.dumps(self._json_cache, cls=self.DeviceStateEncoder)
                    )
                await pipe.execute()

    async def dumps(self) -> DeviceState:
        """Dump full state as DeviceState object."""
        state_data = {"device_id": self.device_id}
        redis_individual_fields = [
            field for field, config in FIELD_CONFIG.items()
            if config["strategy"] == "redis_individual"
        ]

        # Fetch Redis data
        async with self._redis_client.pipeline() as pipe:
            if redis_individual_fields:
                keys = [f"{self.prefix}{field}" for field in redis_individual_fields]
                await pipe.mget(keys)
            if not self._json_cache:
                await pipe.get(f"{self.prefix}_state_json")
            redis_results = await pipe.execute()

        # Process individual fields
        if redis_individual_fields:
            redis_values = redis_results[0][:len(redis_individual_fields)]
            for i, field in enumerate(redis_individual_fields):
                if redis_values[i]:
                    state_data[field] = self._parse_field(FIELD_CONFIG[field]["field_type"], redis_values[i])

        # Process JSON fields
        if not self._json_cache:
            json_data = redis_results[-1] if redis_individual_fields else redis_results[0]
            self._json_cache = json.loads(json_data) if json_data else {}
        for field, config in FIELD_CONFIG.items():
            if config["strategy"] == "redis_json" and field in self._json_cache:
                state_data[field] = self._parse_field(config["field_type"], self._json_cache[field])

        # Process memory fields
        for field, config in FIELD_CONFIG.items():
            if config["strategy"] == "memory":
                state_data[field] = self._parse_field(
                    config["field_type"],
                    self._memory_cache.get(field, config["default"])
                )

        return DeviceState(**state_data)

    async def dumps_dict(self) -> Dict[str, Any]:
        state = await self.dumps()
        return asdict(state)

    def _parse_field(self, target_type: Type[T], raw_value: Any) -> Optional[T]:
        """类型安全的字段解析"""
        if raw_value is None:
            return None

        try:
            # 处理枚举类型
            if isinstance(target_type, type) and issubclass(target_type, Enum):
                return self._parse_enum(target_type, raw_value)

            # 处理时间类型
            if target_type in (datetime, time):
                return self._parse_time(raw_value)

            # 处理特定模型类型
            model_types = {AudioTrack, Alarm}
            if target_type in model_types:
                return self._parse_model(target_type, raw_value)

            if get_origin(target_type) is Union:
                inner_types = [t for t in get_args(target_type) if t is not type(None)]
                if len(inner_types) == 1 and inner_types[0] in model_types:
                    if raw_value is not None:
                        return self._parse_model(inner_types[0], raw_value)  # type: ignore
                    return None

            # 处理可选类型 (Optional[T] 或 Union[T, None])
            if origin_type := get_origin(target_type):
                if origin_type is Union:
                    inner_types = [t for t in get_args(target_type) if t is not type(None)]
                    # 处理Optional[T]情况（即Union[T, None]）
                    if len(inner_types) == 1:
                        return self._parse_field(inner_types[0], raw_value)

                    # 处理真正的多类型Union（如Union[str, int]）
                    for t in inner_types:
                        try:
                            result = self._parse_field(t, raw_value)
                            if result is not None:  # 解析成功
                                return result
                        except (TypeError, ValueError):
                            continue  # 当前类型解析失败，尝试下一个类型

                # 处理 List[T] 类型
                if origin_type is list:
                    item_type = get_args(target_type)[0] if get_args(target_type) else Any
                    if isinstance(raw_value, (list, tuple)):
                        return [self._parse_field(item_type, value) for value in raw_value]
                    return [self._parse_field(item_type, raw_value)]

            # 基础类型转换
            return target_type(raw_value)

        except (TypeError, ValueError, AttributeError) as e:
            log.warning(f"Failed to parse field: type={target_type}, value={raw_value!r}, error={str(e)}")
            return None

    def _parse_enum(self, enum_type: Type[E], value: Any) -> Optional[E]:
        """Parse Enum values."""
        if value is None or isinstance(value, enum_type):
            return value

        try:
            if isinstance(value, str):
                value = value.strip().split(".")[-1].upper()
                return enum_type[value]
            return enum_type(value)
        except (KeyError, ValueError) as e:
            log.warning(f"Failed to parse enum {enum_type.__name__}: value={value!r}, error={str(e)}")
            return None

    def _parse_time(self, value: Any) -> Union[datetime, time, None]:
        """Parse time values."""
        if value is None or isinstance(value, (datetime, time)):
            return value

        if not isinstance(value, str):
            return None
        value = value.strip()
        if not value:
            return None
        try:
            if "T" in value:
                return datetime.fromisoformat(value)
            if ":" in value:
                parts = value.split(":")
                if len(parts) == 2:
                    return time(int(parts[0]), int(parts[1]))
                if len(parts) == 3:
                    return time(int(parts[0]), int(parts[1]), int(parts[2]))
            return datetime.fromtimestamp(float(value))
        except ValueError as e:
            log.warning(f"Failed to parse time: value={value!r}, error={str(e)}")
            return None

    def _parse_model(self, model_class: Type[T], value: Any) -> Optional[T]:
        """Parse model values."""
        if value is None or isinstance(value, model_class):
            return value

        if not isinstance(value, dict):
            return None

        try:
            model_data = {}
            for field in fields(model_class):
                model_data[field.name] = self._parse_field(field.type, value[field.name])
            return model_class(**model_data)
        except (KeyError, TypeError, ValueError) as e:
            log.warning(f"Failed to parse model: class={model_class} value={value!r}, error={str(e)}")
            return None
