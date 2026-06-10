# -*- coding: utf-8 -*-
"""Tests for KeRagClient HTTP client."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from .ke_rag_client import KeRagClient
from .models import KnowledgeChunk


@pytest.fixture
def client():
    """Create a KeRagClient instance for testing."""
    return KeRagClient(
        base_url="https://test.api.com/v1",
        api_key="test_key",
        timeout=10,
    )


@pytest.mark.asyncio
async def test_search_success(client):
    """Test successful knowledge search."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "code": 0,
        "message": "Success",
        "data": {
            "total": 2,
            "results": [
                {
                    "content": "Test content 1",
                    "file_name": "file1.txt",
                    "title": "Title 1",
                    "paths": ["path1"],
                },
                {
                    "content": "Test content 2",
                    "file_name": "file2.txt",
                    "title": "Title 2",
                    "paths": ["path2"],
                },
            ],
        },
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(client, '_get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = await client.search(
            query="test query",
            space_id="test_space",
            mode="normal",
            limit=5,
            user_id="user123",
        )

        assert len(result) == 2
        assert isinstance(result[0], KnowledgeChunk)
        assert result[0].content == "Test content 1"
        assert result[0].file_name == "file1.txt"


@pytest.mark.asyncio
async def test_search_api_error(client):
    """Test search when API returns error code."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "code": 1001,
        "message": "Invalid request",
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(client, '_get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = await client.search("query", "space")

        assert len(result) == 0


@pytest.mark.asyncio
async def test_search_timeout(client):
    """Test search timeout handling."""
    with patch.object(client, '_get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Timeout")
        mock_get_client.return_value = mock_client

        result = await client.search("query", "space")

        assert len(result) == 0


@pytest.mark.asyncio
async def test_search_http_error(client):
    """Test search HTTP error handling."""
    with patch.object(client, '_get_client') as mock_get_client:
        mock_client = AsyncMock()
        response = MagicMock()
        response.status_code = 500
        response.text = "Internal Server Error"
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=response
        )
        mock_get_client.return_value = mock_client

        result = await client.search("query", "space")

        assert len(result) == 0


@pytest.mark.asyncio
async def test_health_check_success(client):
    """Test successful health check."""
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch.object(client, '_get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = await client.health_check()

        assert result is True


@pytest.mark.asyncio
async def test_health_check_failure(client):
    """Test health check failure."""
    with patch.object(client, '_get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection failed")
        mock_get_client.return_value = mock_client

        result = await client.health_check()

        assert result is False
