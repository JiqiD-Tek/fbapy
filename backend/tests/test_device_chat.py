import asyncio

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from pydantic import ValidationError
from sqlalchemy import JSON

from backend.app.cloud.model import DeviceChat
from backend.app.cloud.schema.device.device_chat import CreateDeviceChatParam
from backend.app.cloud.service.device_service import device_service


def _build_chat_payload() -> dict:
    return {
        'content': {
            'user_message': 'Where should we go today?',
            'replies': [
                {'toy_id': 1, 'reply_message': 'Let us go to the park.'},
                {'toy_id': 2, 'reply_message': 'I will bring a kite.'},
            ],
        },
    }


def test_create_device_chat_param_accepts_multiple_toy_replies() -> None:
    obj = CreateDeviceChatParam.model_validate(_build_chat_payload())

    assert obj.model_dump() == _build_chat_payload()


@pytest.mark.parametrize(
    'payload',
    [
        {'content': {'user_message': 'Question', 'replies': []}},
        {'content': {'user_message': '   ', 'replies': [{'toy_id': 1, 'reply_message': 'Reply'}]}},
        {'content': {'user_message': 'Question', 'replies': [{'toy_id': 1, 'reply_message': '   '}]}},
    ],
)
def test_create_device_chat_param_rejects_incomplete_content(payload: dict) -> None:
    with pytest.raises(ValidationError):
        CreateDeviceChatParam.model_validate(payload)


def test_device_chat_model_uses_single_json_content_column() -> None:
    columns = DeviceChat.__table__.columns

    assert isinstance(columns.content.type, JSON)
    assert 'toy_id' not in columns
    assert 'user_message' not in columns
    assert 'reply_message' not in columns
    assert 'idx_device_chat_device_toy_time' not in {index.name for index in DeviceChat.__table__.indexes}


def test_create_chat_persists_content_json(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[DeviceChat] = []

    async def fake_get_baby(*, db: object, did: str) -> SimpleNamespace:  # noqa: RUF029
        assert did == 'device-1'
        return SimpleNamespace(device_id=10, user_id=20, id=30)

    async def fake_create(db: object, chat: DeviceChat) -> DeviceChat:  # noqa: RUF029
        captured.append(chat)
        return chat

    monkeypatch.setattr(
        'backend.app.cloud.service.device_service.baby_service.get_by_device_did',
        fake_get_baby,
    )
    monkeypatch.setattr(
        'backend.app.cloud.service.device_service.device_chat_dao.create',
        fake_create,
    )

    obj = CreateDeviceChatParam.model_validate(_build_chat_payload())
    asyncio.run(device_service.create_chat(db=object(), did='device-1', obj=obj))

    assert len(captured) == 1
    assert captured[0].device_id == 10
    assert captured[0].user_id == 20
    assert captured[0].baby_id == 30
    assert captured[0].content == _build_chat_payload()['content']


def test_get_chat_list_enriches_each_reply_with_toy_info(monkeypatch: pytest.MonkeyPatch) -> None:
    created_time = datetime(2026, 8, 13, 12, 0, 0, tzinfo=timezone.utc)
    chat = SimpleNamespace(
        id=100,
        device_id=10,
        content=_build_chat_payload()['content'],
        user_id=20,
        baby_id=30,
        created_time=created_time,
    )

    class _ToyResult:
        @staticmethod
        def scalars() -> SimpleNamespace:
            return SimpleNamespace(
                all=lambda: [
                    SimpleNamespace(
                        id=1,
                        series_id=101,
                        name='Toy one',
                        avatar_url='https://example.com/1.png',
                        summary=None,
                        nfc_code='nfc-1',
                    ),
                    SimpleNamespace(
                        id=2,
                        series_id=102,
                        name='Toy two',
                        avatar_url='https://example.com/2.png',
                        summary=None,
                        nfc_code='nfc-2',
                    ),
                ],
            )

    class _FakeDB:
        @staticmethod
        async def execute(stmt: object) -> _ToyResult:
            return _ToyResult()

    async def fake_ensure_user_has_device(  # noqa: RUF029
        *,
        db: object,
        user_id: int,
        device_id: int,
    ) -> SimpleNamespace:
        return SimpleNamespace(id=device_id)

    async def fake_get_select(*, device_id: int, baby_id: int | None) -> object:  # noqa: RUF029
        return object()

    async def fake_paging_data(db: object, stmt: object) -> dict[str, Any]:  # noqa: RUF029
        return {'items': [chat], 'total': 1}

    monkeypatch.setattr(
        'backend.app.cloud.service.device_service.DeviceService._ensure_user_has_device',
        fake_ensure_user_has_device,
    )
    monkeypatch.setattr(
        'backend.app.cloud.service.device_service.device_chat_dao.get_select',
        fake_get_select,
    )
    monkeypatch.setattr('backend.app.cloud.service.device_service.paging_data', fake_paging_data)

    page = asyncio.run(
        device_service.get_chat_list(
            db=_FakeDB(),
            device_id=10,
            user_id=20,
        )
    )

    replies = page['items'][0]['content']['replies']
    assert [reply['toy_id'] for reply in replies] == [1, 2]
    assert [reply['toy']['name'] for reply in replies] == ['Toy one', 'Toy two']
