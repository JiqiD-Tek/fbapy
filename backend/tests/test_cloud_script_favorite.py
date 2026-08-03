import asyncio
from types import SimpleNamespace

import pytest

from backend.app.cloud.schema.resource.script import UpdateScriptFavoriteParam
from backend.app.cloud.service.resource.script_service import cloud_script_service
from backend.common.exception import errors


class _ScalarResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar_one(self) -> int:
        return self._value


class _FakeDB:
    def __init__(self, device_count: int) -> None:
        self._device_count = device_count

    async def execute(self, stmt):
        return _ScalarResult(self._device_count)


def test_update_script_favorite_rejects_unbound_device() -> None:
    with pytest.raises(errors.RequestError, match='Device does not belong to current user'):
        asyncio.run(
            cloud_script_service.update_script_favorite(
                db=_FakeDB(device_count=0),
                user_id=7,
                pk=3,
                obj=UpdateScriptFavoriteParam(device_id=9, favorite=1),
            )
        )


def test_update_script_favorite_rejects_script_from_other_device(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(db, pk: int):
        assert pk == 3
        return SimpleNamespace(device_id=12, favorite=0)

    monkeypatch.setattr(
        'backend.app.cloud.service.resource.script_service.cloud_script_dao.get',
        fake_get,
    )

    with pytest.raises(errors.RequestError, match='Script does not belong to current device'):
        asyncio.run(
            cloud_script_service.update_script_favorite(
                db=_FakeDB(device_count=1),
                user_id=7,
                pk=3,
                obj=UpdateScriptFavoriteParam(device_id=9, favorite=1),
            )
        )


def test_update_script_favorite_updates_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    started: list[int] = []

    async def fake_get(db, pk: int):
        assert pk == 3
        return SimpleNamespace(
            device_id=9,
            favorite=0,
            content=[{'toy_id': 1, 'text': 'hello', 'audio_url': None}],
            toy_ids=[1],
        )

    async def fake_update(db, pk: int, payload: dict) -> int:
        captured['pk'] = pk
        captured['payload'] = payload
        return 1

    def fake_start_script_audio_generation(*, script_id: int) -> None:
        started.append(script_id)

    monkeypatch.setattr(
        'backend.app.cloud.service.resource.script_service.cloud_script_dao.get',
        fake_get,
    )
    monkeypatch.setattr(
        'backend.app.cloud.service.resource.script_service.cloud_script_dao.update',
        fake_update,
    )
    monkeypatch.setattr(
        cloud_script_service,
        '_start_script_audio_generation',
        fake_start_script_audio_generation,
    )

    count = asyncio.run(
        cloud_script_service.update_script_favorite(
            db=_FakeDB(device_count=1),
            user_id=7,
            pk=3,
            obj=UpdateScriptFavoriteParam(device_id=9, favorite=1),
        )
    )

    assert count == 1
    assert captured == {'pk': 3, 'payload': {'favorite': 1}}
    assert started == [3]


def test_build_script_content_with_audio_generates_only_missing_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {
        'request_ids': [],
        'tts': [],
        'uploads': [],
    }

    async def fake_get_toys_by_ids(*, db, toy_ids: list[int]):
        assert toy_ids == [1, 2]
        return [
            SimpleNamespace(id=1, voice_id='speaker-1'),
            SimpleNamespace(id=2, voice_id='speaker-2'),
        ]

    async def fake_create_new_request() -> str:
        request_id = 'req-1'
        calls['request_ids'].append(request_id)
        return request_id

    async def fake_query_and_wait(*, obj, request_id: str):
        calls['tts'].append((request_id, obj.text, obj.speaker))
        return None

    async def fake_upload_audio_to_oss(*, request_id: str) -> str:
        calls['uploads'].append(request_id)
        return 'https://oss/generated.mp3'

    monkeypatch.setattr(
        'backend.app.cloud.service.resource.script_service.toy_service.get_toys_by_ids',
        fake_get_toys_by_ids,
    )
    monkeypatch.setattr(
        'backend.app.cloud.service.resource.script_service.tts_cache.create_new_request',
        fake_create_new_request,
    )
    monkeypatch.setattr(
        'backend.app.cloud.service.resource.script_service.tts_stream_service.query_and_wait',
        fake_query_and_wait,
    )
    monkeypatch.setattr(
        'backend.app.cloud.service.resource.script_service.tts_stream_service.upload_audio_to_oss',
        fake_upload_audio_to_oss,
    )

    content = asyncio.run(
        cloud_script_service._build_script_content_with_audio(
            db=_FakeDB(device_count=1),
            script=SimpleNamespace(
                toy_ids=[1, 2],
                content=[
                    {'toy_id': 1, 'text': 'line-1', 'audio_url': 'https://oss/existing.mp3'},
                    {'toy_id': 2, 'text': 'line-2', 'audio_url': None},
                ],
            ),
        )
    )

    assert content == [
        {'toy_id': 1, 'text': 'line-1', 'audio_url': 'https://oss/existing.mp3'},
        {'toy_id': 2, 'text': 'line-2', 'audio_url': 'https://oss/generated.mp3'},
    ]
    assert calls == {
        'request_ids': ['req-1'],
        'tts': [('req-1', 'line-2', 'speaker-2')],
        'uploads': ['req-1'],
    }
