import asyncio

from types import SimpleNamespace

import pytest

from backend.app.cloud.schema.resource.script import UpdateScriptFavoriteParam
from backend.app.cloud.service.resource.script_service import script_service
from backend.common.exception import errors


class _ScalarResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar_one_or_none(self) -> int | None:
        return self._value or None


class _FakeDB:
    def __init__(self, baby_id: int | None) -> None:
        self._baby_id = baby_id

    async def execute(self, stmt):
        return _ScalarResult(self._baby_id or 0)


def test_update_script_favorite_rejects_unowned_baby() -> None:
    with pytest.raises(errors.RequestError, match='宝宝不存在或不属于当前用户'):
        asyncio.run(
            script_service.update_script_favorite(
                db=_FakeDB(baby_id=None),
                user_id=7,
                pk=3,
                obj=UpdateScriptFavoriteParam(baby_id=9, favorite=1),
            )
        )


def test_update_script_favorite_rejects_script_from_other_baby(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(db, pk: int):
        assert pk == 3
        return SimpleNamespace(baby_id=12, favorite=0)

    monkeypatch.setattr(
        'backend.app.cloud.crud.resource.crud_script.script_dao.get',
        fake_get,
    )

    with pytest.raises(errors.RequestError, match='剧本不属于当前宝宝'):
        asyncio.run(
            script_service.update_script_favorite(
                db=_FakeDB(baby_id=9),
                user_id=7,
                pk=3,
                obj=UpdateScriptFavoriteParam(baby_id=9, favorite=1),
            )
        )


def test_update_script_favorite_updates_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_get(db, pk: int):
        assert pk == 3
        return SimpleNamespace(
            baby_id=9,
            favorite=0,
        )

    async def fake_update(db, pk: int, payload: dict) -> int:
        captured['pk'] = pk
        captured['payload'] = payload
        return 1

    monkeypatch.setattr(
        'backend.app.cloud.crud.resource.crud_script.script_dao.get',
        fake_get,
    )
    monkeypatch.setattr(
        'backend.app.cloud.crud.resource.crud_script.script_dao.update',
        fake_update,
    )
    count = asyncio.run(
        script_service.update_script_favorite(
            db=_FakeDB(baby_id=9),
            user_id=7,
            pk=3,
            obj=UpdateScriptFavoriteParam(baby_id=9, favorite=1),
        )
    )

    assert count == 1
    assert captured == {'pk': 3, 'payload': {'favorite': 1}}
