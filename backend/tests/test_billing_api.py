import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from backend.app.cloud.api.router import v1
from backend.app.cloud.api.v1.resource.billing import open_session
from backend.app.cloud.api.v1.terminal.auth import fba_token
from backend.app.cloud.schema.user import DeviceAuthParam
from backend.app.cloud.service.billing_service import billing_service


def _device_auth() -> DeviceAuthParam:
    return DeviceAuthParam(
        mac='00:11:22:33:44:55',
        did='device-1',
        sn='SN-001',
        model='FBA-TOY',
    )


@pytest.mark.filterwarnings('ignore:.*`json_encoders` is deprecated.*')
def test_billing_router_exposes_open_session_only() -> None:
    app = FastAPI()
    app.include_router(v1)
    paths = app.openapi()['paths']

    assert '/api/v1/resource/billing/open_session' in paths
    assert '/api/v1/resource/billing/session' not in paths


def test_open_session_uses_authenticated_device(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    expected = SimpleNamespace(session_id='billing-session-1')

    async def fake_open_session(*, db: object, auth_did: str) -> SimpleNamespace:
        captured.update(db=db, auth_did=auth_did)
        return expected

    monkeypatch.setattr(billing_service, 'open_session', fake_open_session)

    response = asyncio.run(
        open_session(
            db='db-session',  # type: ignore[arg-type]
            auth_ctx=_device_auth(),
        )
    )

    assert captured == {'db': 'db-session', 'auth_did': 'device-1'}
    assert response.data is expected


def test_fba_token_does_not_include_billing_balance(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_payload: dict[str, object] = {}

    async def fake_get_baby(*, db: object, did: str) -> SimpleNamespace:
        assert db == 'db-session'
        assert did == 'device-1'
        return SimpleNamespace(id=7)

    def fake_jwt_encode(payload: dict[str, object]) -> str:
        captured_payload.update(payload)
        return 'encoded-token'

    monkeypatch.setattr(
        'backend.app.cloud.api.v1.terminal.auth.baby_service.get_by_device_did',
        fake_get_baby,
    )
    monkeypatch.setattr(
        'backend.app.cloud.api.v1.terminal.auth.jwt_encode',
        fake_jwt_encode,
    )

    response = asyncio.run(
        fba_token(
            db='db-session',  # type: ignore[arg-type]
            auth_ctx=_device_auth(),
        )
    )

    assert response.data.token == 'encoded-token'
    assert 'balance_token' not in captured_payload
    assert captured_payload['did'] == 'device-1'
    assert captured_payload['baby_id'] == 7
