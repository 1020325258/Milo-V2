# -*- coding: utf-8 -*-
"""Apollo 配置查询 Agent Tool。

职责：封装 Apollo 查询为 Agent 可调用的工具，处理业务逻辑和格式化。
不直接处理 HTTP 通信，而是委托给 ApolloClient。
"""
import logging
from typing import Any, Dict

from agentscope.tool import ToolBase
from agentscope.permission import PermissionContext, PermissionDecision, PermissionBehavior
from agentscope.message import TextBlock
from agentscope.tool._response import ToolChunk

from .client import ApolloClient

logger = logging.getLogger(__name__)


class ApolloQueryTool(ToolBase):
    """查询 Apollo 配置中心的数据。

    支持能力：
    - get: 根据 key 查询单个配置值
    - list: 列出某个 namespace 下的所有配置
    - search: 按关键字模糊搜索配置 key
    - release: 查询 namespace 最新 release 信息（含版本号和注释）
    """

    name = "apollo_query"
    description = (
        "查询 Apollo 配置中心的配置数据。"
        "支持按 key 精确查询、列出全部配置、模糊搜索 key、查看 release 信息。"
        "当你需要了解某个服务的配置项、配置值、或排查配置相关问题时使用。"
        "【重要】配置可能分布在不同 namespace 中，常见 namespace 包括："
        "application（默认）、contract、bootstrap 等。"
        "如果在默认 namespace 中找不到配置，请尝试其他 namespace。"
    )
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get", "list", "search", "release"],
                "description": (
                    "操作类型：\n"
                    "- get: 根据 key 查询单个配置值\n"
                    "- list: 列出 namespace 下所有配置\n"
                    "- search: 按关键字模糊搜索配置 key\n"
                    "- release: 查询最新 release 信息"
                ),
            },
            "env": {
                "type": "string",
                "description": "环境，如 DEV, FAT, UAT, PROD。默认 PROD。",
            },
            "app_id": {
                "type": "string",
                "description": "Apollo appId，如 utopia-nrs-sales-project。不传则使用默认值。",
            },
            "cluster": {
                "type": "string",
                "description": "集群名，默认 default。",
            },
            "namespace": {
                "type": "string",
                "description": "命名空间，如 application, contract 等。不传则使用默认值。",
            },
            "key": {
                "type": "string",
                "description": "配置项的 key。get 时必传，search 时作为搜索关键字。",
            },
        },
        "required": ["action"],
    }
    is_concurrency_safe = True
    is_read_only = True

    def __init__(
        self,
        client: ApolloClient,
        default_env: str = "PROD",
        default_app_id: str = "utopia-nrs-sales-project",
        default_cluster: str = "default",
        default_namespace: str = "application",
    ):
        """初始化 Apollo 查询工具。

        Args:
            client: Apollo HTTP 客户端。
            default_env: 默认环境。
            default_app_id: 默认 appId。
            default_cluster: 默认集群。
            default_namespace: 默认 namespace。
        """
        self.client = client
        self.default_env = default_env
        self.default_app_id = default_app_id
        self.default_cluster = default_cluster
        self.default_namespace = default_namespace

    async def check_permissions(
        self,
        tool_input: Dict[str, Any],
        context: PermissionContext,
    ) -> PermissionDecision:
        """Apollo 查询是只读操作，始终允许。"""
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="Apollo query is always allowed (read-only).",
        )

    async def __call__(
        self,
        action: str,
        env: str = "",
        app_id: str = "",
        cluster: str = "",
        namespace: str = "",
        key: str = "",
        **kwargs: Any,
    ) -> ToolChunk:
        """执行 Apollo 查询。"""
        env = env or self.default_env
        app_id = app_id or self.default_app_id
        cluster = cluster or self.default_cluster
        namespace = namespace or self.default_namespace

        try:
            if action == "get":
                return await self._get_item(env, app_id, cluster, namespace, key)
            elif action == "list":
                return await self._list_items(env, app_id, cluster, namespace)
            elif action == "search":
                return await self._search_items(env, app_id, cluster, namespace, key)
            elif action == "release":
                return await self._get_release(env, app_id, cluster, namespace)
            else:
                return self._error_response(f"未知操作: {action}，支持 get/list/search/release")
        except Exception as e:
            logger.exception("Apollo query failed: action=%s, key=%s", action, key)
            return self._error_response(f"Apollo 查询异常: {str(e)}")

    # ── 业务逻辑 ──────────────────────────────────────────────

    async def _get_item(
        self, env: str, app_id: str, cluster: str, namespace: str, key: str,
    ) -> ToolChunk:
        """查询单个配置项。"""
        if not key:
            return self._error_response("get 操作需要传入 key 参数")

        data = await self.client.get_item(env, app_id, cluster, namespace, key)
        if data is None:
            # 提供更详细的错误提示，建议尝试其他 namespace
            suggestion = ""
            if namespace == "application":
                suggestion = "\n\n【建议】该配置可能在其他 namespace 中，请尝试：\n- namespace='contract'\n- namespace='bootstrap'"
            return self._error_response(
                f"在 namespace='{namespace}' 中未找到配置项: {key}"
                f"{suggestion}"
            )

        value = data.get("value", "")
        result = (
            f"## Apollo 配置查询结果\n\n"
            f"| 字段 | 值 |\n"
            f"|------|----|\n"
            f"| 环境 | {env} |\n"
            f"| appId | {app_id} |\n"
            f"| namespace | {namespace} |\n"
            f"| key | {key} |\n"
            f"| value | {value} |\n"
        )
        return ToolChunk(content=[TextBlock(id="apollo_result", text=result)])

    async def _list_items(
        self, env: str, app_id: str, cluster: str, namespace: str,
    ) -> ToolChunk:
        """列出 namespace 下所有配置项。"""
        data = await self.client.list_items(env, app_id, cluster, namespace)
        if data is None or not isinstance(data, list):
            return self._error_response(
                f"无法获取 namespace={namespace} 的配置列表。\n"
                f"可能原因：\n"
                f"1. Apollo token 过期或无效\n"
                f"2. namespace '{namespace}' 不存在\n"
                f"3. Apollo 服务不可达\n"
                f"建议：尝试使用其他 namespace（如 'application', 'contract'）或检查 Apollo 配置"
            )

        if not data:
            return self._info_response(f"namespace={namespace} 下没有配置项")

        lines = [
            f"## Apollo 配置列表\n\n"
            f"**环境**: {env} | **appId**: {app_id} | **namespace**: {namespace}\n\n"
            f"共 {len(data)} 个配置项：\n\n"
            f"| # | key | value (前100字符) |\n"
            f"|---|-----|--------------------|\n",
        ]
        for i, item in enumerate(data, 1):
            k = item.get("key", "")
            v = item.get("value", "")
            if len(v) > 100:
                v = v[:100] + "..."
            lines.append(f"| {i} | `{k}` | {v} |\n")

        return ToolChunk(content=[TextBlock(id="apollo_list", text="".join(lines))])

    async def _search_items(
        self, env: str, app_id: str, cluster: str, namespace: str, keyword: str,
    ) -> ToolChunk:
        """按关键字模糊搜索配置 key。

        Apollo OpenAPI 没有直接的模糊搜索接口，
        通过 list 全量后在客户端过滤。
        """
        if not keyword:
            return self._error_response("search 操作需要传入 key 参数作为搜索关键字")

        data = await self.client.list_items(env, app_id, cluster, namespace)
        if data is None or not isinstance(data, list):
            return self._error_response(
                f"无法获取 namespace={namespace} 的配置列表。\n"
                f"可能原因：\n"
                f"1. Apollo token 过期或无效\n"
                f"2. namespace '{namespace}' 不存在\n"
                f"3. Apollo 服务不可达\n"
                f"建议：尝试使用其他 namespace（如 'application', 'contract'）或检查 Apollo 配置"
            )

        keyword_lower = keyword.lower()
        matched = [
            item for item in data
            if keyword_lower in item.get("key", "").lower()
            or keyword_lower in item.get("value", "").lower()
        ]

        if not matched:
            return self._info_response(
                f"在 namespace={namespace} 中未找到匹配 '{keyword}' 的配置项"
            )

        lines = [
            f"## Apollo 配置搜索结果\n\n"
            f"**搜索关键字**: `{keyword}` | **匹配数量**: {len(matched)}\n\n"
            f"| # | key | value (前100字符) |\n"
            f"|---|-----|--------------------|\n",
        ]
        for i, item in enumerate(matched, 1):
            k = item.get("key", "")
            v = item.get("value", "")
            if len(v) > 100:
                v = v[:100] + "..."
            lines.append(f"| {i} | `{k}` | {v} |\n")

        return ToolChunk(content=[TextBlock(id="apollo_search", text="".join(lines))])

    async def _get_release(
        self, env: str, app_id: str, cluster: str, namespace: str,
    ) -> ToolChunk:
        """查询 namespace 最新 release 信息。"""
        data = await self.client.get_latest_release(env, app_id, cluster, namespace)
        if data is None:
            return self._error_response(f"无法获取 namespace={namespace} 的 release 信息")

        release_time = data.get("releaseTime", "未知")
        comment = data.get("comment", "无")
        configurations = data.get("configurations", [])

        lines = [
            f"## Apollo Release 信息\n\n"
            f"| 字段 | 值 |\n"
            f"|------|----|\n"
            f"| 环境 | {env} |\n"
            f"| appId | {app_id} |\n"
            f"| namespace | {namespace} |\n"
            f"| 发布时间 | {release_time} |\n"
            f"| 备注 | {comment} |\n"
            f"| 配置项数量 | {len(configurations)} |\n",
        ]

        if configurations:
            lines.append("\n### 配置项详情\n\n")
            lines.append("| key | value (前100字符) |\n")
            lines.append("|-----|--------------------|\n")
            for item in configurations:
                k = item.get("key", "")
                v = item.get("value", "")
                if len(v) > 100:
                    v = v[:100] + "..."
                lines.append(f"| `{k}` | {v} |\n")

        return ToolChunk(content=[TextBlock(id="apollo_release", text="".join(lines))])

    # ── 响应格式化 ─────────────────────────────────────────────

    @staticmethod
    def _error_response(message: str) -> ToolChunk:
        return ToolChunk(
            content=[TextBlock(id="apollo_error", text=f"❌ {message}")]
        )

    @staticmethod
    def _info_response(message: str) -> ToolChunk:
        return ToolChunk(
            content=[TextBlock(id="apollo_info", text=f"ℹ️ {message}")]
        )
