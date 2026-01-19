#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Project : jiqid-py
@File    : assistant.py
@Author  : guhua@jiqid.com
@Created : 2025/05/20 10:49
"""
import re
import asyncio
import traceback

from typing import AsyncGenerator, Callable, Any, Optional, Set, Tuple

from backend.common.openai.core.classifier import Intention, Recognizer

from backend.common.log import log
from backend.common.openai.core.cache.memory import MemoryCache

from backend.common.openai.providers.azure_service.asr import AzureASR
from backend.common.openai.providers.azure_service.llm import AzureLLM
from backend.common.openai.providers.azure_service.tts import AzureTTS


class Assistant:
    """大模型服务的高并发客户端(意图识别、内容生成)

    特性：
    - 线程安全的异步请求管理
    - 动态流式处理器跟踪
    """

    def __init__(self, uid: str):
        """ 初始化大模型服务客户端 """
        self.uid = uid

        self._cache = MemoryCache(max_size=3)
        self._stream_processor: Optional[StreamProcessor] = None

        self.asr = AzureASR()
        self.llm = AzureLLM()
        self.tts = AzureTTS()

        self._recognizer = Recognizer(llm=self.llm)

    @property
    def cache(self) -> MemoryCache:
        """获取聊天缓存实例。"""
        return self._cache

    async def query_intention(self, text: str, chat_config) -> Intention:
        """ 识别用户意图。 """
        conversation_history = await self.cache.retrieve_related(text)
        log.debug(f"意图识别：查询历史记录 [UID:{self.uid} history_count:{len(conversation_history)}]")

        intention = await self._recognizer.detect(
            text, conversation_history=conversation_history, chat_config=chat_config
        )

        # 1. 闹钟 2. 音乐 3. 控制 不会继续调用大模型，直接更新对话缓存
        if intention.meta_data:
            self.cache.add(query=text, response=intention.user_prompt)
            log.debug(f"意图缓存更新 [UID:{self.uid}]")

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
        log.debug(f"流式生成：查询历史记录 [UID:{self.uid} history_count:{len(conversation_history)}]")

        stream = await self.llm.query(
            text=user_prompt or text,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            stream=True
        )

        # 新请求来 → 旧流立即中断
        if self._stream_processor:
            await self._stream_processor.stop()

        self._stream_processor = StreamProcessor(stream)

        try:
            response = await self._stream_processor.run(on_text, on_chunk, on_finish)
            self.cache.add(query=text, response=response)
        except Exception as ex:
            log.error(f"流式生成失败 [UID:{self.uid} - {ex} - {traceback.format_exc()}]")

    async def close(self) -> None:
        """安全关闭活跃流"""
        if self._stream_processor:
            await self._stream_processor.stop()
            self._stream_processor = None
            log.info(f"LLM客户端关闭完成 [UID:{self.uid}]")


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
    """
    智能文本分块器，旨在根据语义边界将长文本分割成有意义的块。
    它会优先在句子或子句的末尾进行分割，同时避免在数字、日期、缩写词等内部错误地断开。
    """

    # 将标点符号按功能分类，便于逻辑扩展
    SENTENCE_ENDINGS: Set[str] = {'。', '？', '！', '.', '?', '!'}
    CLAUSE_SEPARATORS: Set[str] = {'，', '；', ',', '：', ':', '—', '-', '–'}
    OTHER_BREAKS: Set[str] = {'\n', '…', '...'}

    # 合并所有可作为分割依据的标点
    ALL_PUNCTUATION: Set[str] = SENTENCE_ENDINGS | CLAUSE_SEPARATORS | OTHER_BREAKS

    DEFAULT_MIN_CHUNK_SIZE: int = 30  # 默认值

    # 预编译正则表达式以提高性能
    # 匹配常见的数字格式 (e.g., 3.14, 1,000,000)
    NUMBER_REGEX = re.compile(r'\d([.,])\d')
    # 匹配常见的日期和时间格式 (e.g., 2023-01-01, 12:30)
    DATETIME_REGEX = re.compile(r'\d([-:])\d')
    # 匹配常见的缩写 (e.g., U.S.A., Ph.D.)
    ABBREVIATION_REGEX = re.compile(r'\b[A-Z](?:\.[A-Z])+\.?')
    # 匹配省略号
    ELLIPSIS_REGEX = re.compile(r'(\.\.\.|\u2026)')  # ... 或 …

    @classmethod
    def split_text(cls, text: str) -> Tuple[Optional[str], str]:
        """
        从文本开头分割出第一个语义完整的块。

        Args:
            text (str): 待分割的原始文本。

        Returns:
            Tuple[Optional[str], str]: 返回一个元组。
            如果成功分割，第一个元素是分割出的文本块，第二个元素是剩余文本。
            如果无法找到合适的分割点，第一个元素为 None，第二个元素为原始文本。
        """
        if not text:
            return None, ""

        pos = cls._find_optimal_split_pos(text)
        if pos is None:
            return None, text

        chunk = text[:pos].strip()
        remaining_text = text[pos:].strip()
        return chunk, remaining_text

    @classmethod
    def _find_optimal_split_pos(cls, text: str) -> Optional[int]:
        """
        在文本中查找最佳的分割位置。
        它从最小分块长度开始向后扫描，寻找第一个有效的标点符号作为分割点。
        """
        min_chunk_size = cls.DEFAULT_MIN_CHUNK_SIZE

        # 如果文本本身就小于最小分块大小，则不进行分割
        if len(text) < min_chunk_size:
            return None

        # 从最小长度开始，寻找第一个有效的分割点
        # 增加搜索范围，以防有效分割点在min_chunk_size之后
        search_limit = max(min_chunk_size * 2, len(text))

        for pos in range(min_chunk_size, search_limit):
            # 确保 pos-1 在文本范围内
            if pos > len(text):
                break

            if text[pos - 1] in cls.ALL_PUNCTUATION and cls._is_valid_break(text, pos):
                return pos

        # 如果在扩展搜索范围内仍未找到，则在整个文本中从后往前找最后一个有效分割点
        for pos in range(len(text), min_chunk_size, -1):
            if text[pos - 1] in cls.ALL_PUNCTUATION and cls._is_valid_break(text, pos):
                return pos

        return None

    @classmethod
    def _is_valid_break(cls, text: str, pos: int) -> bool:
        """
        使用预编译的正则表达式和逻辑判断，验证一个位置是否是有效的分割点。
        这可以防止在数字、日期、缩写词等中间断开。
        """
        # 检查点是标点符号前面的位置
        break_char = text[pos - 1]

        # 检查周围的上下文，以防在特殊格式中间断开
        # 上下文窗口可以根据需要调整
        context_start = max(0, pos - 10)
        context_end = min(len(text), pos + 10)
        context = text[context_start:context_end]

        # 将当前位置映射到上下文中的相对位置
        relative_pos = pos - context_start

        # 规则 1: 数字格式 (e.g., 3.14, 1,000)
        if break_char in {'.', ','}:
            # 查找所有匹配项，检查是否有任何一个跨越了我们的分割点
            for match in cls.NUMBER_REGEX.finditer(context):
                if match.start(1) < relative_pos <= match.end(1):
                    return False

        # 规则 2: 日期/时间格式 (e.g., 2023-01-01, 12:30)
        if break_char in {'-', ':'}:
            for match in cls.DATETIME_REGEX.finditer(context):
                if match.start(1) < relative_pos <= match.end(1):
                    return False

        # 规则 3: 缩写词 (e.g., U.S.A.)
        if break_char == '.':
            for match in cls.ABBREVIATION_REGEX.finditer(context):
                # 如果分割点在缩写词的内部
                if match.start() < relative_pos - 1 and relative_pos <= match.end():
                    return False

        # 规则 4: 省略号 (...)
        if break_char == '.':
            for match in cls.ELLIPSIS_REGEX.finditer(context):
                if match.start() < relative_pos - 1 and relative_pos <= match.end():
                    return False

        # 规则 5: 连字符词组 (e.g., state-of-the-art)
        # 原始逻辑已经很有效，这里保留
        if break_char in {'-', '–', '—'}:
            prev_char = text[pos - 2] if pos > 1 else None
            next_char = text[pos] if pos < len(text) else None
            if prev_char and next_char and prev_char.isalnum() and next_char.isalnum():
                return False

        return True
