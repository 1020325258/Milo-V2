# -*- coding: utf-8 -*-
"""Ke-RAG retriever adapter implementing the KnowledgeRetriever interface."""
import os
from typing import List

from .ke_rag_client import KeRagClient
from .models import KnowledgeChunk, RetrievalConfig
from .retriever import KnowledgeRetriever

# Environment variable names
ENV_KE_RAG_BASE_URL = "KE_RAG_BASE_URL"
ENV_KE_RAG_API_KEY = "KE_RAG_API_KEY"


class KeRagRetriever(KnowledgeRetriever):
    """Knowledge retriever backed by the Ke-RAG service.

    This retriever adapts the KeRagClient to the KnowledgeRetriever
    interface, providing a unified way to retrieve knowledge.

    Args:
        base_url: Ke-RAG service base URL. Falls back to KE_RAG_BASE_URL env var.
        api_key: Bearer token for authentication. Falls back to KE_RAG_API_KEY env var.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        timeout: int = 30,
    ):
        self._client = KeRagClient(
            base_url=base_url or os.getenv(ENV_KE_RAG_BASE_URL, ""),
            api_key=api_key or os.getenv(ENV_KE_RAG_API_KEY, ""),
            timeout=timeout,
        )

    async def retrieve(
        self,
        query: str,
        config: RetrievalConfig,
    ) -> List[KnowledgeChunk]:
        """Retrieve knowledge chunks from Ke-RAG.

        Args:
            query: The search query string.
            config: Retrieval configuration.

        Returns:
            A list of KnowledgeChunk objects.
        """
        return await self._client.search(
            query=query,
            space_id=config.space_id,
            mode=config.mode,
            limit=config.limit,
            user_id=config.user_id,
            scope_type=config.space_type,
        )

    async def is_available(self) -> bool:
        """Check if the Ke-RAG service is available.

        Returns:
            True if the service is reachable and authenticated.
        """
        return await self._client.health_check()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.close()
