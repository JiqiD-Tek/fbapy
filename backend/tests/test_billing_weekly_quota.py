import asyncio

from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace

import pytest

from backend.app.cloud.schema.billing import CreditUsageType
from backend.app.cloud.service.billing_service import BillingService
from backend.utils.timezone import timezone


class _Session:
    @asynccontextmanager
    async def begin_nested(self):  # noqa: ANN201
        yield


def _account(
        *,
        balance_credits: int = 1000,
        weekly_credits_quota: int | None = 500,
        weekly_credits_usage: int = 0,
        weekly_reset_at: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        balance_credits=balance_credits,
        weekly_credits_quota=weekly_credits_quota,
        weekly_credits_usage=weekly_credits_usage,
        weekly_reset_at=weekly_reset_at,
        status='ACTIVE',
    )


def test_get_weekly_reset_at_uses_next_monday() -> None:
    now = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.tz_info)

    reset_at = BillingService._get_weekly_reset_at(now)

    assert reset_at == datetime(2026, 10, 5, 0, 0, tzinfo=timezone.tz_info)


def test_sync_weekly_period_resets_expired_usage() -> None:
    now = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.tz_info)
    account = _account(
        weekly_credits_usage=300,
        weekly_reset_at=datetime(2026, 9, 29, 0, 0, tzinfo=timezone.tz_info),
    )

    reset_at = BillingService._sync_weekly_period(
        account=account,
        now=now,
    )

    assert reset_at == datetime(2026, 10, 5, 0, 0, tzinfo=timezone.tz_info)
    assert account.weekly_reset_at == datetime(2026, 10, 5, 0, 0, tzinfo=timezone.tz_info)
    assert account.weekly_credits_usage == 0


def test_weekly_remaining_is_none_when_quota_is_unlimited() -> None:
    account = _account(weekly_credits_quota=None, weekly_credits_usage=300)

    assert BillingService._weekly_credits_remaining(account) is None


def test_debit_updates_weekly_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    account = _account(
        weekly_credits_usage=100,
        weekly_reset_at=datetime(2026, 10, 5, 0, 0, tzinfo=timezone.tz_info),
    )
    txn = SimpleNamespace(
        account_id=1,
        session_id='session-1',
        sentence_id='sentence-1',
        amount_credits=300,
        balance_credits=1000,
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
        quantity=100,
        usage_type=CreditUsageType.TTS_CHARACTERS,
        session_id='session-1',
        sentence_id='sentence-1',
    ))

    assert account.balance_credits == 1000
    assert account.weekly_credits_usage == 400
    assert result.weekly_credits_quota == 500
    assert result.weekly_credits_usage == 400
    assert result.weekly_credits_remaining == 100


def test_debit_uses_balance_after_weekly_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    account = _account(
        weekly_credits_usage=450,
        weekly_reset_at=datetime(2026, 10, 5, 0, 0, tzinfo=timezone.tz_info),
    )
    txn = SimpleNamespace(
        account_id=1,
        session_id='session-1',
        sentence_id='sentence-1',
        amount_credits=300,
        balance_credits=750,
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
        quantity=100,
        usage_type=CreditUsageType.TTS_CHARACTERS,
        session_id='session-1',
        sentence_id='sentence-1',
    ))

    assert account.balance_credits == 750
    assert account.weekly_credits_usage == 500
    assert result.weekly_credits_remaining == 0


def test_debit_allows_negative_balance_when_gift_and_balance_are_insufficient(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = _account(
        balance_credits=40,
        weekly_credits_usage=450,
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

    txn = SimpleNamespace(
        account_id=1,
        session_id='session-1',
        sentence_id='sentence-1',
        amount_credits=300,
        balance_credits=0,
    )

    async def create_txn(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        return txn

    monkeypatch.setattr('backend.app.cloud.service.billing_service.bill_txn_dao.create', create_txn)

    result = asyncio.run(BillingService.debit(
        db=_Session(),  # type: ignore[arg-type]
        auth_did='device-1',
        biz_type='CHAT',
        biz_id='session-1:sentence-1',
        quantity=100,
        usage_type=CreditUsageType.TTS_CHARACTERS,
        session_id='session-1',
        sentence_id='sentence-1',
    ))

    assert result.balance_credits == 0
    assert account.balance_credits == 0
    assert account.weekly_credits_usage == 710
    assert result.weekly_credits_remaining == -210
