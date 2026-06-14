# -*- coding: utf-8 -*-
"""SreQueryClient 单元测试。"""
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from .client import SreQueryClient


@pytest.fixture
def client():
    """创建测试用的 SreQueryClient 实例。"""
    return SreQueryClient(
        base_url="http://test.example.com",
        app="sreAgent",
        timeout=10.0,
    )


def test_client_init(client):
    """测试客户端初始化。"""
    assert client.base_url == "http://test.example.com"
    assert client.app == "sreAgent"
    assert isinstance(client.client, httpx.AsyncClient)


def test_get_endpoint(client):
    """测试 action 到 endpoint 的映射。"""
    assert client._get_endpoint("contract") == "/sre/contract"
    assert client._get_endpoint("contract_node") == "/sre/contract-node"
    assert client._get_endpoint("decrypt") == "/sre/decrypt"
    assert client._get_endpoint("unknown") == ""


@pytest.mark.asyncio
async def test_query_unknown_action(client):
    """测试未知 action 返回错误。"""
    result = await client.query("unknown_action")
    assert result["success"] is False
    assert "未知的操作类型" in result["message"]


@pytest.mark.asyncio
async def test_query_success(client):
    """测试正常查询。"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "code": 2000,
        "message": "操作成功",
        "data": {"contractCode": "C001", "status": 1},
        "success": True,
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = await client.query("contract", {"contractCode": "C001"})

        assert result["success"] is True
        assert result["data"]["contractCode"] == "C001"
        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_query_timeout(client):
    """测试查询超时。"""
    with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.TimeoutException("timeout")
        result = await client.query("contract", {"contractCode": "C001"})

        assert result["success"] is False
        assert "超时" in result["message"]


@pytest.mark.asyncio
async def test_query_http_error(client):
    """测试 HTTP 错误。"""
    with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.HTTPStatusError(
            "error",
            request=httpx.Request("GET", "http://test"),
            response=httpx.Response(500),
        )
        result = await client.query("contract", {"contractCode": "C001"})

        assert result["success"] is False
        assert "HTTP 错误" in result["message"]


@pytest.mark.asyncio
async def test_close(client):
    """测试关闭客户端。"""
    with patch.object(client.client, "aclose", new_callable=AsyncMock) as mock_close:
        await client.close()
        mock_close.assert_called_once()
