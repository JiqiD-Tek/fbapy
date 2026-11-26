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


class DeviceUsageService:
    @staticmethod
    async def get_daily_usage(
            *, db: AsyncSession, did: str, usage_date: date | None = None,
    ) -> DeviceUsage | None:
        return await device_usage_dao.get(db, did=did, usage_date=usage_date or timezone.now().date())

    @staticmethod
    def build_quota_result(*, did: str, usage_date: date, usage: DeviceUsage | None) -> dict[str, object]:
        chat_seconds = int(usage.chat_seconds if usage is not None else 0)
        story_count = int(usage.story_count if usage is not None else 0)
        chat_limit = settings.DEVICE_USAGE_DAILY_CHAT_SECONDS_LIMIT
        story_limit = settings.DEVICE_USAGE_DAILY_STORY_COUNT_LIMIT
        return {
            'did': did,
            'usage_date': usage_date,
            'chat_seconds': chat_seconds,
            'story_count': story_count,
            'chat_seconds_remaining': max(chat_limit - chat_seconds, 0) if chat_limit is not None else None,
            'story_count_remaining': max(story_limit - story_count, 0) if story_limit is not None else None,
        }

    @staticmethod
    async def record_usage(
            *, db: AsyncSession, did: str, event_type: str, event_key: str, quantity: int,
            usage_date: date | None = None,
    ) -> bool:
        return await DeviceUsageService._record(
            db=db, did=did, event_type=event_type, event_key=event_key,
            quantity=quantity, usage_date=usage_date,
        )

    @staticmethod
    async def record_chat(
            *, db: AsyncSession, did: str, event_key: str, duration_seconds: int,
            usage_date: date | None = None,
    ) -> bool:
        return await DeviceUsageService._record(
            db=db,
            did=did,
            event_type=USAGE_CHAT,
            event_key=event_key,
            quantity=duration_seconds,
            usage_date=usage_date,
        )

    @staticmethod
    async def record_story(
            *, db: AsyncSession, did: str, event_key: str, usage_date: date | None = None,
    ) -> bool:
        return await DeviceUsageService._record(
            db=db,
            did=did,
            event_type=USAGE_STORY,
            event_key=event_key,
            quantity=1,
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
        if await device_usage_event_dao.get_by_business(
                db, event_type=event_type, event_key=event_key,
        ) is not None:
            return False

        # 预查询用于减少普通重复请求的写入；唯一约束和保存点负责并发请求下的幂等。
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

        usage = await device_usage_dao.get_for_update(db, did=did, usage_date=usage_date)
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

        if event_type == USAGE_CHAT:
            limit = settings.DEVICE_USAGE_DAILY_CHAT_SECONDS_LIMIT
            current = int(usage.chat_seconds)
        else:
            limit = settings.DEVICE_USAGE_DAILY_STORY_COUNT_LIMIT
            current = int(usage.story_count)
        if limit is not None and current + quantity > limit:
            raise errors.RequestError(msg=f'{event_type} 使用量超过当日额度')

        if event_type == USAGE_CHAT:
            usage.chat_seconds += quantity
        else:
            usage.story_count += quantity
        return True


device_usage_service = DeviceUsageService()
