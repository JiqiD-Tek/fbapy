from __future__ import annotations

import asyncio

from types import SimpleNamespace

import pytest

from pydantic import ValidationError

from backend.app.cloud.schema.resource.role import CreateRoleParam
from backend.app.cloud.service.resource import role_service as role_service_module
from backend.app.cloud.service.resource.role_service import CloudRoleService
from backend.common.exception import errors


def test_create_role_param_trims_and_normalizes_text_fields() -> None:
    obj = CreateRoleParam(
        group_key='  planet-x  ',
        name='  scientist  ',
        system_prompt='  stay rational  ',
        avatar_url='   ',
        summary='   ',
        voice_provider='  huoshan  ',
        voice_id='  voice-1  ',
        voice_type=1,
        voice_name='  Brayan  ',
        voice_language='  zh-CN  ',
        status=1,
        sort=0,
        remark='  note  ',
    )

    assert obj.group_key == 'planet-x'
    assert obj.name == 'scientist'
    assert obj.system_prompt == 'stay rational'
    assert obj.avatar_url is None
    assert obj.summary is None
    assert obj.voice_provider == 'huoshan'
    assert obj.voice_id == 'voice-1'
    assert obj.voice_name == 'Brayan'
    assert obj.voice_language == 'zh-CN'
    assert obj.remark == 'note'


def test_create_role_param_rejects_blank_required_fields() -> None:
    with pytest.raises(ValidationError):
        CreateRoleParam(name='  ', system_prompt='ready')

    with pytest.raises(ValidationError):
        CreateRoleParam(name='ready', system_prompt='  ')


def test_create_role_param_requires_complete_voice_binding() -> None:
    with pytest.raises(ValidationError):
        CreateRoleParam(
            name='scientist',
            system_prompt='stay rational',
            voice_provider='huoshan',
        )


def test_create_role_delegates_to_dao(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def create_stub(db: object, obj: CreateRoleParam) -> SimpleNamespace:
        captured['db'] = db
        captured['obj'] = obj
        return SimpleNamespace(id=1, name=obj.name, group_key=obj.group_key, summary=obj.summary)

    monkeypatch.setattr(role_service_module.cloud_role_dao, 'create', create_stub)

    result = asyncio.run(
        CloudRoleService.create_role(
            db=object(),
            obj=CreateRoleParam(
                group_key='planet-x',
                name='scientist',
                system_prompt='stay rational',
            ),
        )
    )

    assert isinstance(captured['obj'], CreateRoleParam)
    assert result.name == 'scientist'


def test_get_roles_by_ids_preserves_order(monkeypatch: pytest.MonkeyPatch) -> None:
    async def get_by_ids_stub(db: object, *, ids: list[int], enabled_only: bool = False) -> list[SimpleNamespace]:
        assert ids == [3, 1]
        assert enabled_only is True
        return [
            SimpleNamespace(id=1, name='one'),
            SimpleNamespace(id=3, name='three'),
        ]

    monkeypatch.setattr(role_service_module.cloud_role_dao, 'get_by_ids', get_by_ids_stub)

    roles = asyncio.run(
        CloudRoleService.get_roles_by_ids(
            db=object(),
            role_ids=[3, 1],
        )
    )

    assert [role.id for role in roles] == [3, 1]


def test_get_roles_by_ids_rejects_missing_role(monkeypatch: pytest.MonkeyPatch) -> None:
    async def get_by_ids_stub(db: object, *, ids: list[int], enabled_only: bool = False) -> list[SimpleNamespace]:
        return [SimpleNamespace(id=1, name='one')]

    monkeypatch.setattr(role_service_module.cloud_role_dao, 'get_by_ids', get_by_ids_stub)

    with pytest.raises(errors.NotFoundError):
        asyncio.run(
            CloudRoleService.get_roles_by_ids(
                db=object(),
                role_ids=[1, 2],
            )
        )
