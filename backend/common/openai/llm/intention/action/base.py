# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：base.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/29 10:32
"""
import abc
import time
from functools import wraps
from typing import TypeVar, Callable, Any, Optional, Dict, Literal, List
from dataclasses import dataclass, field

from backend.common.log import log
from backend.common.device.repository import DeviceStateRepository

from backend.core.conf import settings
from backend.utils.timezone import timezone

T = TypeVar('T')
FuncType = Callable[..., T]


def timed_execute(threshold_ms: float = 1000.0) -> Callable[[FuncType[T]], FuncType[T]]:
    """带性能阈值的耗时统计装饰器

    Args:
        threshold_ms: 警告阈值(毫秒)，超过此值会记录warning日志

    Returns:
        装饰器函数
    """

    def decorator(func: FuncType[T]) -> FuncType[T]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                instance = args[0] if args else None
                action_name = getattr(instance, 'name', func.__name__)
                input_text = kwargs.get('text', '')[:20]  # 显示前20个字符

                log_msg = (
                    f"第三方API工具执行统计 - 工具: {action_name}, "
                    f"输入: '{input_text}...', "
                    f"耗时: {elapsed_ms:.2f}ms"
                )

                if elapsed_ms > threshold_ms:
                    log.warning(f"{log_msg} (超过阈值 {threshold_ms}ms)")
                else:
                    log.debug(log_msg)

        return async_wrapper

    return decorator


@dataclass(frozen=True)
class ActionResult:
    """ 意图结果 """
    user_prompt: Optional[str] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)


class Action(abc.ABC):
    """工具抽象基类

    所有具体工具类应继承此类并实现process方法
    """

    name: str = ""

    @property
    def en_formatted_date(self) -> str:
        """英文 获取格式化的当前日期字符串"""
        weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        months = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]

        now = timezone.now()
        return f"""
            Timezone: {settings.DATETIME_TIMEZONE}
            Date: {weekdays[now.weekday()]}, {months[now.month - 1]} {now.day}, {now.year}
            Time: {now.strftime('%H:%M:%S')}
            Week: {now.isocalendar()[1]}
        """

    @property
    def system_prompt(self) -> str:
        """获取系统提示模板

        Returns:
            多行字符串形式的系统提示
        """
        return """"""

    @abc.abstractmethod
    @timed_execute(threshold_ms=1000)
    async def process(
            self, text: str, content: str,
            conversation_history: Optional[List[Dict[Literal["user", "assistant"], str]]] = None,
            device_repo: DeviceStateRepository = None,
            **kwargs
    ) -> ActionResult:
        """执行工具的主要方法

        Args:
            text: 用户原始输入文本
            content: 经过意图识别处理的文本内容
            conversation_history: 对话历史
            device_repo: 设备状态

        Returns:
            处理结果
        """
        raise NotImplementedError
