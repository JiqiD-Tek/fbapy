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

    async def fake_get(db, pk: int):
        assert pk == 3
        return SimpleNamespace(device_id=9, favorite=0)

    async def fake_update(db, pk: int, payload: dict) -> int:
        captured['pk'] = pk
        captured['payload'] = payload
        return 1

    monkeypatch.setattr(
        'backend.app.cloud.service.resource.script_service.cloud_script_dao.get',
        fake_get,
    )
    monkeypatch.setattr(
        'backend.app.cloud.service.resource.script_service.cloud_script_dao.update',
        fake_update,
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
