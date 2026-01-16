# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：manager.py
@Author  ：guhua@jiqid.com
@Date    ：2025/06/13 10:45
"""

import asyncio
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import AsyncIterator, TypeVar, Generic, Optional

from backend.core.conf import settings
from backend.common.log import log

T = TypeVar('T')  # 客户端类型泛型: ASRClient, TTSClient, LLM


class BaseManager(ABC, Generic[T]):
    """优化后的语音服务管理器基类（支持对象池化）

    特性：
    - 线程安全的连接池管理
    - 完善的错误处理和资源回收
    - 精确的类型提示
    - 可配置的连接池参数
    """

    def __init__(self, pool_size: int = 1000):
        """
        Args:
            pool_size: 每个连接池的最大容量
        """
        self.pool_size = pool_size

        # 使用LifoQueue实现连接池（更符合连接复用的局部性原理）
        self._asr_pool = asyncio.LifoQueue(self.pool_size)
        self._tts_pool = asyncio.LifoQueue(self.pool_size)
        self._llm_pool = asyncio.LifoQueue(self.pool_size)

    @asynccontextmanager
    async def asr_session(self, uid: Optional[str] = None) -> AsyncIterator[T]:
        """ASR会话上下文管理器"""
        client = None
        try:
            client = await self.acquire_asr(uid)
            yield client
        except Exception as e:
            log.warning(f"ASR会话异常: {e}")
            raise
        finally:
            if client is not None:
                await self._safe_release_asr(client)

    @asynccontextmanager
    async def tts_session(self, uid: Optional[str] = None) -> AsyncIterator[T]:
        """TTS会话上下文管理器"""
        client = None
        try:
            client = await self.acquire_tts(uid)
            yield client
        except Exception as e:
            log.warning(f"TTS会话异常: {e}")
            raise
        finally:
            if client is not None:
                await self._safe_release_tts(client)

    async def _safe_release_asr(self, client: T):
        """安全释放ASR资源"""
        try:
            await self.release_asr(client)
        except Exception as e:
            log.warning(f"释放ASR资源失败: {e}")

    async def _safe_release_tts(self, client: T):
        """安全释放TTS资源"""
        try:
            await self.release_tts(client)
        except Exception as e:
            log.warning(f"释放TTS资源失败: {e}")

    @property
    def asr_available(self) -> int:
        """当前可用ASR连接数"""
        return self._asr_pool.qsize()

    @property
    def tts_available(self) -> int:
        """当前可用TTS连接数"""
        return self._tts_pool.qsize()

    @abstractmethod
    async def acquire_asr(self, uid: Optional[str] = None) -> T:
        """获取ASR客户端（必须实现）

        Args:
            uid: 可选的用户标识，用于特定路由
        """
        pass

    @abstractmethod
    async def release_asr(self, client: T) -> None:
        """释放ASR客户端（必须实现）"""
        pass

    @abstractmethod
    async def acquire_tts(self, uid: Optional[str] = None, encoding: str = settings.SPEECH_ENCODING) -> T:
        """获取TTS客户端（必须实现）"""
        pass

    @abstractmethod
    async def release_tts(self, client: T) -> None:
        """释放TTS客户端（必须实现）"""
        pass

    @staticmethod
    async def _force_close(client: T, reason: str = "无") -> None:
        """强制关闭客户端"""
        try:
            await client.close()
            log.debug(f"OpenAI客户端已正常关闭：{reason}")
        except Exception as e:
            log.error(f"OpenAI客户端关闭异常: {e}")
