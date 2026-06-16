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


# ── field_config 维度语义测试 ──────────────────────────────────────


def test_describe_dims_beike_scenario(tool):
    """测试被窝场景的维度描述。"""
    desc = tool.describe_field_config_dims(
        business_type=1, gb_code=110000, company_code="V201601528", version=1, contract_type=1,
    )
    assert "整装" in desc
    assert "被窝" in desc
    assert "110000" in desc
    assert "V201601528" in desc
    assert "被窝2.5" in desc


def test_describe_dims_shengdu_scenario(tool):
    """测试圣都场景的维度描述。"""
    desc = tool.describe_field_config_dims(
        business_type=1, gb_code=0, company_code="", version=2, contract_type=3,
    )
    assert "整装" in desc
    assert "圣都" in desc
    assert "圣都2.5" in desc


def test_describe_dims_shengdu_v3(tool):
    """测试圣都 version=3 的维度描述。"""
    desc = tool.describe_field_config_dims(
        business_type=2, gb_code=0, company_code="", version=3,
    )
    assert "团装" in desc
    assert "圣都2.5开启预报价" in desc


def test_describe_dims_no_params(tool):
    """测试无参数时的维度描述。"""
    desc = tool.describe_field_config_dims()
    assert "未指定维度参数" in desc


def test_describe_dims_partial_params(tool):
    """测试部分参数时的维度描述。"""
    desc = tool.describe_field_config_dims(business_type=3, contract_type=5)
    assert "局装" in desc
    assert "合同类型: 5" in desc


def test_describe_dims_unknown_business_type(tool):
    """测试未知业务类型。"""
    desc = tool.describe_field_config_dims(business_type=99)
    assert "未知(99)" in desc


@pytest.mark.asyncio
async def test_field_config_with_dim_context(tool, mock_client):
    """测试 field_config 输出包含维度语义描述（OneIdPageInfo 分页结构）。"""
    mock_client.query.return_value = {
        "code": 2000,
        "message": "操作成功",
        "data": {
            "total": 1,
            "pageNum": 1,
            "pageSize": 50,
            "pages": 1,
            "hasNextPage": False,
            "data": [
                {
                    "businessType": 1,
                    "gbcode": 110000,
                    "companyCode": "V201601528",
                    "contractType": 1,
                    "version": 1,
                    "moduleKey": "basic",
                    "fieldKey": "address",
                    "fieldName": "地址",
                    "required": 1,
                },
            ],
        },
        "success": True,
    }

    result = await tool.__call__(
        action="field_config",
        business_type=1,
        gb_code=110000,
        company_code="V201601528",
        contract_type=1,
        version=1,
    )
    text = result.content[0].text
    assert "查询维度" in text
    assert "被窝" in text
    assert "整装" in text
    assert "被窝2.5" in text
    assert "字段配置" in text
    assert "分页信息" in text
    assert "已是最后一页" in text


@pytest.mark.asyncio
async def test_field_config_shengdu_fallback(tool, mock_client):
    """测试圣都兜底配置查询输出。"""
    mock_client.query.return_value = {
        "code": 2000,
        "message": "操作成功",
        "data": {
            "total": 1,
            "pageNum": 1,
            "pageSize": 50,
            "pages": 1,
            "hasNextPage": False,
            "data": [
                {
                    "businessType": 1,
                    "gbcode": 0,
                    "companyCode": "",
                    "contractType": 1,
                    "version": 2,
                    "moduleKey": "basic",
                    "fieldKey": "name",
                    "fieldName": "姓名",
                    "required": 1,
                },
            ],
        },
        "success": True,
    }

    result = await tool.__call__(
        action="field_config",
        business_type=1,
        gb_code=0,
        company_code="",
        contract_type=1,
        version=2,
    )
    text = result.content[0].text
    assert "查询维度" in text
    assert "圣都" in text
    assert "圣都2.5" in text


@pytest.mark.asyncio
async def test_field_config_no_dims(tool, mock_client):
    """测试无维度参数时返回验证错误，提示需要明确全部维度。"""
    result = await tool.__call__(action="field_config")
    text = result.content[0].text
    # 应返回错误提示，列出缺失的维度
    assert "需要明确全部 5 个维度" in text
    assert "business_type" in text
    assert "gb_code" in text
    assert "company_code" in text
    assert "contract_type" in text
    assert "version" in text
    # 不应发起实际查询
    mock_client.query.assert_not_called()


@pytest.mark.asyncio
async def test_field_config_partial_dims(tool, mock_client):
    """测试部分维度缺失时返回验证错误。"""
    result = await tool.__call__(
        action="field_config",
        business_type=1,
        gb_code=0,
        company_code="",
    )
    text = result.content[0].text
    assert "需要明确全部 5 个维度" in text
    # 缺失 contract_type 和 version
    assert "contract_type" in text
    assert "version" in text
    # 已提供的不应出现在缺失列表中
    assert "business_type" not in text.split("需要明确全部 5 个维度")[1] or "business_type（" not in text.split("需要明确全部 5 个维度")[1]
    mock_client.query.assert_not_called()


@pytest.mark.asyncio
async def test_field_config_missing_company_code(tool, mock_client):
    """测试 company_code 未传（None）与传空字符串的区别。"""
    # company_code=None 应报错
    result = await tool.__call__(
        action="field_config",
        business_type=1,
        gb_code=0,
        version=2,
        contract_type=1,
    )
    text = result.content[0].text
    assert "company_code" in text
    mock_client.query.assert_not_called()


@pytest.mark.asyncio
async def test_field_config_pagination_has_next(tool, mock_client):
    """测试分页：有下一页时提示翻页。"""
    mock_client.query.return_value = {
        "code": 2000,
        "message": "操作成功",
        "data": {
            "total": 128,
            "pageNum": 1,
            "pageSize": 50,
            "pages": 3,
            "hasNextPage": True,
            "nextPage": 2,
            "data": [
                {"moduleKey": "basic", "fieldKey": f"field_{i}", "fieldName": f"字段{i}"}
                for i in range(50)
            ],
        },
        "success": True,
    }

    result = await tool.__call__(
        action="field_config",
        business_type=1,
        gb_code=0,
        company_code="",
        contract_type=1,
        version=2,
    )
    text = result.content[0].text
    assert "第 1/3 页" in text
    assert "共 128 条" in text
    assert "page_num=2" in text
    assert "还有下一页" in text


@pytest.mark.asyncio
async def test_field_config_pagination_last_page(tool, mock_client):
    """测试分页：最后一页时提示已到底。"""
    mock_client.query.return_value = {
        "code": 2000,
        "message": "操作成功",
        "data": {
            "total": 128,
            "pageNum": 3,
            "pageSize": 50,
            "pages": 3,
            "hasNextPage": False,
            "data": [
                {"moduleKey": "basic", "fieldKey": f"field_{i}", "fieldName": f"字段{i}"}
                for i in range(28)
            ],
        },
        "success": True,
    }

    result = await tool.__call__(
        action="field_config",
        business_type=1,
        gb_code=0,
        company_code="",
        contract_type=1,
        version=2,
        page_num=3,
    )
    text = result.content[0].text
    assert "第 3/3 页" in text
    assert "共 128 条" in text
    assert "已是最后一页" in text


@pytest.mark.asyncio
async def test_field_config_backward_compat_plain_list(tool, mock_client):
    """测试向后兼容：接口返回纯列表时仍能正常格式化。"""
    mock_client.query.return_value = {
        "code": 2000,
        "message": "操作成功",
        "data": [
            {"moduleKey": "basic", "fieldKey": "name", "fieldName": "姓名"},
        ],
        "success": True,
    }

    result = await tool.__call__(
        action="field_config",
        business_type=1,
        gb_code=0,
        company_code="",
        contract_type=1,
        version=2,
    )
    text = result.content[0].text
    assert "字段配置" in text
    assert "姓名" in text
