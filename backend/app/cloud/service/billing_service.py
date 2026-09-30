# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : billing_service.py
@Author  : guhua@jiqid.com
@Date    : 2026/07/01
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_CEILING
from typing import TYPE_CHECKING, ClassVar, cast
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from backend.app.cloud.crud.crud_billing import bill_account_dao, bill_txn_dao
from backend.app.cloud.schema.billing import (
    BillAccountStatus,
    CreditUsageType,
    BillingAccountQuotaResult,
    BillingSessionResult,
    BillTurnDebitResult,
)
from backend.common.exception import errors
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.app.cloud.model.billing import BillAccount, BillTxn

ACCOUNT_SUBJECT_DEVICE = 'DEVICE'
ACCOUNT_ACTIVE = 'ACTIVE'
BILL_BIZ_CHAT = 'CHAT'
BILL_BIZ_STORY = 'STORY'
CHANGE_DEBIT = 'DEBIT'
LEGACY_USAGE_TYPE = 'legacy'


class CreditCalculator:
    """集中定义计费单价，并将各类用量换算为整数积分。"""

    # 1 积分 = 0.0000001 元，10 元 = 1 亿积分。
    CREDITS_PER_YUAN = 10_000_000

    # 模型和语音服务单价。
    LLM_INPUT_CREDITS_PER_1K_TOKENS = 3
    LLM_OUTPUT_CREDITS_PER_1K_TOKENS = 30
    TTS_CREDITS_PER_CHAR = 3
    ASR_CREDITS_PER_HOUR = 45_000_000

    @classmethod
    def yuan_to_credits(cls, amount_yuan: Decimal | int | str) -> int:
        """将人民币金额换算为积分，非整数积分向上取整。"""
        amount = Decimal(str(amount_yuan))
        if amount < 0:
            raise ValueError('金额不能为负数')
        return int((amount * cls.CREDITS_PER_YUAN).to_integral_value(rounding=ROUND_CEILING))

    @classmethod
    def credits_to_yuan(cls, credits: int) -> Decimal:
        """将积分换算为人民币金额。"""
        if credits < 0:
            raise ValueError('积分不能为负数')
        return (Decimal(credits) / cls.CREDITS_PER_YUAN).quantize(Decimal('0.0000001'))

    @staticmethod
    def _per_thousand(units: int, credits_per_1k: int) -> int:
        if units < 0:
            raise ValueError('用量不能为负数')
        if credits_per_1k < 0:
            raise ValueError('单价不能为负数')
        return (units * credits_per_1k + 999) // 1000

    @classmethod
    def llm_input(cls, tokens: int) -> int:
        """按 llm 输入 tokens 换算积分。"""
        return cls._per_thousand(tokens, cls.LLM_INPUT_CREDITS_PER_1K_TOKENS)

    @classmethod
    def llm_output(cls, tokens: int) -> int:
        """按 llm 输出 tokens 换算积分。"""
        return cls._per_thousand(tokens, cls.LLM_OUTPUT_CREDITS_PER_1K_TOKENS)

    @classmethod
    def tts(cls, characters: int) -> int:
        """按语音合成字符数换算积分。"""
        if characters < 0:
            raise ValueError('字符数不能为负数')
        return characters * cls.TTS_CREDITS_PER_CHAR

    @classmethod
    def asr(cls, seconds: Decimal | int | float | str) -> int:
        """按语音识别秒数换算积分，不足一积分向上取整。"""
        duration = Decimal(str(seconds))
        if duration < 0:
            raise ValueError('时长不能为负数')
        credits = duration * cls.ASR_CREDITS_PER_HOUR / 3600
        return int(credits.to_integral_value(rounding=ROUND_CEILING))

    @classmethod
    def calculate(cls, *, usage_type: CreditUsageType, quantity: Decimal | int | float | str) -> int:
        """按原始用量类型统一换算积分。"""
        if usage_type == CreditUsageType.ASR_SECONDS:
            return cls.asr(quantity)

        value = Decimal(str(quantity))
        if value < 0 or value != value.to_integral_value():
            raise ValueError('当前用量类型必须使用非负整数')
        count = int(value)
        if usage_type == CreditUsageType.LLM_INPUT_TOKENS:
            return cls.llm_input(count)
        if usage_type == CreditUsageType.LLM_OUTPUT_TOKENS:
            return cls.llm_output(count)
        if usage_type == CreditUsageType.TTS_CHARACTERS:
            return cls.tts(count)
        raise ValueError(f'不支持的计费用量类型：{usage_type}')


class BillingService:
    """计费服务。"""

    # 新账户默认积分额度。
    DEFAULT_BALANCE_CREDITS: ClassVar[int] = CreditCalculator.CREDITS_PER_YUAN * 0
    DEFAULT_WEEKLY_CREDITS_QUOTA: ClassVar[int] = CreditCalculator.CREDITS_PER_YUAN * 10

    # 公开接口。
    @classmethod
    async def open_session(cls, *, db: AsyncSession, auth_did: str) -> BillingSessionResult:
        """创建终端计费会话，并返回当前额度快照。"""
        account = await cls.get_or_create_device_account(db=db, did=auth_did)
        now = timezone.now()
        weekly_reset_at = cls._sync_weekly_period(account=account, now=now)
        weekly_remaining = cls._weekly_credits_remaining(account)
        available_credits = None if weekly_remaining is None else weekly_remaining + account.balance_credits
        return BillingSessionResult(
            session_id=uuid4().hex,
            account_id=account.id,
            account_status=cls._get_account_status(account.status),
            balance_credits=account.balance_credits,
            weekly_credits_quota=account.weekly_credits_quota,
            weekly_credits_usage=account.weekly_credits_usage,
            weekly_credits_remaining=weekly_remaining,
            available_credits=available_credits,
            weekly_reset_at=weekly_reset_at,
        )

    @classmethod
    async def get_device_account_quota(
            cls,
            *,
            db: AsyncSession,
            device_did: str,
    ) -> BillingAccountQuotaResult:
        """查询设备额度，账户不存在时初始化默认账户。"""
        account = await cls.get_or_create_device_account(db=db, did=device_did)

        now = timezone.now()
        reset_at = cls._sync_weekly_period(account=account, now=now)
        weekly_remaining = cls._weekly_credits_remaining(account)
        available_credits = None if weekly_remaining is None else weekly_remaining + account.balance_credits
        return BillingAccountQuotaResult(
            device_did=device_did,
            account_id=account.id,
            account_status=cls._get_account_status(account.status),
            balance_credits=account.balance_credits,
            weekly_credits_quota=account.weekly_credits_quota,
            weekly_credits_usage=account.weekly_credits_usage,
            weekly_credits_remaining=weekly_remaining,
            available_credits=available_credits,
            weekly_reset_at=reset_at,
        )

    @classmethod
    async def debit(
            cls,
            *,
            db: AsyncSession,
            auth_did: str,
            biz_type: str,
            biz_id: str,
            quantity: Decimal | int | float | str,
            usage_type: CreditUsageType,
            session_id: str | None = None,
            sentence_id: str | None = None,
    ) -> BillTurnDebitResult:
        """按业务幂等标识扣费，聊天和故事任务共用同一套额度逻辑。"""
        try:
            amount_credits = CreditCalculator.calculate(usage_type=usage_type, quantity=quantity)
        except ValueError as exc:
            raise errors.RequestError(msg=f'计费用量无效：{exc}') from exc
        if amount_credits <= 0:
            raise errors.RequestError(msg='计费积分必须大于 0')

        session_id = session_id or f'{biz_type.lower()}:{biz_id}'
        sentence_id = sentence_id or 'submit'
        account = await cls.get_or_create_device_account(db=db, did=auth_did)
        now = timezone.now()
        weekly_reset_at = cls._sync_weekly_period(account=account, now=now)

        current = await cls._load_debit_result(
            db=db,
            account=account,
            biz_type=biz_type,
            biz_id=biz_id,
            usage_type=usage_type.value,
            weekly_reset_at=weekly_reset_at,
        )
        if current is not None:
            return current

        if account.status != ACCOUNT_ACTIVE:
            raise errors.ForbiddenError(msg='计费账户不可用')

        weekly_credits_amount, balance_credits_amount = cls._allocate_credits(
            account=account,
            amount_credits=amount_credits,
        )
        balance_credits = max(account.balance_credits - balance_credits_amount, 0)
        txn_obj = {
            'account_id': account.id,
            'biz_type': biz_type,
            'biz_id': biz_id,
            'usage_type': usage_type.value,
            'session_id': session_id,
            'sentence_id': sentence_id,
            'amount_credits': amount_credits,
            'balance_credits': balance_credits,
            'change_type': CHANGE_DEBIT,
        }

        try:
            async with db.begin_nested():
                txn = await bill_txn_dao.create(db, obj=txn_obj)
        except IntegrityError:
            current = await cls._load_debit_result(
                db=db,
                account=account,
                biz_type=biz_type,
                biz_id=biz_id,
                usage_type=usage_type.value,
                weekly_reset_at=weekly_reset_at,
            )
            if current is not None:
                return current
            raise

        account.balance_credits = balance_credits
        account.weekly_credits_usage += weekly_credits_amount
        return cls._build_debit_result(
            txn=txn,
            account=account,
            weekly_reset_at=weekly_reset_at,
        )

    @classmethod
    async def get_or_create_device_account(cls, *, db: AsyncSession, did: str) -> BillAccount:
        account = await bill_account_dao.get_by_subject_for_update(
            db,
            subject_type=ACCOUNT_SUBJECT_DEVICE,
            subject_key=did,
        )
        if account is not None:
            return account

        try:
            async with db.begin_nested():
                account = await bill_account_dao.create(
                    db,
                    subject_type=ACCOUNT_SUBJECT_DEVICE,
                    subject_key=did,
                    balance_credits=cls.DEFAULT_BALANCE_CREDITS,
                    weekly_credits_quota=cls.DEFAULT_WEEKLY_CREDITS_QUOTA,
                    weekly_reset_at=cls._get_weekly_reset_at(),
                    status=ACCOUNT_ACTIVE,
                )
        except IntegrityError:
            account = await bill_account_dao.get_by_subject_for_update(
                db,
                subject_type=ACCOUNT_SUBJECT_DEVICE,
                subject_key=did,
            )
        if account is None:
            raise errors.ServerError(msg='创建计费账户失败')
        return account

    # 账户流水与幂等查询。

    @classmethod
    async def _load_debit_result(
            cls,
            *,
            db: AsyncSession,
            account: BillAccount,
            biz_type: str,
            biz_id: str,
            usage_type: str,
            weekly_reset_at: datetime,
    ) -> BillTurnDebitResult | None:
        txn = await bill_txn_dao.get_by_business(
            db,
            biz_type=biz_type,
            biz_id=biz_id,
            usage_type=usage_type,
        )
        if txn is None:
            # 迁移前的流水无法判断原始用量类型，重试时优先避免重复扣费。
            txn = await bill_txn_dao.get_by_business(
                db,
                biz_type=biz_type,
                biz_id=biz_id,
                usage_type=LEGACY_USAGE_TYPE,
            )
        if txn is None:
            return None
        if txn.account_id != account.id:
            raise errors.ConflictError(msg='扣费幂等标识已被其他账户使用')
        return cls._build_debit_result(
            txn=txn,
            account=account,
            weekly_reset_at=weekly_reset_at,
        )

    # 周期、额度和扣费分配。

    @staticmethod
    def _get_weekly_reset_at(now: datetime | None = None) -> datetime:
        now = now or timezone.now()
        local_now = timezone.from_datetime(now)
        weekly_period_start = local_now.date() - timedelta(days=local_now.weekday())
        next_period_start = weekly_period_start + timedelta(days=7)
        return datetime.combine(next_period_start, time.min, tzinfo=timezone.tz_info)

    @classmethod
    def _sync_weekly_period(cls, *, account: BillAccount, now: datetime) -> datetime:
        reset_at = account.weekly_reset_at
        if reset_at is not None and now < reset_at:
            return reset_at

        reset_at = cls._get_weekly_reset_at(now)
        account.weekly_reset_at = reset_at
        account.weekly_credits_usage = 0
        return reset_at

    @staticmethod
    def _weekly_credits_remaining(account: BillAccount) -> int | None:
        quota = account.weekly_credits_quota
        return None if quota is None else quota - account.weekly_credits_usage

    @staticmethod
    def _get_account_status(status: str) -> BillAccountStatus:
        if status not in ('ACTIVE', 'BLOCKED'):
            raise errors.ServerError(msg=f'计费账户状态无效：{status}')
        return cast(BillAccountStatus, status)

    @classmethod
    def _allocate_credits(
            cls,
            *,
            account: BillAccount,
            amount_credits: int,
    ) -> tuple[int, int]:
        """按周赠送额度、充值余额、周额度透支的顺序分配本次用量。"""
        weekly_remaining = cls._weekly_credits_remaining(account)
        if weekly_remaining is None:
            return amount_credits, 0

        weekly_free_amount = min(amount_credits, max(weekly_remaining, 0))
        balance_credits_amount = min(
            amount_credits - weekly_free_amount,
            max(account.balance_credits, 0),
        )
        weekly_credits_amount = amount_credits - balance_credits_amount
        return weekly_credits_amount, balance_credits_amount

    @classmethod
    def _build_debit_result(
            cls,
            *,
            txn: BillTxn,
            account: BillAccount,
            weekly_reset_at: datetime,
    ) -> BillTurnDebitResult:
        return BillTurnDebitResult(
            account_id=txn.account_id,
            session_id=txn.session_id,
            sentence_id=txn.sentence_id,
            amount_credits=txn.amount_credits,
            balance_credits=txn.balance_credits,
            account_status=cls._get_account_status(account.status),
            weekly_credits_quota=account.weekly_credits_quota,
            weekly_credits_usage=account.weekly_credits_usage,
            weekly_credits_remaining=cls._weekly_credits_remaining(account),
            weekly_reset_at=weekly_reset_at,
        )


billing_service: BillingService = BillingService()
