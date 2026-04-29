# -*- coding: UTF-8 -*-
"""
Simple Huoshan stream ASR service.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import gzip
import io
import json
import uuid
import wave
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, ClassVar

import websockets

from backend.app.cloud.schema.resource.huoshan import (
    HuoshanStreamASRParam,
    HuoshanStreamASRResult,
)
from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings

SUCCESS_CODES = {0, 1000, 20000000}
SERVER_ERROR_RESPONSE = 0x0F
MESSAGE_TYPE_FULL_REQUEST = 0x01
MESSAGE_TYPE_AUDIO = 0x02
LAST_AUDIO_FLAG = 0x02
RESPONSE_BODY_OFFSET = 12
MAX_WS_MESSAGE_SIZE = 1_000_000_000


class DoubaoProtocolError(Exception):
    """Doubao streaming protocol error."""


@dataclass(frozen=True, slots=True)
class ASRAudioSpec:
    pcm_bytes: bytes
    sample_rate: int
    bits: int
    channel: int


def _build_auth_headers(
        app_id: str,
        access_token: str,
        resource_id: str,
) -> dict[str, str]:
    return {
        'X-Api-App-Key': app_id,
        'X-Api-Access-Key': access_token,
        'X-Api-Resource-Id': resource_id,
        'X-Api-Connect-Id': str(uuid.uuid4()),
    }


def _build_protocol_header(
        *,
        version: int = 0x01,
        message_type: int = MESSAGE_TYPE_FULL_REQUEST,
        message_flags: int = 0x00,
        serialization_method: int = 0x01,
        compression_type: int = 0x01,
        reserved_data: int = 0x00,
        extension_header: bytes = b'',
) -> bytearray:
    header = bytearray()
    header_size = int(len(extension_header) / 4) + 1
    header.append((version << 4) | header_size)
    header.append((message_type << 4) | message_flags)
    header.append((serialization_method << 4) | compression_type)
    header.append(reserved_data)
    header.extend(extension_header)
    return header


def _build_request_packet(
        payload: bytes,
        *,
        message_type: int,
        message_flags: int = 0x00,
) -> bytearray:
    packet = bytearray(
        _build_protocol_header(
            message_type=message_type,
            message_flags=message_flags,
        )
    )
    packet.extend(len(payload).to_bytes(4, 'big'))
    packet.extend(payload)
    return packet


def _build_json_request_packet(request: dict[str, Any]) -> bytearray:
    payload = gzip.compress(json.dumps(request, ensure_ascii=False).encode('utf-8'))
    return _build_request_packet(
        payload,
        message_type=MESSAGE_TYPE_FULL_REQUEST,
    )


def _build_audio_request_packet(
        pcm_frame: bytes,
        *,
        is_final: bool = False,
) -> bytearray:
    payload = gzip.compress(pcm_frame)
    return _build_request_packet(
        payload,
        message_type=MESSAGE_TYPE_AUDIO,
        message_flags=LAST_AUDIO_FLAG if is_final else 0x00,
    )


def _parse_protocol_response(response: bytes) -> dict[str, Any]:
    if len(response) < 4:
        raise DoubaoProtocolError(f'Response too short: {len(response)}')

    message_type = response[1] >> 4
    if message_type == SERVER_ERROR_RESPONSE:
        if len(response) < RESPONSE_BODY_OFFSET:
            raise DoubaoProtocolError(f'Error response too short: {len(response)}')
        return {
            'code': int.from_bytes(response[4:8], 'big', signed=False),
            'msg_length': int.from_bytes(response[8:12], 'big', signed=False),
            'payload_msg': json.loads(response[12:].decode('utf-8')),
        }

    if len(response) <= RESPONSE_BODY_OFFSET:
        return {'payload_msg': {}}

    return {
        'payload_msg': json.loads(response[RESPONSE_BODY_OFFSET:].decode('utf-8')),
    }


def _extract_response_code(result: dict[str, Any]) -> int | None:
    payload = result.get('payload_msg')
    if isinstance(payload, dict) and 'code' in payload:
        return payload['code']

    code = result.get('code')
    return int(code) if code is not None else None


def _is_success_code(code: int | None) -> bool:
    return code is None or code in SUCCESS_CODES


class ASRRealtimeSession:
    def __init__(
            self,
            *,
            service: ASRStreamService,
            request_id: str,
            stream_config: dict[str, Any],
            audio_spec: ASRAudioSpec,
            websocket: Any,
    ) -> None:
        self._service = service
        self.request_id = request_id
        self.stream_config = stream_config
        self.audio_spec = audio_spec
        self.websocket = websocket
        self._frame_size = self._service._resolve_frame_size(
            audio_spec,
            int(self.stream_config.get('frame_duration_ms') or self._service.DEFAULT_FRAME_DURATION_MS),
        )
        self._pending_audio = bytearray()
        self._input_finished = False
        self._closed = False
        self._latest_text = ''

    async def send_audio_chunk(self, audio_chunk: bytes) -> None:
        if self._closed:
            raise errors.RequestError(msg='ASR realtime session is already closed')
        if self._input_finished:
            raise errors.RequestError(msg='ASR realtime input has already finished')
        if not audio_chunk:
            return

        self._pending_audio.extend(audio_chunk)
        await self._flush_pending_audio()

    async def finish_input(self) -> None:
        if self._closed or self._input_finished:
            return

        try:
            if self._pending_audio:
                await self.websocket.send(_build_audio_request_packet(bytes(self._pending_audio)))
                self._pending_audio.clear()
            await self.websocket.send(_build_audio_request_packet(b'', is_final=True))
        except websockets.ConnectionClosed as exc:
            raise DoubaoProtocolError(f'Huoshan ASR websocket is closed: {exc}') from exc
        self._input_finished = True

    async def iter_events(self):
        while True:
            try:
                response = await self._receive_message()
            except asyncio.TimeoutError:
                break
            except websockets.ConnectionClosed:
                break

            result = _parse_protocol_response(response)
            log.debug(f'Receive Huoshan realtime ASR result: {result}')
            for event in self._build_events(result):
                yield event

        yield {
            'type': 'completed',
            'request_id': self.request_id,
            'text': self._latest_text,
        }

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._pending_audio.clear()
        with suppress(Exception):
            await self.websocket.close()

    async def _flush_pending_audio(self) -> None:
        try:
            while len(self._pending_audio) >= self._frame_size:
                frame = bytes(self._pending_audio[:self._frame_size])
                del self._pending_audio[:self._frame_size]
                await self.websocket.send(_build_audio_request_packet(frame))
        except websockets.ConnectionClosed as exc:
            raise DoubaoProtocolError(f'Huoshan ASR websocket is closed: {exc}') from exc

    async def _receive_message(self) -> bytes:
        if self._input_finished:
            return await asyncio.wait_for(
                self.websocket.recv(),
                timeout=self._service.DEFAULT_REALTIME_FINAL_TIMEOUT_SECONDS,
            )
        return await self.websocket.recv()

    def _build_events(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        response_code = _extract_response_code(result)
        if not _is_success_code(response_code):
            payload = result.get('payload_msg')
            if isinstance(payload, dict):
                error_message = (
                    payload.get('error')
                    or payload.get('message')
                    or json.dumps(payload, ensure_ascii=False)
                )
            else:
                error_message = str(response_code)
            raise DoubaoProtocolError(f'Huoshan ASR returned error: {error_message}')

        payload = result.get('payload_msg')
        if not isinstance(payload, dict):
            return []

        result_payload = payload.get('result')
        if not isinstance(result_payload, dict):
            return []

        events: list[dict[str, Any]] = []
        result_text = self._service._normalize_text(result_payload.get('text'))
        if result_text:
            self._latest_text = result_text
            events.append(
                {
                    'type': 'partial',
                    'request_id': self.request_id,
                    'text': result_text,
                }
            )

        utterances = result_payload.get('utterances')
        if not isinstance(utterances, list):
            return events

        for utterance in utterances:
            if not isinstance(utterance, dict):
                continue
            if not utterance.get('definite', False):
                continue

            utterance_text = self._service._normalize_text(utterance.get('text'))
            if not utterance_text:
                continue

            events.append(
                {
                    'type': 'final',
                    'request_id': self.request_id,
                    'text': utterance_text,
                }
            )
        return events


class ASRStreamService:
    DEFAULT_WS_URL: ClassVar[str] = 'wss://openspeech.bytedance.com/api/v3/sauc/bigmodel'
    DEFAULT_RESOURCE_ID: ClassVar[str] = 'volc.bigasr.sauc.duration'
    DEFAULT_WORKFLOW: ClassVar[str] = 'audio_in,resample,partition,vad,fe,decode,itn,nlu_punctuate'
    DEFAULT_RESULT_TYPE: ClassVar[str] = 'single'
    DEFAULT_AUDIO_FORMAT: ClassVar[str] = 'pcm'
    DEFAULT_AUDIO_CODEC: ClassVar[str] = 'pcm'
    DEFAULT_SAMPLE_RATE: ClassVar[int] = 16000
    DEFAULT_BITS: ClassVar[int] = 16
    DEFAULT_CHANNEL: ClassVar[int] = 1
    DEFAULT_END_WINDOW_SIZE: ClassVar[int] = 200
    DEFAULT_FRAME_DURATION_MS: ClassVar[int] = 200
    DEFAULT_RECV_TIMEOUT_SECONDS: ClassVar[float] = 10.0
    DEFAULT_REALTIME_FINAL_TIMEOUT_SECONDS: ClassVar[float] = 1.5
    DEFAULT_UID: ClassVar[str] = 'huoshan_stream_asr_service'

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return str(value or '').strip()

    @classmethod
    def _read_positive_int(cls, value: Any, default: int, field_name: str) -> int:
        if value in (None, ''):
            return default
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise errors.RequestError(msg=f'invalid {field_name}') from exc
        if parsed <= 0:
            raise errors.RequestError(msg=f'invalid {field_name}')
        return parsed

    @classmethod
    def _resolve_stream_config(cls) -> dict[str, Any]:
        appid = cls._normalize_text(settings.BYTES_ASR_APPID)
        access_token = cls._normalize_text(settings.BYTES_ASR_TOKEN)
        cluster = cls._normalize_text(settings.BYTES_ASR_CLUSTER)
        if not appid or not access_token or not cluster:
            raise errors.ServerError(
                msg='Huoshan ASR config requires appid, access_token and cluster'
            )

        return {
            'appid': appid,
            'access_token': access_token,
            'cluster': cluster,
            'ws_url': cls._normalize_text(settings.BYTES_ASR_STREAM_WS_URL) or cls.DEFAULT_WS_URL,
            'resource_id': cls.DEFAULT_RESOURCE_ID,
            'workflow': cls.DEFAULT_WORKFLOW,
            'result_type': cls.DEFAULT_RESULT_TYPE,
            'format': cls.DEFAULT_AUDIO_FORMAT,
            'codec': cls.DEFAULT_AUDIO_CODEC,
            'sample_rate': cls.DEFAULT_SAMPLE_RATE,
            'bits': cls.DEFAULT_BITS,
            'channel': cls.DEFAULT_CHANNEL,
            'end_window_size': cls.DEFAULT_END_WINDOW_SIZE,
            'frame_duration_ms': cls.DEFAULT_FRAME_DURATION_MS,
            'recv_timeout_seconds': cls.DEFAULT_RECV_TIMEOUT_SECONDS,
            'realtime_final_timeout_seconds': cls.DEFAULT_REALTIME_FINAL_TIMEOUT_SECONDS,
        }

    @classmethod
    def _decode_base64_audio(cls, value: str) -> bytes:
        normalized_value = cls._normalize_text(value)
        if not normalized_value:
            raise errors.RequestError(msg='audio_base64 is required')

        try:
            return base64.b64decode(normalized_value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise errors.RequestError(msg='audio_base64 is invalid') from exc

    @classmethod
    def _resolve_audio_spec(
            cls,
            obj: HuoshanStreamASRParam,
            stream_config: dict[str, Any],
    ) -> ASRAudioSpec:
        audio_bytes = cls._decode_base64_audio(obj.audio_base64)
        if not audio_bytes:
            raise errors.RequestError(msg='audio data is empty')

        if obj.audio_format == 'wav':
            return cls._resolve_wav_audio_spec(audio_bytes)

        return ASRAudioSpec(
            pcm_bytes=audio_bytes,
            sample_rate=stream_config['sample_rate'],
            bits=stream_config['bits'],
            channel=stream_config['channel'],
        )

    @staticmethod
    def _resolve_wav_audio_spec(audio_bytes: bytes) -> ASRAudioSpec:
        try:
            with wave.open(io.BytesIO(audio_bytes), 'rb') as wav_file:
                pcm_bytes = wav_file.readframes(wav_file.getnframes())
                sample_rate = wav_file.getframerate()
                bits = wav_file.getsampwidth() * 8
                channel = wav_file.getnchannels()
        except wave.Error as exc:
            raise errors.RequestError(msg='invalid wav audio data') from exc

        if not pcm_bytes:
            raise errors.RequestError(msg='wav audio data is empty')

        return ASRAudioSpec(
            pcm_bytes=pcm_bytes,
            sample_rate=sample_rate,
            bits=bits,
            channel=channel,
        )

    @classmethod
    def build_realtime_audio_spec(
            cls,
            *,
            sample_rate: Any = None,
            bits: Any = None,
            channel: Any = None,
    ) -> ASRAudioSpec:
        return ASRAudioSpec(
            pcm_bytes=b'',
            sample_rate=cls._read_positive_int(
                sample_rate,
                cls.DEFAULT_SAMPLE_RATE,
                'sample_rate',
            ),
            bits=cls._read_positive_int(bits, cls.DEFAULT_BITS, 'bits'),
            channel=cls._read_positive_int(channel, cls.DEFAULT_CHANNEL, 'channel'),
        )

    @classmethod
    def _resolve_frame_size(
            cls,
            audio_spec: ASRAudioSpec,
            frame_duration_ms: int,
    ) -> int:
        bytes_per_sample = max(1, audio_spec.bits // 8)
        frame_size = (
            audio_spec.sample_rate
            * bytes_per_sample
            * audio_spec.channel
            * frame_duration_ms
        ) // 1000
        if frame_size <= 0:
            raise errors.RequestError(msg='invalid ASR frame size')
        return frame_size

    @classmethod
    def _build_request_payload(
            cls,
            *,
            request_id: str,
            stream_config: dict[str, Any],
            audio_spec: ASRAudioSpec,
    ) -> dict[str, Any]:
        return {
            'app': {
                'appid': stream_config['appid'],
                'cluster': stream_config['cluster'],
                'token': stream_config['access_token'],
            },
            'user': {'uid': cls.DEFAULT_UID},
            'request': {
                'reqid': request_id,
                'workflow': stream_config['workflow'],
                'show_utterances': True,
                'result_type': stream_config['result_type'],
                'sequence': 1,
                'end_window_size': stream_config['end_window_size'],
            },
            'audio': {
                'format': stream_config['format'],
                'codec': stream_config['codec'],
                'rate': audio_spec.sample_rate,
                'bits': audio_spec.bits,
                'channel': audio_spec.channel,
                'sample_rate': audio_spec.sample_rate,
            },
        }

    @staticmethod
    def _mask_request_for_log(request: dict[str, Any]) -> dict[str, Any]:
        masked_request = json.loads(json.dumps(request, ensure_ascii=False))
        app_config = masked_request.get('app', {})
        token = app_config.get('token')
        if token:
            token_text = str(token)
            app_config['token'] = f'{token_text[:4]}***'
        return masked_request

    async def create_realtime_session(
            self,
            *,
            sample_rate: Any = None,
            bits: Any = None,
            channel: Any = None,
    ) -> ASRRealtimeSession:
        request_id = uuid.uuid4().hex
        stream_config = self._resolve_stream_config()
        audio_spec = self.build_realtime_audio_spec(
            sample_rate=sample_rate,
            bits=bits,
            channel=channel,
        )
        websocket = await self._open_upstream_websocket(stream_config)
        try:
            await self._send_init_request(
                websocket,
                request_id=request_id,
                stream_config=stream_config,
                audio_spec=audio_spec,
            )
        except Exception:
            with suppress(Exception):
                await websocket.close()
            raise

        return ASRRealtimeSession(
            service=self,
            request_id=request_id,
            stream_config=stream_config,
            audio_spec=audio_spec,
            websocket=websocket,
        )

    async def transcribe(self, obj: HuoshanStreamASRParam) -> HuoshanStreamASRResult:
        request_id = uuid.uuid4().hex
        stream_config = self._resolve_stream_config()
        audio_spec = self._resolve_audio_spec(obj, stream_config)

        websocket = None
        receiver_task: asyncio.Task[str] | None = None
        try:
            websocket = await self._open_upstream_websocket(stream_config)

            await self._send_init_request(
                websocket,
                request_id=request_id,
                stream_config=stream_config,
                audio_spec=audio_spec,
            )
            receiver_task = asyncio.create_task(
                self._receive_results(
                    websocket,
                    recv_timeout_seconds=stream_config['recv_timeout_seconds'],
                ),
                name=f'huoshan-stream-asr:{request_id}',
            )
            await self._send_pcm_frames(
                websocket,
                audio_spec=audio_spec,
                frame_duration_ms=stream_config['frame_duration_ms'],
            )
            await websocket.send(_build_audio_request_packet(b'', is_final=True))
            text = await receiver_task
            return HuoshanStreamASRResult(request_id=request_id, text=text)
        except errors.BaseExceptionError:
            raise
        except DoubaoProtocolError as exc:
            log.error(f'Huoshan stream ASR protocol failed: request_id={request_id}, error={exc}')
            raise errors.GatewayError(msg=str(exc)) from exc
        except Exception as exc:
            log.error(f'Huoshan stream ASR failed: request_id={request_id}, error={exc}')
            raise errors.GatewayError(msg='Huoshan stream ASR failed') from exc
        finally:
            if receiver_task is not None and not receiver_task.done():
                receiver_task.cancel()
                with suppress(asyncio.CancelledError):
                    await receiver_task
            if websocket is not None:
                with suppress(Exception):
                    await websocket.close()

    async def _send_init_request(
            self,
            websocket: Any,
            *,
            request_id: str,
            stream_config: dict[str, Any],
            audio_spec: ASRAudioSpec,
    ) -> None:
        request_payload = self._build_request_payload(
            request_id=request_id,
            stream_config=stream_config,
            audio_spec=audio_spec,
        )
        log.debug(
            'Send Huoshan ASR init request: '
            f'{json.dumps(self._mask_request_for_log(request_payload), ensure_ascii=False)}'
        )
        await websocket.send(_build_json_request_packet(request_payload))

        response = _parse_protocol_response(await websocket.recv())
        log.debug(f'Receive Huoshan ASR init response: {response}')
        response_code = _extract_response_code(response)
        if _is_success_code(response_code):
            return

        payload = response.get('payload_msg')
        if isinstance(payload, dict):
            error_message = (
                payload.get('error')
                or payload.get('message')
                or json.dumps(payload, ensure_ascii=False)
            )
        else:
            error_message = 'unknown error'
        raise DoubaoProtocolError(f'Huoshan ASR init failed: {error_message}')

    async def _open_upstream_websocket(self, stream_config: dict[str, Any]):
        return await websockets.connect(
            stream_config['ws_url'],
            additional_headers=_build_auth_headers(
                stream_config['appid'],
                stream_config['access_token'],
                stream_config['resource_id'],
            ),
            max_size=MAX_WS_MESSAGE_SIZE,
            ping_interval=None,
            ping_timeout=None,
            close_timeout=10,
        )

    async def _send_pcm_frames(
            self,
            websocket: Any,
            *,
            audio_spec: ASRAudioSpec,
            frame_duration_ms: int,
    ) -> None:
        frame_size = self._resolve_frame_size(audio_spec, frame_duration_ms)
        for start in range(0, len(audio_spec.pcm_bytes), frame_size):
            frame = audio_spec.pcm_bytes[start:start + frame_size]
            await websocket.send(_build_audio_request_packet(frame))

    async def _receive_results(
            self,
            websocket: Any,
            *,
            recv_timeout_seconds: float,
    ) -> str:
        definite_segments: list[str] = []
        latest_text = ''

        while True:
            try:
                response = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=recv_timeout_seconds,
                )
            except asyncio.TimeoutError:
                break
            except websockets.ConnectionClosed:
                break

            result = _parse_protocol_response(response)
            log.debug(f'Receive Huoshan ASR result: {result}')

            response_code = _extract_response_code(result)
            if not _is_success_code(response_code):
                payload = result.get('payload_msg')
                if isinstance(payload, dict):
                    error_message = (
                        payload.get('error')
                        or payload.get('message')
                        or json.dumps(payload, ensure_ascii=False)
                    )
                else:
                    error_message = str(response_code)
                raise DoubaoProtocolError(f'Huoshan ASR returned error: {error_message}')

            payload = result.get('payload_msg')
            if not isinstance(payload, dict):
                continue

            result_payload = payload.get('result')
            if not isinstance(result_payload, dict):
                continue

            result_text = self._normalize_text(result_payload.get('text'))
            if result_text:
                latest_text = result_text

            utterances = result_payload.get('utterances')
            if not isinstance(utterances, list):
                continue

            for utterance in utterances:
                if not isinstance(utterance, dict):
                    continue
                if not utterance.get('definite', False):
                    continue

                utterance_text = self._normalize_text(utterance.get('text'))
                if not utterance_text:
                    continue
                if definite_segments and definite_segments[-1] == utterance_text:
                    continue
                definite_segments.append(utterance_text)

        if definite_segments:
            return ''.join(definite_segments)
        return latest_text


asr_stream_service = ASRStreamService()
