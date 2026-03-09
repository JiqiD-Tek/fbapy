import zoneinfo

from datetime import datetime
from datetime import timezone as datetime_timezone

from backend.core.conf import settings


class TimeZone:
    def __init__(self, tz: str = settings.DATETIME_TIMEZONE) -> None:
        """Initialize timezone helper."""
        tz_name = (tz or settings.DATETIME_TIMEZONE).strip()
        # UTC should not depend on system tzdb.
        if tz_name.upper() in {'UTC', 'ETC/UTC'}:
            self.tz_info = datetime_timezone.utc
        else:
            self.tz_info = zoneinfo.ZoneInfo(tz_name)

    def now(self) -> datetime:
        return datetime.now(self.tz_info)

    def from_datetime(self, t: datetime) -> datetime:
        """
        将 datetime 对象转换为当前时区时间

        :param t: 需要转换的 datetime 对象
        :return:
        """
        return t.astimezone(self.tz_info)

    def from_str(self, t_str: str, format_str: str = settings.DATETIME_FORMAT) -> datetime:
        """
        将时间字符串转换为当前时区的 datetime 对象

        :param t_str: 时间字符串
        :param format_str: 时间格式字符串，默认为 settings.DATETIME_FORMAT
        :return:
        """
        return datetime.strptime(t_str, format_str).replace(tzinfo=self.tz_info)

    @staticmethod
    def to_str(t: datetime, format_str: str = settings.DATETIME_FORMAT) -> str:
        """
        将 datetime 对象转换为指定格式的时间字符串

        :param t: datetime 对象
        :param format_str: 时间格式字符串，默认为 settings.DATETIME_FORMAT
        :return:
        """
        return t.strftime(format_str)

    @staticmethod
    def to_utc(t: datetime | int) -> datetime:
        """
        将 datetime 对象或时间戳转换为 UTC 时区时间

        :param t: 需要转换的 datetime 对象或时间戳
        :return:
        """
        if isinstance(t, datetime):
            return t.astimezone(datetime_timezone.utc)
        return datetime.fromtimestamp(t, tz=datetime_timezone.utc)


timezone: TimeZone = TimeZone()
