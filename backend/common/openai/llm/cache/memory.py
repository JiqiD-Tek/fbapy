# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：memory.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/30 09:15
"""

import asyncio
from collections import deque
from typing import Deque, Dict, Any, List, Optional

from backend.utils.timezone import timezone
from backend.common.openai.llm.cache.base import Cache


class MemoryCache(Cache):
    """In-memory cache for conversation history with LRU eviction policy.
    """

    def __init__(self, max_size: int = 3) -> None:
        """Initialize with specified cache size.

        Args:
            max_size: Maximum number of interactions to retain
        """
        self._cache: Deque[Dict[str, Any]] = deque(maxlen=max_size)

        # 事件循环引用
        self._loop = asyncio.get_running_loop()

    def add(self,
            query: str,
            response: str,
            metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add an interaction to cache with automatic eviction when full.

        Args:
            query: User input/query
            response: System response
            metadata: Additional context data (e.g., embeddings, scores)
        """
        record = {
            'datetime': timezone.now(),
            'user': query,
            'assistant': response,
            'metadata': metadata or {},
            'last_accessed': self._loop.time()
        }
        self._cache.append(record)

    async def retrieve_recent(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Get most recent interactions sorted by access time (newest first).

        Args:
            limit: Maximum number of records to return

        Returns:
            List of interaction records sorted by recency
        """
        return sorted(
            list(self._cache)[-limit:],
            key=lambda x: x['last_accessed'],
            reverse=False
        )

    async def retrieve_related(self,
                               query: str,
                               limit: int = 3) -> List[Dict[str, Any]]:
        """Placeholder for semantic search (returns recent by default).

        Args:
            query: Reference query for similarity search
            limit: Maximum results to return

        Returns:
            Currently returns recent interactions as fallback
        """
        return await self.retrieve_recent(limit)  # TODO: Implement semantic search

    def is_empty(self) -> bool:
        """Check if cache contains no interactions.

        Returns:
            True if cache is empty, False otherwise
        """
        return not bool(self._cache)

    def size(self) -> int:
        """Get the current number of cached interactions.

        Returns:
            int: Count of currently stored interactions (0 <= size <= max_size)
        """
        return len(self._cache)

    async def clear(self) -> None:
        """Reset the cache to empty state."""
        self._cache.clear()

    def __len__(self) -> int:
        """Current number of cached interactions."""
        return len(self._cache)
