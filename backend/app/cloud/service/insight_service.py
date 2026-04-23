# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : insight_service.py
@Author  : OpenAI
@Date    : 2026/04/23
"""

from __future__ import annotations

import asyncio

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.service.baby_service import baby_service
from backend.app.cloud.service.device_service import device_service
from backend.app.cloud.schema.device.device_insight import (
    DeviceTSDBEventDetail,
    DeviceTSDBInsightDetail,
    DeviceVikingInsightDetail,
    DeviceVikingMemorySectionDetail,
    GetDeviceInsightDetail,
)
from backend.app.cloud.timeseries.event_store import event_store
from backend.common.exception import errors
from backend.common.providers.viking_memory import viking_memory_client
from backend.database.tsdb import tsdb_client


class DeviceInsightService:
    """Aggregate device-related TSDB and Viking data."""

    @staticmethod
    async def _query_tsdb(
            *,
            model: str,
            baby_id: int,
            start_time: datetime | str | None,
            end_time: datetime | str | None,
            direction: str | None,
            category: str | None,
            service: str | None,
            limit: int,
    ) -> DeviceTSDBInsightDetail:
        try:
            rows = await event_store.query(
                model=model,
                baby_id=baby_id,
                start_time=start_time,
                end_time=end_time,
                direction=direction,
                category=category,
                service=service,
                limit=limit,
            )
            items = [DeviceTSDBEventDetail.model_validate(row) for row in rows]
            return DeviceTSDBInsightDetail(
                enabled=tsdb_client.enabled,
                ready=tsdb_client.ready,
                error=None,
                items=items,
            )
        except Exception as exc:
            return DeviceTSDBInsightDetail(
                enabled=tsdb_client.enabled,
                ready=tsdb_client.ready,
                error=str(exc),
                items=[],
            )

    @staticmethod
    async def _query_viking_events(
            *,
            baby_id: int,
            query: str | None,
            limit: int,
            assistant_id: str | None,
    ) -> DeviceVikingMemorySectionDetail:
        try:
            raw = await viking_memory_client.query_event_memories(
                user_id=str(baby_id),
                query=query,
                limit=limit,
                assistant_id=assistant_id,
            )
            return DeviceVikingMemorySectionDetail(
                enabled=viking_memory_client.enabled,
                error=None,
                raw=raw,
                text=viking_memory_client.format_event_memories(raw),
            )
        except Exception as exc:
            return DeviceVikingMemorySectionDetail(
                enabled=viking_memory_client.enabled,
                error=str(exc),
                raw={},
                text='',
            )

    @staticmethod
    async def _query_viking_profiles(
            *,
            baby_id: int,
            query: str | None,
            limit: int,
            assistant_id: str | None,
    ) -> DeviceVikingMemorySectionDetail:
        try:
            raw = await viking_memory_client.query_profile_memories(
                user_id=str(baby_id),
                query=query,
                limit=limit,
                assistant_id=assistant_id,
            )
            return DeviceVikingMemorySectionDetail(
                enabled=viking_memory_client.enabled,
                error=None,
                raw=raw,
                text=viking_memory_client.format_profile_memories(raw),
            )
        except Exception as exc:
            return DeviceVikingMemorySectionDetail(
                enabled=viking_memory_client.enabled,
                error=str(exc),
                raw={},
                text='',
            )

    async def get_device_insight(
            self,
            *,
            db: AsyncSession,
            user_id: int,
            baby_id: int,
            start_time: datetime | str | None = None,
            end_time: datetime | str | None = None,
            direction: str | None = None,
            category: str | None = None,
            service: str | None = None,
            tsdb_limit: int = 100,
            memory_query: str | None = None,
            memory_event_limit: int = 10,
            memory_profile_limit: int = 10,
            assistant_id: str | None = None,
    ) -> GetDeviceInsightDetail:
        baby = await baby_service.get(db=db, user_id=user_id, pk=baby_id)
        if baby.device_id is None:
            raise errors.RequestError(msg='宝宝未绑定设备')

        device = await device_service.get(db=db, user_id=user_id, pk=baby.device_id)
        tsdb_result, viking_event_result, viking_profile_result = await asyncio.gather(
            self._query_tsdb(
                model=device.model,
                baby_id=baby_id,
                start_time=start_time,
                end_time=end_time,
                direction=direction,
                category=category,
                service=service,
                limit=tsdb_limit,
            ),
            self._query_viking_events(
                baby_id=baby_id,
                query=memory_query,
                limit=memory_event_limit,
                assistant_id=assistant_id,
            ),
            self._query_viking_profiles(
                baby_id=baby_id,
                query=memory_query,
                limit=memory_profile_limit,
                assistant_id=assistant_id,
            ),
        )

        return GetDeviceInsightDetail(
            tsdb=tsdb_result,
            viking=DeviceVikingInsightDetail(
                enabled=viking_memory_client.enabled,
                events=viking_event_result,
                profiles=viking_profile_result,
            ),
        )


device_insight_service = DeviceInsightService()
