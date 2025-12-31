# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：base.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/30 09:24
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class Cache(ABC):
    """Abstract base class for interaction caching systems.

    Provides a generic interface for storing and retrieving interaction records.
    """

    @abstractmethod
    def add(self, query: str, response: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Adds a new interaction record to the cache.

        Args:
            query: The input message (e.g., user query)
            response: The output response (e.g., AI response)
            metadata: Optional additional metadata about the interaction
        """
        pass

    @abstractmethod
    async def retrieve_recent(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Retrieves the most recent interactions.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of interaction records, ordered from newest to oldest
        """
        pass

    @abstractmethod
    async def retrieve_related(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Retrieves interactions semantically related to the query.

        Args:
            query: The reference query for finding related interactions
            limit: Maximum number of related records to return

        Returns:
            List of related interaction records
        """
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clears all cached interactions."""
        pass

    @abstractmethod
    def is_empty(self) -> bool:
        """Checks if the cache contains no interactions.

        Returns:
            True if cache is empty, False otherwise
        """
        pass

    @abstractmethod
    def size(self) -> int:
        """Get the current number of cached interactions.

        Returns:
            int: Count of currently stored interactions (0 <= size <= max_size)
        """
        pass
