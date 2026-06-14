# -*- coding: utf-8 -*-
"""SreQueryTool 单元测试。"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from agentscope.permission import PermissionContext, PermissionDecision, PermissionBehavior

from .client import SreQueryClient
from .tools import SreQueryTool


@pytest.fixture
def mock_client():
    """创建 mock 的 SreQueryClient。"""
    client = MagicMock(spec=SreQueryClient)
    client.query = AsyncMock()
    return client


@pytest.fixture
def tool(mock_client):
    """创建测试用的 SreQueryTool 实例。"""
    return SreQueryTool(client=mock_client)


def test_tool_attributes(tool):
    """测试工具属性。"""
    assert tool.name == "sre_query"
    assert tool.is_concurrency_safe is True
    assert tool.is_read_only is True
    assert "action" in tool.input_schema["properties"]


@pytest.mark.asyncio
async def test_check_permissions(tool):
    """测试权限检查（始终允许）。"""
    context = MagicMock(spec=PermissionContext)
    decision = await tool.check_permissions({}, context)
    assert decision.behavior == PermissionBehavior.ALLOW


@pytest.mark.asyncio
async def test_validate_params_missing_action(tool):
    """测试缺少 action 参数。"""
    result = await tool.__call__(action="")
    assert "缺少必需参数" in result.content[0].text


@pytest.mark.asyncio
async def test_validate_params_missing_contract_code(tool):
    """测试 contract 操作缺少 contract_code。"""
    result = await tool.__call__(action="contract")
    assert "需要 contract_code 或 project_order_id" in result.content[0].text


@pytest.mark.asyncio
async def test_validate_params_missing_encrypted_text(tool):
    """测试 decrypt 操作缺少 encrypted_text。"""
    result = await tool.__call__(action="decrypt")
    assert "需要 encrypted_text" in result.content[0].text


@pytest.mark.asyncio
async def test_validate_params_unknown_action(tool):
    """测试未知的 action。"""
    result = await tool.__call__(action="unknown_action")
    assert "未知的操作类型" in result.content[0].text


@pytest.mark.asyncio
async def test_query_success_single_object(tool, mock_client):
    """测试成功查询单个对象。"""
    mock_client.query.return_value = {
        "code": 2000,
        "message": "操作成功",
        "data": {"contractCode": "C001", "status": 1},
        "success": True,
    }

    result = await tool.__call__(action="contract", contract_code="C001")
    assert "合同信息" in result.content[0].text
    assert "C001" in result.content[0].text


@pytest.mark.asyncio
async def test_query_success_list(tool, mock_client):
    """测试成功查询列表。"""
    mock_client.query.return_value = {
        "code": 2000,
        "message": "操作成功",
        "data": [
            {"nodeId": 1, "nodeName": "节点1"},
            {"nodeId": 2, "nodeName": "节点2"},
        ],
        "success": True,
    }

    result = await tool.__call__(action="contract_node", contract_code="C001")
    assert "合同节点" in result.content[0].text
    assert "节点1" in result.content[0].text


@pytest.mark.asyncio
async def test_query_empty_data(tool, mock_client):
    """测试查询结果为空。"""
    mock_client.query.return_value = {
        "code": 2000,
        "message": "操作成功",
        "data": None,
        "success": True,
    }

    result = await tool.__call__(action="contract", contract_code="C001")
    assert "查询结果为空" in result.content[0].text


@pytest.mark.asyncio
async def test_query_failed(tool, mock_client):
    """测试查询失败。"""
    mock_client.query.return_value = {
        "code": 5000,
        "message": "系统错误",
        "data": None,
        "success": False,
    }

    result = await tool.__call__(action="contract", contract_code="C001")
    assert "系统错误" in result.content[0].text


@pytest.mark.asyncio
async def test_query_decrypt(tool, mock_client):
    """测试解密查询。"""
    mock_client.query.return_value = {
        "code": 2000,
        "message": "操作成功",
        "data": "110101199001011234",
        "success": True,
    }

    result = await tool.__call__(action="decrypt", encrypted_text="xxx")
    assert "解密结果" in result.content[0].text
    assert "110101199001011234" in result.content[0].text


@pytest.mark.asyncio
async def test_query_contract_field(tool, mock_client):
    """测试查询合同扩展字段。"""
    mock_client.query.return_value = {
        "code": 2000,
        "message": "操作成功",
        "data": {"field1": "value1", "field2": "value2"},
        "success": True,
    }

    result = await tool.__call__(action="contract_field", contract_code="C001")
    assert "合同扩展字段" in result.content[0].text
    assert "field1" in result.content[0].text


@pytest.mark.asyncio
async def test_query_exception(tool, mock_client):
    """测试查询异常。"""
    mock_client.query.side_effect = Exception("网络异常")

    result = await tool.__call__(action="contract", contract_code="C001")
    assert "查询异常" in result.content[0].text
