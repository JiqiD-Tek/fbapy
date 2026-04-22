from __future__ import annotations

import json
import uuid

from backend.common.log import log
from backend.app.cloud.timeseries.js61_event import JS61EventTable
from backend.app.cloud.timeseries.k11_event import K11EventTable

from backend.database.tsdb import TSDBTable, tsdb_client


class EventRouter:
    """MQTT message handler for TSDB ingestion."""

    MODEL_TSDB_TABLES: dict[str, TSDBTable] = {
        'js61': JS61EventTable.__table__,
        'k11': K11EventTable.__table__,
    }
    PAYLOAD_MAX_LENGTH = 4096

    @classmethod
    def _parse_topic(cls, topic: str) -> tuple[str, str, str, str] | None:
        parts = [segment.strip() for segment in topic.split('/') if segment.strip()]
        if len(parts) < 4:
            return None

        model = parts[0].lower()
        device_id = parts[1]
        direction = parts[2]
        category = parts[3]
        return model, device_id, direction, category

    @classmethod
    def _serialize_payload(cls, topic: str, payload: dict) -> str:
        text = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))

        if len(text) > cls.PAYLOAD_MAX_LENGTH:
            log.debug(f'payload is too long, topic={topic}, payload={text}')
            return text[: cls.PAYLOAD_MAX_LENGTH - 3] + '...'

        return text

    @classmethod
    async def insert(cls, message_ctx) -> None:
        """Persist one MQTT message into the TSDB table resolved from topic."""

        if not tsdb_client.enabled:
            log.debug('skip TSDB ingestion because TSDB client is not enabled')
            return

        if not tsdb_client.ready:
            log.debug('skip TSDB ingestion because TSDB client is not ready')
            return

        parsed = cls._parse_topic(message_ctx.topic)
        if parsed is None:
            return

        model, device_id, direction, category = parsed
        table = cls.MODEL_TSDB_TABLES.get(model)
        if table is None:
            return

        try:
            await table.insert(
                tsdb_client,
                subtable_name=f"{model}_{device_id}",
                tags={
                    'did': device_id,
                    'model': model,
                },
                values={
                    'ts': int(message_ctx.timestamp * 1000),
                    'event_id': uuid.uuid4().hex,
                    'direction': direction,
                    'category': category,
                    'service': 'mqtt',  # todo: 解析payload获取服务名
                    'topic': message_ctx.topic,
                    'payload': cls._serialize_payload(message_ctx.topic, message_ctx.payload),
                },
            )
        except Exception as exc:
            log.error(
                f'failed to ingest MQTT message into TSDB, table={table.name}, topic={message_ctx.topic}, error={exc}'
            )
