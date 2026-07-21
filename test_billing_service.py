from __future__ import annotations

import asyncio

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from sqlalchemy.exc import IntegrityError

from backend.app.cloud.api.v1.billing import debit as debit_api
from backend.app.cloud.api.v1.billing import session as session_api
from backend.app.cloud.model.billing import BillSession, BillTxn
from backend.app.cloud.schema.billing import (
    BillCloseSessionParam,
    BillDebitUsageParam,
    BillDebitUsageResult,
    BillOpenSessionParam,
    BillOpenSessionResult,
)
from backend.app.cloud.schema.user import DeviceAuthParam
from backend.app.cloud.service import billing_service as billing_service_module
from backend.app.cloud.service.billing_service import BillingService
from backend.common.exception import errors


def _device_auth(did: str = 'did-1') -> DeviceAuthParam:
    return DeviceAuthParam(
        mac='AA:BB:CC:DD:EE:FF',
        did=did,
        sn='SN-1',
        model='Model-1',
    )


class _DummyDB:
    @asynccontextmanager
    async def begin_nested(self):
        yield


def test_open_session_returns_recovered_account_after_concurrent_session_create(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started_at = datetime.now(timezone.utc)
    created_account = SimpleNamespace(
        id=1,
        status='ACTIVE',
        balance_token=100,
    )
    recovered_account = SimpleNamespace(
        id=2,
        status='ACTIVE',
        balance_token=88,
    )
    recovered_session = SimpleNamespace(
        session_id='session-1',
        account_id=2,
        device_did='did-1',
        status='OPEN',
    )
    monkeypatch.setattr(
        billing_service_module.bill_session_dao,
        'get_by_session_id',
        AsyncMock(side_effect=[None, recovered_session]),
    )
    monkeypatch.setattr(
        billing_service_module.bill_account_dao,
        'get_by_subject_for_update',
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        billing_service_module.bill_account_dao,
        'create',
        AsyncMock(return_value=created_account),
    )
    monkeypatch.setattr(
        billing_service_module.bill_session_dao,
        'create',
        AsyncMock(side_effect=IntegrityError('insert', None, None)),
    )
    monkeypatch.setattr(
        billing_service_module.bill_account_dao,
        'get_for_update',
        AsyncMock(return_value=recovered_account),
    )

    result = asyncio.run(
        BillingService.open_session(
            db=object(),
            obj=BillOpenSessionParam(
                session_id='session-1',
                subject_type='DEVICE',
                subject_key='did-1',
                device_did='did-1',
                started_at=started_at,
            ),
            auth_did='did-1',
        )
    )

    assert result == BillOpenSessionResult(
        account_id=2,
        balance_token=88,
        account_status='ACTIVE',
        session_status='OPEN',
    )


def test_debit_usage_rejects_new_debit_when_session_already_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        BillingService,
        '_load_debit_result',
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        billing_service_module.bill_session_dao,
        'get_with_account_for_update',
        AsyncMock(
            return_value=(
                SimpleNamespace(
                    session_id='session-1',
                    device_did='did-1',
                    status='BLOCKED',
                    last_activity_at=None,
                ),
                SimpleNamespace(
                    id=1,
                    balance_token=100,
                    status='ACTIVE',
                ),
            )
        ),
    )

    with pytest.raises(errors.ConflictError):
        asyncio.run(
            BillingService.debit_usage(
                db=object(),
                obj=BillDebitUsageParam(
                    usage_id='session-1:1:TURN',
                    session_id='session-1',
                    turn_no=1,
                    usage_token=10,
                ),
                auth_did='did-1',
            )
        )


def test_debit_usage_blocks_when_balance_is_nonpositive_after_debit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    occurred_at = datetime.now(timezone.utc)
    session = SimpleNamespace(
        session_id='session-1',
        account_id=1,
        device_did='did-1',
        status='OPEN',
        last_activity_at=None,
    )
    account = SimpleNamespace(
        id=1,
        balance_token=0,
        status='ACTIVE',
    )
    txn = SimpleNamespace(
        account_id=1,
        usage_id='session-1:1:TURN',
        usage_token=0,
        balance_after_token=0,
        account_status_after='BLOCKED',
        session_status_after='BLOCKED',
        created_time=occurred_at,
    )
    monkeypatch.setattr(
        BillingService,
        '_load_debit_result',
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        billing_service_module.bill_session_dao,
        'get_with_account_for_update',
        AsyncMock(return_value=(session, account)),
    )
    monkeypatch.setattr(
        billing_service_module.bill_txn_dao,
        'create',
        AsyncMock(return_value=txn),
    )

    result = asyncio.run(
        BillingService.debit_usage(
            db=_DummyDB(),
            obj=BillDebitUsageParam(
                usage_id='session-1:1:TURN',
                session_id='session-1',
                turn_no=1,
                usage_token=0,
            ),
            auth_did='did-1',
        )
    )

    assert result == BillDebitUsageResult(
        account_id=1,
        usage_id='session-1:1:TURN',
        amount_token=0,
        balance_after_token=0,
        account_status='BLOCKED',
        session_status='BLOCKED',
        should_stop=True,
    )
    assert account.balance_token == 0
    assert account.status == 'BLOCKED'
    assert session.status == 'BLOCKED'
    assert session.last_activity_at == occurred_at


def test_close_session_param_accepts_blocked_status() -> None:
    result = BillCloseSessionParam(
        session_id='session-1',
        status='BLOCKED',
        ended_at=datetime.now(timezone.utc),
    )

    assert result.status == 'BLOCKED'


def test_billing_schemas_reject_removed_legacy_fields() -> None:
    with pytest.raises(ValidationError):
        BillOpenSessionParam(
            session_id='session-1',
            subject_type='USER',
            subject_key='user-1',
            device_did='did-1',
            started_at=datetime.now(timezone.utc),
        )

    with pytest.raises(ValidationError):
        BillDebitUsageParam(
            usage_id='session-1:1:TURN',
            session_id='session-1',
            turn_no=1,
            usage_token=5,
            stage_no=0,
            usage_kind='TTS',
            provider='azure_push',
            occurred_at=datetime.now(timezone.utc),
        )

    with pytest.raises(ValidationError):
        BillDebitUsageResult(
            account_id=7,
            usage_id='session-1:1:TURN',
            charge_id='session-1:1:TURN',
            amount_token=5,
            balance_after_token=94,
            account_status='ACTIVE',
            session_status='OPEN',
            should_stop=False,
        )


def test_usage_id_column_is_longer_than_session_id_column() -> None:
    session_id_length = BillSession.__table__.c.session_id.type.length
    usage_id_length = BillTxn.__table__.c.usage_id.type.length

    assert usage_id_length >= session_id_length + 16


def test_billing_routes_return_direct_payload_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    open_result = BillOpenSessionResult(
        account_id=7,
        balance_token=99,
        account_status='ACTIVE',
        session_status='OPEN',
    )
    debit_result = BillDebitUsageResult(
        account_id=7,
        usage_id='session-1:1:TURN',
        amount_token=5,
        balance_after_token=94,
        account_status='ACTIVE',
        session_status='OPEN',
        should_stop=False,
    )
    monkeypatch.setattr(
        session_api.billing_service,
        'open_session',
        AsyncMock(return_value=open_result),
    )
    monkeypatch.setattr(
        debit_api.billing_service,
        'debit_usage',
        AsyncMock(return_value=debit_result),
    )

    auth_ctx = _device_auth()
    open_payload = BillOpenSessionParam(
        session_id='session-1',
        subject_type='DEVICE',
        subject_key='did-1',
        device_did='did-1',
        started_at=datetime.now(timezone.utc),
    )
    debit_payload = BillDebitUsageParam(
        usage_id='session-1:1:TURN',
        session_id='session-1',
        turn_no=1,
        usage_token=5,
    )

    open_response = asyncio.run(
        session_api.open_session(
            db=object(),
            obj=open_payload,
            auth_ctx=auth_ctx,
        )
    )
    debit_response = asyncio.run(
        debit_api.debit_usage(
            db=object(),
            obj=debit_payload,
            auth_ctx=auth_ctx,
        )
    )

    assert isinstance(open_response, BillOpenSessionResult)
    assert not hasattr(open_response, 'code')
    assert isinstance(debit_response, BillDebitUsageResult)
    assert not hasattr(debit_response, 'data')
