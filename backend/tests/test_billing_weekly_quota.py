import asyncio

from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace

import pytest

from backend.app.cloud.service.billing_service import BillingService
from backend.common.exception import errors
from backend.utils.timezone import timezone


class _Session:
    @asynccontextmanager
    async def begin_nested(self):  # noqa: ANN201
        yield


def _account(
        *,
        balance_token: int = 1000,
        weekly_token_quota: int | None = 500,
        weekly_token_usage: int = 0,
        weekly_reset_at: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        balance_token=balance_token,
        weekly_token_quota=weekly_token_quota,
        weekly_token_usage=weekly_token_usage,
        weekly_reset_at=weekly_reset_at,
        status='ACTIVE',
    )


def test_get_weekly_reset_at_uses_next_monday() -> None:
    now = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.tz_info)

    reset_at = BillingService._get_weekly_reset_at(now)

    assert reset_at == datetime(2026, 10, 5, 0, 0, tzinfo=timezone.tz_info)


def test_reset_weekly_usage_only_when_period_changes() -> None:
    now = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.tz_info)
    account = _account(
        weekly_token_usage=300,
        weekly_reset_at=datetime(2026, 9, 29, 0, 0, tzinfo=timezone.tz_info),
    )

    BillingService._reset_weekly_usage(
        account=account,
        now=now,
        next_reset_at=datetime(2026, 10, 5, 0, 0, tzinfo=timezone.tz_info),
    )

    assert account.weekly_reset_at == datetime(2026, 10, 5, 0, 0, tzinfo=timezone.tz_info)
    assert account.weekly_token_usage == 0


def test_weekly_remaining_is_none_when_quota_is_unlimited() -> None:
    account = _account(weekly_token_quota=None, weekly_token_usage=300)

    assert BillingService._weekly_token_remaining(account) is None


def test_debit_updates_weekly_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    account = _account(
        weekly_token_usage=100,
        weekly_reset_at=datetime(2026, 10, 5, 0, 0, tzinfo=timezone.tz_info),
    )
    txn = SimpleNamespace(
        account_id=1,
        session_id='session-1',
        sentence_id='sentence-1',
        amount_token=200,
        balance_token=1000,
    )

    async def get_account(**kwargs):  # noqa: ANN003, ANN202
        return account

    async def get_txn(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        return None

    async def create_txn(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        return txn

    monkeypatch.setattr(BillingService, 'get_or_create_device_account', get_account)
    monkeypatch.setattr('backend.app.cloud.service.billing_service.bill_txn_dao.get_by_business', get_txn)
    monkeypatch.setattr('backend.app.cloud.service.billing_service.bill_txn_dao.create', create_txn)
    monkeypatch.setattr(
        'backend.app.cloud.service.billing_service.timezone.now',
        lambda: datetime(2026, 9, 30, 12, 0, tzinfo=timezone.tz_info),
    )

    result = asyncio.run(BillingService.debit(
        db=_Session(),  # type: ignore[arg-type]
        auth_did='device-1',
        biz_type='CHAT',
        biz_id='session-1:sentence-1',
        amount_token=200,
        session_id='session-1',
        sentence_id='sentence-1',
    ))

    assert account.balance_token == 1000
    assert account.weekly_token_usage == 300
    assert result.weekly_token_quota == 500
    assert result.weekly_token_usage == 300
    assert result.weekly_token_remaining == 200


def test_debit_uses_balance_after_weekly_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    account = _account(
        weekly_token_usage=450,
        weekly_reset_at=datetime(2026, 10, 5, 0, 0, tzinfo=timezone.tz_info),
    )
    txn = SimpleNamespace(
        account_id=1,
        session_id='session-1',
        sentence_id='sentence-1',
        amount_token=100,
        balance_token=950,
    )

    async def get_account(**kwargs):  # noqa: ANN003, ANN202
        return account

    async def get_txn(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        return None

    async def create_txn(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        return txn

    monkeypatch.setattr(BillingService, 'get_or_create_device_account', get_account)
    monkeypatch.setattr('backend.app.cloud.service.billing_service.bill_txn_dao.get_by_business', get_txn)
    monkeypatch.setattr('backend.app.cloud.service.billing_service.bill_txn_dao.create', create_txn)
    monkeypatch.setattr(
        'backend.app.cloud.service.billing_service.timezone.now',
        lambda: datetime(2026, 9, 30, 12, 0, tzinfo=timezone.tz_info),
    )

    result = asyncio.run(BillingService.debit(
        db=_Session(),  # type: ignore[arg-type]
        auth_did='device-1',
        biz_type='CHAT',
        biz_id='session-1:sentence-1',
        amount_token=100,
        session_id='session-1',
        sentence_id='sentence-1',
    ))

    assert account.balance_token == 950
    assert account.weekly_token_usage == 500
    assert result.weekly_token_remaining == 0


def test_debit_rejects_when_gift_and_balance_are_insufficient(monkeypatch: pytest.MonkeyPatch) -> None:
    account = _account(
        balance_token=40,
        weekly_token_usage=450,
        weekly_reset_at=datetime(2026, 10, 5, 0, 0, tzinfo=timezone.tz_info),
    )

    async def get_account(**kwargs):  # noqa: ANN003, ANN202
        return account

    async def get_txn(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        return None

    monkeypatch.setattr(BillingService, 'get_or_create_device_account', get_account)
    monkeypatch.setattr('backend.app.cloud.service.billing_service.bill_txn_dao.get_by_business', get_txn)
    monkeypatch.setattr(
        'backend.app.cloud.service.billing_service.timezone.now',
        lambda: datetime(2026, 9, 30, 12, 0, tzinfo=timezone.tz_info),
    )

    with pytest.raises(errors.CustomError, match='可用额度不足'):
        asyncio.run(BillingService.debit(
            db=_Session(),  # type: ignore[arg-type]
            auth_did='device-1',
            biz_type='CHAT',
            biz_id='session-1:sentence-1',
            amount_token=100,
            session_id='session-1',
            sentence_id='sentence-1',
        ))

    assert account.balance_token == 40
    assert account.weekly_token_usage == 450
