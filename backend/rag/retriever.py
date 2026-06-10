# -*- coding: utf-8 -*-
"""Abstract knowledge retriever interface."""
from abc import ABC, abstractmethod
from typing import List

from .models import KnowledgeChunk, RetrievalConfig


class KnowledgeRetriever(ABC):
    """Abstract base class for knowledge retrieval backends.

    All knowledge retrieval implementations must inherit from this class
    and implement the `retrieve` and `is_available` methods.

    Usage:
        class MyRetriever(KnowledgeRetriever):
            async def retrieve(self, query, config):
                # Implement retrieval logic
                return [KnowledgeChunk(...)]

            async def is_available(self):
                # Check if backend is available
                return True
    """

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        config: RetrievalConfig,
    ) -> List[KnowledgeChunk]:
        """Retrieve knowledge chunks based on the query.

        Args:
            query: The search query string.
            config: Retrieval configuration including space_id, mode, etc.

        Returns:
            A list of KnowledgeChunk objects matching the query.
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the knowledge retrieval backend is available.

        Returns:
            True if the backend is available, False otherwise.
        """
        ...
