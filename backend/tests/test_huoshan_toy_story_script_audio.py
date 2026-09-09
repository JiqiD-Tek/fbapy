import asyncio

from pathlib import Path

import pytest

from backend.app.cloud.schema.resource.huoshan import (
    HuoshanToyStoryScriptLine,
    HuoshanToyStoryScriptResult,
    HuoshanToyStoryToyInfo,
)
from backend.app.cloud.service.resource.huoshan import service as huoshan_service_module
from backend.app.cloud.service.resource.huoshan.service import huoshan_voice_service


def test_toy_story_script_save_content_uses_complete_audio_and_line_ranges(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = HuoshanToyStoryScriptResult(
        task_id='task-1',
        toy_ids=[1, 2],
        text='story',
        model='model',
        toys=[
            HuoshanToyStoryToyInfo(toy_id=1, name='one', speaker='speaker-1'),
            HuoshanToyStoryToyInfo(toy_id=2, name='two', speaker='speaker-2'),
        ],
        lines=[
            HuoshanToyStoryScriptLine(toy_id=1, text='first', tts_token='token-1'),
            HuoshanToyStoryScriptLine(toy_id=2, text='second', tts_token='token-2'),
        ],
        device_id=1,
        is_completed=True,
        task_status=2,
    )
    requests: list[tuple[str, str, str, int, int]] = []
    durations = iter([1.25, 2.5])

    async def fake_query_and_wait(*, obj, request_id: str) -> None:
        requests.append((request_id, obj.text, obj.speaker, obj.speech_rate, obj.loudness_rate))

    async def fake_get_audio_bytes(*, request_id: str) -> bytes:
        return request_id.encode()

    def fake_probe_audio_duration(path: Path) -> float:
        return next(durations)

    def fake_concatenate_audio_segments(segment_paths: list[Path], output_path: Path) -> None:
        output_path.write_bytes(b'complete-audio')

    async def fake_upload_bytes(*, key: str, data: bytes) -> str:
        assert key.endswith('/task-1.mp3')
        assert data == b'complete-audio'
        return 'https://cdn.example.com/task-1.mp3'

    monkeypatch.setattr(huoshan_service_module.tts_stream_service, 'query_and_wait', fake_query_and_wait)
    monkeypatch.setattr(huoshan_service_module.tts_stream_service, 'get_audio_bytes', fake_get_audio_bytes)
    monkeypatch.setattr(huoshan_service_module, 'probe_audio_duration', fake_probe_audio_duration)
    monkeypatch.setattr(huoshan_service_module, 'concatenate_audio_segments', fake_concatenate_audio_segments)
    monkeypatch.setattr(huoshan_service_module.oss_client, 'upload_bytes', fake_upload_bytes)

    content, play_url = asyncio.run(huoshan_voice_service._build_toy_story_script_content(result))

    assert requests == [
        ('token-1', 'first', 'speaker-1', 0, 0),
        ('token-2', 'second', 'speaker-2', 0, 0),
    ]
    assert [line.model_dump() for line in content] == [
        {
            'toy_id': 1,
            'text': 'first',
            'start_at': '00:00:00.000',
            'end_at': '00:00:01.250',
        },
        {
            'toy_id': 2,
            'text': 'second',
            'start_at': '00:00:01.250',
            'end_at': '00:00:03.750',
        },
    ]
    assert play_url == 'https://cdn.example.com/task-1.mp3'
