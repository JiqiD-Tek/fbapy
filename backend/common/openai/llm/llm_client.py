#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Project : jiqid-py
@File    : llm_client.py
@Author  : guhua@jiqid.com
@Created : 2025/05/20 10:49
"""

import asyncio
import traceback

from typing import AsyncGenerator, Callable, Any, Optional, Set, Tuple

from backend.common.openai.llm.intention.recognizer.base import Intention
from backend.core.conf import settings

from backend.common.log import log
from backend.common.openai.llm.cache.memory import MemoryCache
from backend.common.openai.llm.intention import recognizer
from backend.common.openai.llm.models import llm

from backend.common.device.repository import DeviceStateRepository


class LLMClient:
    """大模型服务的高并发客户端(意图识别、内容生成)

    特性：
    - 线程安全的异步请求管理
    - 动态流式处理器跟踪
    """

    def __init__(self, uid: str = ""):
        """ 初始化大模型服务客户端 """
        if not isinstance(uid, str):
            raise ValueError("UID必须为字符串")

        self._uid = uid
        self._cache = MemoryCache(max_size=3)
        self._access_lock = asyncio.Lock()
        self._active_processors: Set['StreamProcessor'] = set()
        self._recognizer = recognizer
        self._llm = llm

    async def set_uid(self, uid: str):
        if not isinstance(uid, str) or not uid:
            raise ValueError("UID必须为非空字符串")
        async with self._access_lock:
            self._uid = uid
            log.debug(f"设置UID成功-{uid}")

    @property
    def cache(self) -> MemoryCache:
        """获取聊天缓存实例。"""
        return self._cache

    async def query_intention(self, text: str, device_repo: DeviceStateRepository) -> Intention:
        """ 识别用户意图。 """
        conversation_history = await self.cache.retrieve_related(text)
        log.debug(f"意图识别：查询历史记录 [UID:{self._uid} history_count:{len(conversation_history)}]")

        intention = await self._recognizer.detect(
            text, conversation_history=conversation_history, device_repo=device_repo
        )

        # 1. 闹钟 2. 音乐 3. 控制 不会继续调用大模型，直接更新对话缓存
        if intention.meta_data:
            self.cache.add(query=text, response=intention.user_prompt)
            log.debug(f"意图缓存更新 [UID:{self._uid}]")

        return intention

    async def query_stream(
            self,
            text: str,
            user_prompt: Optional[str] = None,
            system_prompt: Optional[str] = None,
            on_text: Optional[Callable[[str], Any]] = None,
            on_chunk: Optional[Callable[[str, bool], Any]] = None,
            on_finish: Optional[Callable[[str], Any]] = None,
    ) -> None:
        """
        执行流式文本生成查询。

        Args:
            text: 原始输入文本
            user_prompt: 用户提示词
            system_prompt: 系统提示词
            on_text: 文本回调
            on_chunk: 分块回调
            on_finish: 最终结果回调
        """
        conversation_history = await self.cache.retrieve_related(text)
        log.debug(f"流式生成：查询历史记录 [UID:{self._uid} history_count:{len(conversation_history)}]")

        stream = await self._llm.query(
            text=user_prompt or text,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            stream=True
        )
        processor = StreamProcessor(stream)

        async with self._access_lock:
            self._active_processors.add(processor)

        try:
            response = await processor.run(on_text, on_chunk, on_finish)
            self.cache.add(query=text, response=response)
        except Exception as ex:
            log.error(f"流式生成失败 [UID:{self._uid} - {ex} - {traceback.format_exc()}]")
        finally:
            async with self._access_lock:
                self._active_processors.discard(processor)

    async def close(self) -> None:
        """安全关闭所有活跃流"""
        async with self._access_lock:
            tasks = [processor.stop() for processor in self._active_processors]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                log.debug(f"关闭 {len(tasks)} 个活跃流处理器 [UID:{self._uid}]")

            self._active_processors.clear()
            await self._cache.clear()
            log.info(f"LLM客户端关闭完成 [UID:{self._uid}]")

    @property
    def active_stream_count(self) -> int:
        """获取当前活跃流数量"""
        return len(self._active_processors)


class StreamProcessor:
    """高效流式文本处理器（支持即时中断）"""

    def __init__(self, stream: AsyncGenerator[str, None]):
        self.stream: AsyncGenerator[str, None] = stream
        self._pending_chunk: str = ""
        self._is_active: asyncio.Event = asyncio.Event()
        self._is_active.set()

    async def stop(self):
        """优雅关闭流处理器"""
        self._is_active.clear()
        log.debug("流处理器关闭")

    async def run(
            self,
            on_text: Callable[[str], Any],
            on_chunk: Callable[[str, bool], Any],
            on_finish: Callable[[str], Any],
            on_error: Optional[Callable[[Exception], Any]] = None
    ) -> str:
        """处理文本流并触发回调"""
        full_text = ''
        try:
            async for text in self.stream:
                if not self._is_active.is_set():
                    log.debug("流数据处理器关闭")
                    raise asyncio.CancelledError

                if not text:
                    continue

                full_text += text
                await self._invoke_callback(on_text, text)

                if chunk_text := await self._process_chunk(text):
                    await self._invoke_callback(on_chunk, chunk_text, False)

            await self._invoke_callback(on_chunk, self._pending_chunk.strip(), True)  # 最后一块文本

            await self._invoke_callback(on_finish, full_text)
            log.debug(f"流处理完成 - 长度:{len(full_text)} - 文本:{full_text}")
            return full_text

        except asyncio.CancelledError:
            log.warning(f"流处理被取消 - {traceback.format_exc()}", exc_info=True)
            raise

        except Exception as ex:
            log.error(f"流处理错误 - {ex} - {traceback.format_exc()}", exc_info=True)
            if on_error:
                await self._invoke_callback(on_error, ex)
            raise

    async def _process_chunk(self, text: str) -> Optional[str]:
        """处理文本块并返回可合成的片段"""
        self._pending_chunk += text

        chunk, self._pending_chunk = TextChunker.split_text(self._pending_chunk)
        return chunk

    @staticmethod
    async def _invoke_callback(callback: Callable, *args: Any) -> None:
        """ 安全调用回调函数。 """
        try:
            result = callback(*args)
            if asyncio.iscoroutine(result):
                await result
        except Exception as ex:
            log.error(f"回调执行失败 [callback: {callback.__name__} - {ex} - {traceback.format_exc()}]")


class TextChunker:
    """智能文本分块器，按语义边界分割长文本，支持阿拉伯语等语言"""

    PUNCTUATION: Set[str] = {
        '。', '？', '！', '.', '?', '!',  # 通用句子结束符
        '，', '؛', ';', '،', ',',  # 子句分隔符（包括阿拉伯语逗号和分号）
        '：', ':', '—', '-', '–',  # 子句分隔符
        '۔', '؟', '!',  # 阿拉伯语特定的句子结束符
        '\n', '…', '...',  # 换行和省略号
    }

    # 阿拉伯语优先标点
    AR_PUNCTUATION_PRIORITY: Set[str] = {'،', '؛'}

    MIN_CHUNK_SIZE: dict[str, int] = {
        "zh-CN": 10,
        "en-US": 30,
        "ar-SA": 10,  # 降低以适应阿拉伯语短句
    }

    ARABIC_DIGITS: Set[str] = set('٠١٢٣٤٥٦٧٨٩')

    @classmethod
    def split_text(cls, text: str, language: str = settings.LLM_LANGUAGE) -> Tuple[Optional[str], str]:
        """智能文本分块"""
        pos = cls._find_optimal_split_pos(text, language)
        if pos is None:
            return None, text

        chunk = text[:pos].strip()
        return chunk, text[pos:]

    @classmethod
    def _find_optimal_split_pos(cls, text: str, language: str) -> Optional[int]:
        """查找最佳分割位置"""
        min_chunk_size = cls.MIN_CHUNK_SIZE.get(language, 30)
        if len(text) < min_chunk_size:
            return None

        validator = cls._is_ar_valid_break if language == "ar-SA" else cls._is_valid_break
        for pos in range(min_chunk_size, len(text)):
            if text[pos - 1] not in cls.PUNCTUATION:
                continue

            if validator(text, pos):
                return pos

        return None

    @staticmethod
    def _is_ar_valid_break(text: str, pos: int) -> bool:
        """
        判断当前位置是否允许分割，优化为阿拉伯语特性
        :param text: 完整文本
        :param pos: 待检查位置
        :return: 是否允许分割
        """
        char = text[pos - 1]
        prev_char = text[pos] if pos < len(text) else None  # 逻辑右侧（RTL）
        next_char = text[pos - 2] if pos >= 2 else None  # 逻辑左侧（RTL）

        # 阿拉伯语数字格式（١٢٣٫٤٥، ١٬٠٠٠）
        if char in {'.', '٫', ','} and prev_char and prev_char in TextChunker.ARABIC_DIGITS:
            if next_char and (next_char in TextChunker.ARABIC_DIGITS or next_char in {'"', "'", '”', '’'}):
                return False

        # 时间/日期（١٢:٣٠، ٢٠٢٣-٠١-٠١）
        if char in {':', '-'} and prev_char and next_char:
            if prev_char in TextChunker.ARABIC_DIGITS and next_char in TextChunker.ARABIC_DIGITS:
                return False

        # 缩写词（م.ع.، د.）
        if char in {'.', '٫'} and pos >= 3:
            fragment = text[max(0, pos - 3):pos]
            if '٫' in fragment[:-1]:
                return False

        # 连字符词组（عالي-الجودة）或阿拉伯语连字符（ـ）
        if char in {'-', '–', '—', 'ـ'} and prev_char and next_char:
            if prev_char.isalnum() and next_char.isalnum():
                return False

        # 省略号（... 或 … 或 ⋯）
        if char in {'.', '…', '⋯'} and pos >= 3:
            fragment = text[max(0, pos - 3):pos]
            if fragment in {'...', '…', '⋯'} or fragment.endswith('..'):
                return False

        # 避免在定冠词“ال”后分割
        if pos < len(text) - 1 and text[pos:pos + 2] == 'ال':
            return False

        return True

    @staticmethod
    def _is_valid_break(text: str, pos: int) -> bool:
        """
        判断当前位置是否允许分割，通用语言（非阿拉伯语）
        """
        char = text[pos - 1]
        prev_char = text[pos - 2] if pos >= 2 else None
        next_char = text[pos] if pos < len(text) else None

        # 数字格式（3.14, 1,000）
        if char in {'.', ','} and prev_char and prev_char.isdigit():
            if next_char and (next_char.isdigit() or next_char in {'"', "'", '”', '’'}):
                return False

        # 时间/日期（12:30, 2023-01-01）
        if char in {':', '-'} and prev_char and next_char:
            if prev_char.isdigit() and next_char.isdigit():
                return False

        # 缩写词（U.S.A., Ph.D.）
        if char == '.' and pos >= 3:
            fragment = text[max(0, pos - 4):pos]
            if fragment.isupper() or '.' in fragment[:-1]:
                return False

        # 连字符词组（state-of-the-art）
        if char in {'-', '–', '—'} and prev_char and next_char:
            if prev_char.isalnum() and next_char.isalnum():
                return False

        # 省略号（... 或 … 或 ⋯）
        if char in {'.', '…', '⋯'} and pos >= 3:
            fragment = text[max(0, pos - 3):pos]
            if fragment in {'...', '…', '⋯'} or fragment.endswith('..'):
                return False

        return True
