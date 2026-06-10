# -*- coding: utf-8 -*-
"""Tests for knowledge_search tool."""
import pytest
from unittest.mock import AsyncMock, patch

from .models import KnowledgeChunk, RetrievalConfig
from .tools import KnowledgeSearchTool


@pytest.fixture
def tool():
    """Create a KnowledgeSearchTool instance for testing."""
    return KnowledgeSearchTool(
        space_id="test_space",
        mode="normal",
        limit=5,
        user_id="user123",
    )


@pytest.mark.asyncio
async def test_tool_call_success(tool):
    """Test successful tool execution."""
    chunks = [
        KnowledgeChunk(
            content="Test content",
            file_name="test.txt",
            title="Test Title",
            chunk_id="test_0",
        ),
    ]

    with patch("backend.rag.tools.get_retriever") as mock_get_retriever:
        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = chunks
        mock_get_retriever.return_value = mock_retriever

        result = await tool(query="test query")

        assert result.state == "success"
        assert len(result.content) == 1
        assert "找到 1 条相关知识" in result.content[0].text


@pytest.mark.asyncio
async def test_tool_call_no_retriever(tool):
    """Test tool execution when no retriever is configured."""
    with patch("backend.rag.tools.get_retriever") as mock_get_retriever:
        mock_get_retriever.return_value = None

        result = await tool(query="test query")

        assert len(result.content) == 1
        assert "No knowledge retriever" in result.content[0].text


@pytest.mark.asyncio
async def test_tool_call_empty_results(tool):
    """Test tool execution with no search results."""
    with patch("backend.rag.tools.get_retriever") as mock_get_retriever:
        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = []
        mock_get_retriever.return_value = mock_retriever

        result = await tool(query="test query")

        assert len(result.content) == 1
        assert "未找到相关知识" in result.content[0].text


@pytest.mark.asyncio
async def test_tool_call_error(tool):
    """Test tool execution when search fails."""
    with patch("backend.rag.tools.get_retriever") as mock_get_retriever:
        mock_retriever = AsyncMock()
        mock_retriever.retrieve.side_effect = Exception("Search failed")
        mock_get_retriever.return_value = mock_retriever

        result = await tool(query="test query")

        assert len(result.content) == 1
        assert "Knowledge search failed" in result.content[0].text


def test_tool_properties(tool):
    """Test tool properties."""
    assert tool.name == "knowledge_search"
    assert tool.is_read_only is True
    assert tool.is_concurrency_safe is True
    assert "query" in tool.input_schema["properties"]


def test_format_results(tool):
    """Test result formatting."""
    chunks = [
        KnowledgeChunk(
            content="Short content",
            file_name="file1.txt",
            title="Title 1",
        ),
        KnowledgeChunk(
            content="A" * 600,  # Long content should be truncated
            file_name="file2.txt",
            title="Title 2",
        ),
    ]

    result = tool._format_results(chunks)

    assert "找到 2 条相关知识" in result
    assert "Title 1" in result
    assert "Title 2" in result
    assert "..." in result  # Content was truncated
