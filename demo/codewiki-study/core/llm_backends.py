"""
LLM 后端工厂 — 统一创建各种 completer

三种 completer 对应不同的使用场景：
  1. cluster_completer   — 聚类用，单轮纯文本补全（无工具）
  2. doc_completer       — 文档生成用，Agent 模式（Write/Read 工具 + MCP）
  3. overview_completer  — 概览生成用，单轮纯文本补全（无工具）

支持两种后端：
  - "claude_code" : Claude Code SDK（claude_agent_sdk）
  - "openai"      : OpenAI 兼容 API（如 mimo token plan）
"""

import os
import json
import logging
from typing import Callable, Tuple

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# OpenAI 后端
# ─────────────────────────────────────────────────────────────

def _create_openai_client():
    """创建 OpenAI 客户端"""
    from openai import OpenAI
    return OpenAI(
        base_url=os.getenv("OPENAI_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "tp-cxq9g672kqgmcpmgvzhktpk7vucswrn9atq4i4ehwyxc6ngl"),
    )


def _openai_complete(client, system_prompt: str, user_prompt: str) -> str:
    """OpenAI 单次补全（system + user 双 prompt）"""
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "mimo-v2.5-pro"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0, max_tokens=8192,
    )
    result = response.choices[0].message.content
    logger.info(f"      ✅ OpenAI response: {response.usage.total_tokens} tokens")
    return result


def create_openai_backends() -> Tuple[Callable[[str], str], Callable[[str, str], str], Callable[[str, str], str]]:
    """
    创建 OpenAI 后端的三种 completer。

    Returns:
        (cluster_completer, doc_completer, overview_completer)
    """
    from core.cluster_modules import create_openai_completer
    client = _create_openai_client()

    cluster_completer = create_openai_completer()

    def doc_completer(system_prompt: str, user_prompt: str) -> str:
        return _openai_complete(client, system_prompt, user_prompt)

    overview_completer = doc_completer

    return cluster_completer, doc_completer, overview_completer


# ─────────────────────────────────────────────────────────────
# Claude Code SDK 后端
# ─────────────────────────────────────────────────────────────

def create_claude_code_backends(
    output_dir: str,
    script_dir: str,
    components: dict = None,
) -> Tuple[Callable[[str], str], Callable[[str, str], str], Callable[[str, str], str]]:
    """
    创建 Claude Code SDK 后端的三种 completer。

    Args:
        output_dir: 输出目录（用于 MCP 组件数据导出）
        script_dir: 脚本目录（用于定位 MCP server 脚本）
        components: 组件字典（导出 MCP 数据用，doc_completer 不需要时可传 None）

    Returns:
        (cluster_completer, doc_completer, overview_completer)
    """
    from core.cluster_modules import (
        create_claude_code_completer,
        create_claude_code_doc_completer,
        create_claude_code_overview_completer,
    )

    # 聚类：无工具纯补全
    cluster_completer = create_claude_code_completer()

    # 文档生成：Write/Read 工具 + MCP read_code_components
    mcp_components_path = os.path.join(output_dir, "components_for_mcp.json")
    mcp_server_path = os.path.join(script_dir, "server", "mcp_component_server.py")

    if components:
        _export_components_for_mcp(components, mcp_components_path)
        logger.info(f"   MCP components: {mcp_components_path}")

    doc_completer = create_claude_code_doc_completer(
        mcp_server_name="code-components",
        mcp_server_command="python",
        mcp_server_args=[mcp_server_path, mcp_components_path],
    )

    # 概览：无工具纯补全
    overview_completer = create_claude_code_overview_completer()

    return cluster_completer, doc_completer, overview_completer


# ─────────────────────────────────────────────────────────────
# 统一入口
# ─────────────────────────────────────────────────────────────

def create_backends(
    backend: str,
    output_dir: str,
    script_dir: str,
    components: dict = None,
) -> Tuple[Callable[[str], str], Callable[[str, str], str], Callable[[str, str], str]]:
    """
    根据 backend 名称创建对应的三种 completer。

    Args:
        backend: "claude_code" 或 "openai"
        output_dir: 输出目录
        script_dir: 脚本目录
        components: 组件字典（MCP 导出用）

    Returns:
        (cluster_completer, doc_completer, overview_completer)
    """
    if backend == "claude_code":
        logger.info("   LLM Backend: Claude Code SDK (mimo-v2.5-pro) + MCP read_code_components")
        return create_claude_code_backends(output_dir, script_dir, components)
    else:
        logger.info("   LLM Backend: OpenAI API (mimo-v2.5-pro)")
        return create_openai_backends()


# ─────────────────────────────────────────────────────────────
# MCP 数据导出
# ─────────────────────────────────────────────────────────────

def _export_components_for_mcp(components: dict, output_path: str):
    """导出组件数据为 JSON，供 MCP 服务器读取"""
    result = {}
    for comp_id, comp in components.items():
        result[comp_id] = {
            "name": comp.name,
            "component_type": comp.component_type,
            "relative_path": comp.relative_path,
            "source_code": comp.source_code or "",
        }
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    logger.info(f"✓ Exported {len(result)} components for MCP")
