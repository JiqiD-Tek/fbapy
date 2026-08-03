import asyncio
from types import SimpleNamespace

import pytest

from backend.app.cloud.api.v1.resource.huoshan import _resolve_toy_story_script_device_id
from backend.app.cloud.schema.user import DeviceAuthParam


def test_resolve_toy_story_script_device_id_uses_real_device_id_for_device_auth(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_by_did(*, db, did: str):
        assert db == 'db-session'
        assert did == 'device-did'
        return SimpleNamespace(id=42)

    monkeypatch.setattr(
        'backend.app.cloud.api.v1.resource.huoshan.device_service.get_by_did',
        fake_get_by_did,
    )

    device_id = asyncio.run(
        _resolve_toy_story_script_device_id(
            db='db-session',
            auth_ctx=DeviceAuthParam(mac='00:11:22:33:44:55', did='device-did', sn='SN-001', model='FBA-TOY'),
        )
    )

    assert device_id == 42


def test_resolve_toy_story_script_device_id_uses_platform_default_for_jwt_auth() -> None:
    device_id = asyncio.run(
        _resolve_toy_story_script_device_id(
            db='db-session',
            auth_ctx=SimpleNamespace(id=7, is_staff=True),
        )
    )

    assert device_id == 1
