# -*- coding: UTF-8 -*-
"""
Simple Huoshan bidirectional TTS stream service.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from typing import Any, ClassVar

import websockets

from backend.app.cloud.schema.resource.huoshan import (
    HuoshanStreamTTSParam,
    HuoshanStreamTTSResult,
)
from backend.app.cloud.service.resource.huoshan.config import (
    get_voice_project_for_speaker,
)
from backend.app.cloud.service.resource.huoshan.tts.tts_cache import tts_cache
from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings

PROTOCOL_VERSION = 0b0001
DEFAULT_HEADER_SIZE = 0b0001
FIXED_HEADER_BYTES = 4
EMPTY_JSON_BYTES = b'{}'
MAX_WS_MESSAGE_SIZE = 1_000_000_000

FULL_CLIENT_REQUEST = 0b0001
AUDIO_ONLY_RESPONSE = 0b1011
FULL_SERVER_RESPONSE = 0b1001
ERROR_INFORMATION = 0b1111

MSG_TYPE_FLAG_WITH_EVENT = 0b100
JSON_SERIALIZATION = 0b0001
COMPRESSION_NO = 0b0000

EVENT_NONE = 0
EVENT_FINISH_CONNECTION = 2

EVENT_CONNECTION_STARTED = 50
EVENT_CONNECTION_FAILED = 51
EVENT_CONNECTION_FINISHED = 52

EVENT_START_SESSION = 100
EVENT_FINISH_SESSION = 102

EVENT_SESSION_STARTED = 150
EVENT_SESSION_FINISHED = 152
EVENT_SESSION_FAILED = 153

EVENT_TASK_REQUEST = 200
EVENT_TTS_RESPONSE = 352


@dataclass(slots=True)
class ProtocolHeader:
    protocol_version: int = PROTOCOL_VERSION
    header_size: int = DEFAULT_HEADER_SIZE
    message_type: int = 0
    message_type_specific_flags: int = 0
    serial_method: int = JSON_SERIALIZATION
    compression_type: int = COMPRESSION_NO
    reserved_data: int = 0

    def as_bytes(self) -> bytes:
        return bytes(
            [
                (self.protocol_version << 4) | self.header_size,
                (self.message_type << 4) | self.message_type_specific_flags,
                (self.serial_method << 4) | self.compression_type,
                self.reserved_data,
            ]
        )


@dataclass(slots=True)
class ProtocolOptionalFields:
    event: int = EVENT_NONE
    session_id: str | None = None
    error_code: int = 0
    connection_id: str | None = None
    response_meta_json: str | None = None

    def as_bytes(self) -> bytes:
        option_bytes = bytearray()
        if self.event != EVENT_NONE:
            option_bytes.extend(self.event.to_bytes(4, 'big', signed=True))
        if self.session_id is not None:
            session_id_bytes = self.session_id.encode('utf-8')
            option_bytes.extend(len(session_id_bytes).to_bytes(4, 'big', signed=True))
            option_bytes.extend(session_id_bytes)
        return bytes(option_bytes)


@dataclass(slots=True)
class ProtocolResponse:
    header: ProtocolHeader
    optional: ProtocolOptionalFields
    payload: bytes | None = None


FULL_CLIENT_REQUEST_HEADER = ProtocolHeader(
    message_type=FULL_CLIENT_REQUEST,
    message_type_specific_flags=MSG_TYPE_FLAG_WITH_EVENT,
    serial_method=JSON_SERIALIZATION,
).as_bytes()


class TTSStreamService:
    DEFAULT_SAMPLE_RATE: ClassVar[int] = 24000

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return str(value or '').strip()

    @classmethod
    def _resolve_stream_config(cls) -> dict[str, Any]:
        return {
            'ws_url': (
                cls._normalize_text(settings.BYTES_TTS_STREAM_WS_URL)
                or 'wss://openspeech.bytedance.com/api/v3/tts/bidirection'
            ),
            'resource_id': (
                cls._normalize_text(settings.BYTES_TTS_STREAM_RESOURCE_ID)
                or 'seed-tts-2.0'
            ),
            'audio_format': (
                cls._normalize_text(settings.BYTES_TTS_STREAM_AUDIO_FORMAT)
                or 'mp3'
            ),
            'speech_rate': int(settings.BYTES_TTS_STREAM_SPEECH_RATE or 0),
            'loudness_rate': int(settings.BYTES_TTS_STREAM_LOUDNESS_RATE or 0),
        }

    @classmethod
    def _build_ws_headers(
            cls,
            *,
            appid: str,
            access_token: str,
            resource_id: str,
    ) -> dict[str, str]:
        return {
            'X-Api-App-Key': appid,
            'X-Api-Access-Key': access_token,
            'X-Api-Resource-Id': resource_id,
            'X-Api-Connect-Id': uuid.uuid4().hex,
        }

    async def submit(self, obj: HuoshanStreamTTSParam) -> HuoshanStreamTTSResult:
        request_id = await tts_cache.create_new_request()
        task = asyncio.create_task(
            self._run_stream_task(request_id=request_id, obj=obj),
            name=f'tts-stream:{request_id}',
        )
        self._tasks[request_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(request_id, None))
        return HuoshanStreamTTSResult(request_id=request_id)

    async def _run_stream_task(
            self,
            *,
            request_id: str,
            obj: HuoshanStreamTTSParam,
    ) -> None:
        ws: Any | None = None
        try:
            speaker = self._normalize_text(obj.speaker)
            text = self._normalize_text(obj.text)
            if not speaker:
                raise errors.RequestError(msg='speaker is required')
            if not text:
                raise errors.RequestError(msg='text is required')

            stream_config = self._resolve_stream_config()
            ws_url = stream_config['ws_url']
            resource_id = stream_config['resource_id']
            audio_format = stream_config['audio_format']
            speech_rate = stream_config['speech_rate']
            loudness_rate = stream_config['loudness_rate']
            project = get_voice_project_for_speaker(speaker)
            if not project.app_id or not project.access_token:
                raise errors.ServerError(
                    msg=f'Huoshan TTS credentials are not configured for project={project.name}'
                )

            ws = await websockets.connect(
                ws_url,
                additional_headers=self._build_ws_headers(
                    appid=project.app_id,
                    access_token=project.access_token,
                    resource_id=resource_id,
                ),
                max_size=MAX_WS_MESSAGE_SIZE,
            )

            await self._send_protocol_event(
                ws,
                event=EVENT_START_SESSION,
                session_id=request_id,
                payload=self._build_request_payload(
                    event=EVENT_START_SESSION,
                    speaker=speaker,
                    audio_format=audio_format,
                    speech_rate=speech_rate,
                    loudness_rate=loudness_rate,
                ),
            )

            task_requested = False
            while True:
                response = self._parse_response(await ws.recv())
                event = response.optional.event

                if response.header.message_type == ERROR_INFORMATION:
                    raise errors.GatewayError(
                        msg=f'Huoshan stream TTS error: {self._decode_payload_text(response.payload)}'
                    )

                if event == EVENT_CONNECTION_FAILED:
                    raise errors.GatewayError(
                        msg=response.optional.response_meta_json or 'Huoshan stream TTS connection failed'
                    )

                if event == EVENT_SESSION_FAILED:
                    raise errors.GatewayError(
                        msg=response.optional.response_meta_json or 'Huoshan stream TTS session failed'
                    )

                if event == EVENT_SESSION_STARTED and not task_requested:
                    await self._send_protocol_event(
                        ws,
                        event=EVENT_TASK_REQUEST,
                        session_id=request_id,
                        payload=self._build_request_payload(
                            event=EVENT_TASK_REQUEST,
                            text=text,
                            speaker=speaker,
                            audio_format=audio_format,
                            speech_rate=speech_rate,
                            loudness_rate=loudness_rate,
                        ),
                    )
                    await self._send_protocol_event(
                        ws,
                        event=EVENT_FINISH_SESSION,
                        session_id=request_id,
                    )
                    task_requested = True
                    continue

                if event == EVENT_TTS_RESPONSE and response.payload:
                    await tts_cache.append_audio_delta(
                        response.payload,
                        request_id=request_id,
                    )
                    continue

                if event in (EVENT_SESSION_FINISHED, EVENT_CONNECTION_FINISHED):
                    break

            await self._send_protocol_event(ws, event=EVENT_FINISH_CONNECTION)
        except Exception as exc:
            log.error(f'Huoshan stream TTS task failed: request_id={request_id}, error={exc}')
        finally:
            await tts_cache.finish_request(request_id=request_id)
            if ws is not None:
                try:
                    await ws.close()
                except Exception:
                    pass

    @staticmethod
    async def _send_protocol_message(
            ws: Any,
            *,
            header: bytes,
            optional: bytes | None = None,
            payload: bytes | None = None,
    ) -> None:
        full_client_request = bytearray(header)
        if optional is not None:
            full_client_request.extend(optional)
        if payload is not None:
            full_client_request.extend(len(payload).to_bytes(4, 'big', signed=True))
            full_client_request.extend(payload)
        await ws.send(full_client_request)

    @classmethod
    async def _send_protocol_event(
            cls,
            ws: Any,
            *,
            event: int,
            session_id: str | None = None,
            payload: bytes | None = None,
    ) -> None:
        optional = ProtocolOptionalFields(event=event, session_id=session_id).as_bytes()
        await cls._send_protocol_message(
            ws,
            header=FULL_CLIENT_REQUEST_HEADER,
            optional=optional,
            payload=payload if payload is not None else EMPTY_JSON_BYTES,
        )

    @classmethod
    def _build_request_payload(
            cls,
            *,
            event: int,
            speaker: str,
            text: str = '',
            audio_format: str = 'mp3',
            speech_rate: int = 0,
            loudness_rate: int = 0,
    ) -> bytes:
        payload = {
            'user': {'uid': 'fba'},
            'event': event,
            'namespace': 'BidirectionalTTS',
            'req_params': {
                'text': text,
                'speaker': speaker,
                'audio_params': {
                    'format': audio_format,
                    'sample_rate': cls.DEFAULT_SAMPLE_RATE,
                    'speech_rate': int(speech_rate),
                    'loudness_rate': int(loudness_rate),
                },
                'additions': json.dumps({}, ensure_ascii=False),
            },
        }
        return json.dumps(payload, ensure_ascii=False).encode('utf-8')

    @staticmethod
    def _require_bytes(res: bytes, offset: int, size: int, field_name: str) -> None:
        if len(res) < offset + size:
            raise ValueError(f'parse {field_name} failed because response bytes are too short')

    @classmethod
    def _read_response_text(cls, res: bytes, offset: int) -> tuple[str, int]:
        cls._require_bytes(res, offset, 4, 'content size')
        content_size = int.from_bytes(res[offset: offset + 4], 'big', signed=True)
        if content_size < 0:
            raise ValueError('content_size cannot be negative')
        offset += 4
        cls._require_bytes(res, offset, content_size, 'content')
        content = res[offset: offset + content_size].decode('utf-8', errors='ignore')
        return content, offset + content_size

    @classmethod
    def _read_response_payload(cls, res: bytes, offset: int) -> tuple[bytes, int]:
        cls._require_bytes(res, offset, 4, 'payload size')
        payload_size = int.from_bytes(res[offset: offset + 4], 'big', signed=True)
        if payload_size < 0:
            raise ValueError('payload_size cannot be negative')
        offset += 4
        cls._require_bytes(res, offset, payload_size, 'payload')
        payload = res[offset: offset + payload_size]
        return payload, offset + payload_size

    @staticmethod
    def _decode_payload_text(payload: bytes | None) -> str:
        if not payload:
            return ''
        return payload.decode('utf-8', errors='ignore')

    @classmethod
    def _parse_response(cls, res: bytes | str) -> ProtocolResponse:
        if isinstance(res, str):
            raise RuntimeError(res)

        response = ProtocolResponse(
            header=ProtocolHeader(),
            optional=ProtocolOptionalFields(),
        )
        cls._require_bytes(res, 0, FIXED_HEADER_BYTES, 'fixed header')

        bit_mask = 0b00001111
        response.header.protocol_version = (res[0] >> 4) & bit_mask
        response.header.header_size = res[0] & bit_mask
        response.header.message_type = (res[1] >> 4) & bit_mask
        response.header.message_type_specific_flags = res[1] & bit_mask
        response.header.serial_method = (res[2] >> 4) & bit_mask
        response.header.compression_type = res[2] & bit_mask
        response.header.reserved_data = res[3]

        offset = FIXED_HEADER_BYTES
        if response.header.message_type in (FULL_SERVER_RESPONSE, AUDIO_ONLY_RESPONSE):
            if response.header.message_type_specific_flags == MSG_TYPE_FLAG_WITH_EVENT:
                cls._require_bytes(res, offset, 4, 'event')
                response.optional.event = int.from_bytes(
                    res[offset: offset + 4],
                    'big',
                    signed=True,
                )
                offset += 4

            if response.optional.event == EVENT_CONNECTION_STARTED:
                response.optional.connection_id, offset = cls._read_response_text(res, offset)
            elif response.optional.event == EVENT_CONNECTION_FAILED:
                response.optional.response_meta_json, offset = cls._read_response_text(res, offset)
            elif response.optional.event in (
                    EVENT_SESSION_STARTED,
                    EVENT_SESSION_FAILED,
                    EVENT_SESSION_FINISHED,
            ):
                response.optional.session_id, offset = cls._read_response_text(res, offset)
                response.optional.response_meta_json, offset = cls._read_response_text(res, offset)
            elif response.optional.event not in (EVENT_NONE, EVENT_CONNECTION_FINISHED):
                response.optional.session_id, offset = cls._read_response_text(res, offset)
                if offset < len(res):
                    response.payload, offset = cls._read_response_payload(res, offset)

        elif response.header.message_type == ERROR_INFORMATION:
            cls._require_bytes(res, offset, 4, 'error code')
            response.optional.error_code = int.from_bytes(
                res[offset: offset + 4],
                'big',
                signed=True,
            )
            offset += 4
            if offset < len(res):
                response.payload, offset = cls._read_response_payload(res, offset)

        return response


tts_stream_service = TTSStreamService()
