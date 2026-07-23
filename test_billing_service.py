from __future__ import annotations

import asyncio

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from backend.app.cloud.api.v1.resource import xiaozhi as xiaozhi_api
from backend.app.cloud.model.billing import BillTxn
from backend.app.cloud.schema.billing import BillTurnDebitParam, BillTurnDebitResult
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


def test_debit_turn_returns_existing_result_when_blocked_account_has_existing_txn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        billing_service_module.bill_account_dao,
        'get_by_subject_for_update',
        AsyncMock(
            return_value=SimpleNamespace(
                id=1,
                balance_token=0,
                status='BLOCKED',
            )
        ),
    )
    monkeypatch.setattr(
        billing_service_module.bill_txn_dao,
        'get_by_session_sentence',
        AsyncMock(
            return_value=SimpleNamespace(
                account_id=1,
                session_id='session-1',
                sentence_id='sentence-1',
                amount_token=5,
                balance_token=95,
            )
        ),
    )

    result = asyncio.run(
        BillingService.debit_turn(
            db=_DummyDB(),
            obj=BillTurnDebitParam(
                session_id='session-1',
                sentence_id='sentence-1',
                amount_token=5,
            ),
            auth_did='did-1',
        )
    )

    assert result == BillTurnDebitResult(
        account_id=1,
        session_id='session-1',
        sentence_id='sentence-1',
        amount_token=5,
        balance_token=95,
        account_status='ACTIVE',
    )


def test_debit_turn_blocks_when_balance_is_nonpositive_after_debit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = SimpleNamespace(
        id=1,
        balance_token=5,
        status='ACTIVE',
    )
    monkeypatch.setattr(
        billing_service_module.bill_txn_dao,
        'get_by_session_sentence',
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        billing_service_module.bill_account_dao,
        'get_by_subject_for_update',
        AsyncMock(return_value=account),
    )
    monkeypatch.setattr(
        billing_service_module.bill_txn_dao,
        'create',
        AsyncMock(
            return_value=SimpleNamespace(
                account_id=1,
                session_id='session-1',
                sentence_id='sentence-1',
                amount_token=10,
                balance_token=-5,
            )
        ),
    )

    result = asyncio.run(
        BillingService.debit_turn(
            db=_DummyDB(),
            obj=BillTurnDebitParam(
                session_id='session-1',
                sentence_id='sentence-1',
                amount_token=10,
            ),
            auth_did='did-1',
        )
    )

    assert result == BillTurnDebitResult(
        account_id=1,
        session_id='session-1',
        sentence_id='sentence-1',
        amount_token=10,
        balance_token=-5,
        account_status='BLOCKED',
    )
    assert account.balance_token == -5
    assert account.status == 'BLOCKED'
    create_payload = billing_service_module.bill_txn_dao.create.await_args.kwargs['obj']
    assert create_payload['amount_token'] == 10
    assert 'usage_token' not in create_payload
    assert 'delta_token' not in create_payload


def test_debit_turn_rejects_new_debit_when_account_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        billing_service_module.bill_txn_dao,
        'get_by_session_sentence',
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        billing_service_module.bill_account_dao,
        'get_by_subject_for_update',
        AsyncMock(
            return_value=SimpleNamespace(
                id=1,
                balance_token=0,
                status='BLOCKED',
            )
        ),
    )

    with pytest.raises(errors.ForbiddenError):
        asyncio.run(
            BillingService.debit_turn(
                db=object(),
                obj=BillTurnDebitParam(
                    session_id='session-1',
                    sentence_id='sentence-2',
                    amount_token=1,
                ),
                auth_did='did-1',
            )
        )


def test_debit_turn_recovers_existing_txn_after_insert_race(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = SimpleNamespace(
        id=1,
        balance_token=100,
        status='ACTIVE',
    )
    monkeypatch.setattr(
        billing_service_module.bill_txn_dao,
        'get_by_session_sentence',
        AsyncMock(
            return_value=SimpleNamespace(
                account_id=1,
                session_id='session-1',
                sentence_id='sentence-1',
                amount_token=5,
                balance_token=95,
            ),
        ),
    )
    monkeypatch.setattr(
        billing_service_module.bill_account_dao,
        'get_by_subject_for_update',
        AsyncMock(return_value=account),
    )
    monkeypatch.setattr(
        billing_service_module.bill_txn_dao,
        'create',
        AsyncMock(side_effect=IntegrityError('insert', None, None)),
    )

    result = asyncio.run(
        BillingService.debit_turn(
            db=_DummyDB(),
            obj=BillTurnDebitParam(
                session_id='session-1',
                sentence_id='sentence-1',
                amount_token=5,
            ),
            auth_did='did-1',
        )
    )

    assert result == BillTurnDebitResult(
        account_id=1,
        session_id='session-1',
        sentence_id='sentence-1',
        amount_token=5,
        balance_token=95,
        account_status='ACTIVE',
    )
    assert account.balance_token == 100
    assert account.status == 'ACTIVE'


def test_billing_schemas_reject_removed_legacy_fields() -> None:
    with pytest.raises(ValidationError):
        BillTurnDebitParam(
            usage_id='session-1:1:TURN',
            session_id='session-1',
            sentence_id='sentence-1',
            turn_no=1,
            usage_token=5,
            amount_token=5,
        )

    with pytest.raises(ValidationError):
        BillTurnDebitResult(
            account_id=7,
            session_id='session-1',
            sentence_id='sentence-1',
            usage_token=5,
            amount_token=5,
            balance_token=95,
            balance_after_token=95,
            account_status='ACTIVE',
            account_status_after='ACTIVE',
            session_status='OPEN',
            should_stop=False,
        )


def test_txn_model_uses_sentence_id_without_status_snapshot() -> None:
    unique_constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in BillTxn.__table__.constraints
        if isinstance(constraint, sa.UniqueConstraint)
    }

    assert ('session_id', 'sentence_id') in unique_constraints
    assert 'sentence_id' in BillTxn.__table__.c
    assert 'amount_token' in BillTxn.__table__.c
    assert 'balance_token' in BillTxn.__table__.c
    assert 'usage_token' not in BillTxn.__table__.c
    assert 'delta_token' not in BillTxn.__table__.c
    assert 'balance_after_token' not in BillTxn.__table__.c
    assert 'usage_id' not in BillTxn.__table__.c
    assert 'turn_no' not in BillTxn.__table__.c
    assert 'session_status_after' not in BillTxn.__table__.c
    assert 'account_status_after' not in BillTxn.__table__.c


def test_xiaozhi_billing_route_returns_wrapped_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    debit_result = BillTurnDebitResult(
        account_id=7,
        session_id='session-1',
        sentence_id='sentence-1',
        amount_token=5,
        balance_token=95,
        account_status='ACTIVE',
    )
    monkeypatch.setattr(
        xiaozhi_api.billing_service,
        'debit_turn',
        AsyncMock(return_value=debit_result),
    )

    response = asyncio.run(
        xiaozhi_api.debit_billing_turn(
            db=object(),
            obj=BillTurnDebitParam(
                session_id='session-1',
                sentence_id='sentence-1',
                amount_token=5,
            ),
            auth_ctx=_device_auth(),
        )
    )

    assert response.data == debit_result
    assert not hasattr(response.data, 'session_status')
