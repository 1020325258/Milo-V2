# -*- coding: utf-8 -*-
"""Tests for KnowledgeRetriever abstract interface."""
import pytest
from typing import List

from .models import KnowledgeChunk, RetrievalConfig
from .retriever import KnowledgeRetriever


class MockRetriever(KnowledgeRetriever):
    """Mock retriever for testing."""

    def __init__(self, chunks: List[KnowledgeChunk] = None, available: bool = True):
        self._chunks = chunks or []
        self._available = available
        self._last_query = None
        self._last_config = None

    async def retrieve(
        self,
        query: str,
        config: RetrievalConfig,
    ) -> List[KnowledgeChunk]:
        self._last_query = query
        self._last_config = config
        return self._chunks

    async def is_available(self) -> bool:
        return self._available


@pytest.mark.asyncio
async def test_retriever_returns_chunks():
    """Test that retriever returns knowledge chunks."""
    chunks = [
        KnowledgeChunk(
            content="Test content",
            file_name="test.txt",
            title="Test Title",
            chunk_id="test_0",
        ),
    ]
    retriever = MockRetriever(chunks=chunks)
    config = RetrievalConfig(space_id="test_space")

    result = await retriever.retrieve("test query", config)

    assert len(result) == 1
    assert result[0].content == "Test content"
    assert result[0].file_name == "test.txt"


@pytest.mark.asyncio
async def test_retriever_passes_config():
    """Test that retriever receives the correct config."""
    retriever = MockRetriever()
    config = RetrievalConfig(
        space_id="my_space",
        mode="ultra",
        limit=10,
        user_id="user123",
    )

    await retriever.retrieve("query", config)

    assert retriever._last_query == "query"
    assert retriever._last_config.space_id == "my_space"
    assert retriever._last_config.mode == "ultra"
    assert retriever._last_config.limit == 10


@pytest.mark.asyncio
async def test_retriever_is_available():
    """Test retriever availability check."""
    available_retriever = MockRetriever(available=True)
    unavailable_retriever = MockRetriever(available=False)

    assert await available_retriever.is_available() is True
    assert await unavailable_retriever.is_available() is False


@pytest.mark.asyncio
async def test_retriever_empty_results():
    """Test retriever with no results."""
    retriever = MockRetriever(chunks=[])
    config = RetrievalConfig(space_id="test_space")

    result = await retriever.retrieve("query", config)

    assert len(result) == 0
