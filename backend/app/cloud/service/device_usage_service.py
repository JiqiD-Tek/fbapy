from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.crud_device_usage import device_usage_dao, device_usage_event_dao
from backend.app.cloud.model import DeviceUsage
from backend.common.exception import errors
from backend.core.conf import settings
from backend.utils.timezone import timezone

USAGE_CHAT = 'CHAT'
USAGE_STORY = 'STORY'


class UsageCalculator:
    """将原始用量换算为整数单位：1 元成本对应 100 万单位。"""

    # 识别 0.07 元/分钟，模型 0.003 元/千字符，合成 0.3 元/千字符。
    ASR_UNITS_PER_MINUTE = 70_000
    LLM_UNITS_PER_CHARACTER = 3
    TTS_UNITS_PER_CHARACTER = 300

    @classmethod
    def calculate_quantity(cls, *, asr_characters: int, tts_characters: int) -> int:
        """CHAT、STORY 共用算法；识别时长根据识别字符数和语速估算。"""
        if asr_characters < 0:
            raise ValueError('语音识别字符数不能为负数')
        if tts_characters < 0:
            raise ValueError('语音合成字符数不能为负数')
        characters_per_minute = settings.ASR_CHARACTERS_PER_MINUTE
        text_units = (
            (asr_characters + tts_characters) * cls.LLM_UNITS_PER_CHARACTER
            + tts_characters * cls.TTS_UNITS_PER_CHARACTER
        )
        # 统一分母后仅向上取整一次，全程整数运算。
        numerator = asr_characters * cls.ASR_UNITS_PER_MINUTE + text_units * characters_per_minute
        return (numerator + characters_per_minute - 1) // characters_per_minute


class DeviceUsageService:
    @staticmethod
    async def get_daily_usage(
            *, db: AsyncSession, did: str, usage_date: date | None = None,
    ) -> DeviceUsage | None:
        return await device_usage_dao.get(db, did=did, usage_date=usage_date or timezone.now().date())

    @staticmethod
    def build_quota_result(*, did: str, usage_date: date, usage: DeviceUsage | None) -> dict[str, object]:
        quantity = int(usage.quantity if usage is not None else 0)
        daily_quota = settings.DEVICE_DAILY_AI_QUOTA
        return {
            'did': did,
            'usage_date': usage_date,
            'daily_quota': daily_quota,
            'quantity': quantity,
            'remaining_quantity': max(daily_quota - quantity, 0) if daily_quota is not None else None,
        }

    @staticmethod
    async def ensure_quota_available(*, db: AsyncSession, did: str) -> None:
        usage = await DeviceUsageService.get_daily_usage(db=db, did=did)
        quota = settings.DEVICE_DAILY_AI_QUOTA
        if quota is not None and (usage.quantity if usage else 0) >= quota:
            raise errors.RequestError(msg='当日 AI 使用额度已用完')

    @staticmethod
    async def record_usage(
            *, db: AsyncSession, did: str, event_type: str, event_key: str,
            asr_characters: int, tts_characters: int,
            usage_date: date | None = None,
    ) -> bool:
        return await DeviceUsageService._record(
            db=db,
            did=did,
            event_type=event_type,
            event_key=event_key,
            quantity=UsageCalculator.calculate_quantity(
                asr_characters=asr_characters, tts_characters=tts_characters,
            ),
            usage_date=usage_date,
        )

    @staticmethod
    async def _record(
            *, db: AsyncSession, did: str, event_type: str, event_key: str,
            quantity: int, usage_date: date | None,
    ) -> bool:
        did = did.strip()
        event_key = event_key.strip()
        if not did:
            raise ValueError('设备 DID 不能为空')
        if not event_key:
            raise ValueError('事件标识不能为空')
        if event_type not in {USAGE_CHAT, USAGE_STORY}:
            raise ValueError(f'不支持的使用事件类型: {event_type}')
        if quantity < 0:
            raise ValueError('使用量不能为负数')
        usage_date = usage_date or timezone.now().date()
        # 唯一约束和保存点保证并发重试只记录一次，不回滚调用方的外层事务。
        try:
            async with db.begin_nested():
                event = device_usage_event_dao.model(
                    did=did,
                    event_type=event_type,
                    event_key=event_key,
                    usage_date=usage_date,
                    quantity=quantity,
                )
                db.add(event)
                await db.flush()
        except IntegrityError:
            if await device_usage_event_dao.get_by_business(
                    db, event_type=event_type, event_key=event_key,
            ) is not None:
                return False
            raise

        usage = await device_usage_dao.get(db, did=did, usage_date=usage_date)
        if usage is None:
            try:
                async with db.begin_nested():
                    usage = DeviceUsage(did=did, usage_date=usage_date)
                    db.add(usage)
                    await db.flush()
            except IntegrityError:
                usage = await device_usage_dao.get_for_update(db, did=did, usage_date=usage_date)
                if usage is None:
                    raise
        usage = await device_usage_dao.get_for_update(db, did=did, usage_date=usage_date)
        assert usage is not None
        # 已完成的消耗如实记账；额度耗尽后由调用方停止新请求，不能丢弃超出部分。
        usage.quantity += quantity
        await db.flush()
        return True


device_usage_service = DeviceUsageService()
