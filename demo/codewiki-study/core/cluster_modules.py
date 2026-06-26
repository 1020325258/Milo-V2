"""
模块聚类 — 对应 CodeWiki 的 codewiki/src/be/cluster_modules.py

核心流程（递归 LLM 分割）：
1. 将叶子节点按文件分组，格式化为文本
2. 计算 token 量，判断是否超过阈值
3. 超过阈值 → 调用 LLM 将组件聚类为模块树
4. 递归聚类：对每个子模块重复步骤 1-3，直到 token 在阈值内
5. 输出：层级模块树 dict

LLM 调用：
- 默认使用 Claude Agent SDK（mimo-v2.5-pro）
- 可配置 base_url / auth_token / model
"""

import os
import re
import json
import logging
from typing import Dict, List, Any, Optional, Callable
from collections import defaultdict

import tiktoken

from core.models import Node

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 模块名清洗
# ─────────────────────────────────────────────────────────────

def sanitize_module_name(name: str) -> str:
    """将模块名转为文件名安全的 snake_case。

    例：
        "Contract PDF Generation" → "contract_pdf_generation"
        "Personal Relation & Signing" → "personal_relation_signing"
        "Contract-Context-Handler" → "contract_context_handler"
    """
    name = name.strip()
    # 空格、横杠 → 下划线
    name = re.sub(r'[\s-]+', '_', name)
    # 移除特殊字符（保留中英文、数字、下划线）
    name = re.sub(r'[^a-zA-Z0-9一-鿿_]', '', name)
    # 合并连续下划线
    name = re.sub(r'_+', '_', name)
    # 去首尾下划线，小写化
    return name.strip('_').lower()


def sanitize_module_tree_keys(tree: dict) -> dict:
    """递归清洗模块树中所有 dict key（模块名）为 snake_case。"""
    sanitized = {}
    for key, value in tree.items():
        new_key = sanitize_module_name(key)
        if isinstance(value, dict):
            # 递归清洗 children
            if "children" in value and isinstance(value["children"], dict):
                value["children"] = sanitize_module_tree_keys(value["children"])
            sanitized[new_key] = value
        else:
            sanitized[new_key] = value
    return sanitized


# ─────────────────────────────────────────────────────────────
# Token 计数
# ─────────────────────────────────────────────────────────────

_enc = tiktoken.encoding_for_model("gpt-4")


def count_tokens(text: str) -> int:
    """计算文本的 token 数（使用 GPT-4 tokenizer）"""
    return len(_enc.encode(text))


# ─────────────────────────────────────────────────────────────
# 组件格式化
# ─────────────────────────────────────────────────────────────

def format_potential_core_components(
    leaf_nodes: List[str], components: Dict[str, Node]
) -> tuple[str, str]:
    """
    将叶子节点按文件分组，生成两份文本：
    1. 纯列表（组件 ID）
    2. 带源码（组件 ID + 源代码）

    对应 CodeWiki 的同名函数。
    """
    valid_leaf_nodes = [n for n in leaf_nodes if n in components]

    leaf_nodes_by_file = defaultdict(list)
    for leaf_node in valid_leaf_nodes:
        leaf_nodes_by_file[components[leaf_node].relative_path].append(leaf_node)

    potential_core_components = ""
    potential_core_components_with_code = ""

    for file, nodes in sorted(leaf_nodes_by_file.items()):
        potential_core_components += f"# {file}\n"
        potential_core_components_with_code += f"# {file}\n"
        for node_id in nodes:
            comp = components[node_id]
            potential_core_components += f"\t{node_id}\n"
            potential_core_components_with_code += f"\t{node_id}\n"
            potential_core_components_with_code += f"{comp.source_code}\n"

    return potential_core_components, potential_core_components_with_code


def get_clustering_input_token_count(
    leaf_nodes: List[str], components: Dict[str, Node]
) -> int:
    """计算聚类输入的 token 数"""
    _, with_code = format_potential_core_components(leaf_nodes, components)
    return count_tokens(with_code)


# ─────────────────────────────────────────────────────────────
# Prompt 模板（对应 CodeWiki 的 prompt_template.py）
# ─────────────────────────────────────────────────────────────

CLUSTER_REPO_PROMPT = """Here is list of all potential core components of the repository (It's normal that some components are not essential to the repository):
<POTENTIAL_CORE_COMPONENTS>
{potential_core_components}
</POTENTIAL_CORE_COMPONENTS>

Please group the components into groups such that each group is a set of components that are closely related to each other and together they form a module. DO NOT include components that are not essential to the repository.

Each component ID has the form `<file_path>::<name>`. Return the IDs EXACTLY as given — do NOT strip the `<file_path>::` prefix or shorten the ID to the bare name.

IMPORTANT: Module names MUST use snake_case format (lowercase English letters, words separated by underscores). No spaces, no hyphens, no special characters. Examples: contract_context_handler, contract_pdf_generation, personal_relation_signing.

Firstly reason about the components and then group them and return the result in the following format:
<GROUPED_COMPONENTS>
{{
    "module_name_1": {{
        "path": "<path_to_the_module_1>",
        "components": [
            "<component_name_1>",
            "<component_name_2>"
        ]
    }},
    "module_name_2": {{
        "path": "<path_to_the_module_2>",
        "components": [
            "<component_name_1>",
            "<component_name_2>"
        ]
    }}
}}
</GROUPED_COMPONENTS>"""


CLUSTER_MODULE_PROMPT = """Here is the module tree of a repository:

<MODULE_TREE>
{module_tree}
</MODULE_TREE>

Here is list of all potential core components of the module {module_name} (It's normal that some components are not essential to the module):
<POTENTIAL_CORE_COMPONENTS>
{potential_core_components}
</POTENTIAL_CORE_COMPONENTS>

Please group the components into groups such that each group is a set of components that are closely related to each other and together they form a smaller module. DO NOT include components that are not essential to the module.

Each component ID has the form `<file_path>::<name>`. Return the IDs EXACTLY as given — do NOT strip the `<file_path>::` prefix or shorten the ID to the bare name.

IMPORTANT: Module names MUST use snake_case format (lowercase English letters, words separated by underscores). No spaces, no hyphens, no special characters. Examples: contract_context_handler, contract_pdf_generation, personal_relation_signing.

Firstly reason based on given context and then group them and return the result in the following format:
<GROUPED_COMPONENTS>
{{
    "module_name_1": {{
        "path": "<path_to_the_module_1>",
        "components": [
            "<component_name_1>",
            "<component_name_2>"
        ]
    }},
    "module_name_2": {{
        "path": "<path_to_the_module_2>",
        "components": [
            "<component_name_1>",
            "<component_name_2>"
        ]
    }}
}}
</GROUPED_COMPONENTS>"""


def format_cluster_prompt(
    potential_core_components: str,
    module_tree: dict = None,
    module_name: str = None,
) -> str:
    """格式化聚类 Prompt。

    对应 CodeWiki 的 prompt_template.format_cluster_prompt()：
    - module_tree 为空 → 首次聚类（仓库级），用 CLUSTER_REPO_PROMPT
    - module_tree 非空 → 递归聚类（子模块级），用 CLUSTER_MODULE_PROMPT + 已有模块树上下文
    """
    if not module_tree:
        return CLUSTER_REPO_PROMPT.format(
            potential_core_components=potential_core_components,
        )
    else:
        # 格式化已有的模块树为可读文本
        lines = []

        def _format_tree(tree, indent=0):
            for key, value in tree.items():
                if key == module_name:
                    lines.append(f"{'  ' * indent}{key} (current module)")
                else:
                    lines.append(f"{'  ' * indent}{key}")

                by_file = defaultdict(list)
                for c in value.get("components", []):
                    if "::" in c:
                        fpath, name = c.split("::", 1)
                        by_file[fpath].append(name)
                    else:
                        by_file[""].append(c)
                for fpath, names in by_file.items():
                    prefix = f"{fpath}: " if fpath else ""
                    lines.append(f"{'  ' * (indent + 1)} {prefix}{', '.join(names)}")

                children = value.get("children", {})
                if isinstance(children, dict) and len(children) > 0:
                    lines.append(f"{'  ' * (indent + 1)} Children:")
                    _format_tree(children, indent + 2)

        _format_tree(module_tree)
        formatted_tree = "\n".join(lines)

        return CLUSTER_MODULE_PROMPT.format(
            potential_core_components=potential_core_components,
            module_tree=formatted_tree,
            module_name=module_name,
        )


# ─────────────────────────────────────────────────────────────
# LLM 调用
# ─────────────────────────────────────────────────────────────

def create_openai_completer(
    base_url: str = None,
    api_key: str = None,
    model: str = None,
) -> Callable[[str], str]:
    """
    创建 OpenAI 兼容 API 补全函数。

    直接调用 HTTP API，无 CLI 子进程开销，速度快。
    适用于小米 mimo token plan、vLLM、Ollama 等 OpenAI 兼容服务。

    Args:
        base_url: API 地址
        api_key: API Key
        model: 模型名

    Returns:
        completer: (prompt: str) -> str 的函数
    """
    from openai import OpenAI

    _base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
    _api_key = api_key or os.getenv("OPENAI_API_KEY", "tp-cxq9g672kqgmcpmgvzhktpk7vucswrn9atq4i4ehwyxc6ngl")
    _model = model or os.getenv("OPENAI_MODEL", "mimo-v2.5-pro")

    client = OpenAI(base_url=_base_url, api_key=_api_key)

    def completer(prompt: str) -> str:
        response = client.chat.completions.create(
            model=_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=8192,
        )
        result = response.choices[0].message.content
        logger.info(f"      ✅ OpenAI response: {response.usage.total_tokens} tokens, model={response.model}")
        return result

    return completer


# ─────────────────────────────────────────────────────────────
# Claude Code SDK 公共逻辑
# ─────────────────────────────────────────────────────────────

def _get_sdk_config():
    """获取 Claude Code SDK 的公共配置"""
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage
    base_url = os.getenv("ANTHROPIC_BASE_URL", "https://token-plan-cn.xiaomimimo.com/anthropic")
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN", "tp-cxq9g672kqgmcpmgvzhktpk7vucswrn9atq4i4ehwyxc6ngl")
    model = os.getenv("ANTHROPIC_MODEL", "mimo-v2.5-pro")
    return query, ClaudeAgentOptions, AssistantMessage, ResultMessage, base_url, auth_token, model


async def _stream_sdk_messages(prompt, options):
    """
    公共的消息流处理：打印 prompt → 流式处理消息 → 返回最终文本。

    所有 Claude Code SDK 调用都通过此函数，统一日志格式。
    """
    from claude_agent_sdk import query, AssistantMessage, UserMessage, ResultMessage

    # 打印 prompt（前100行 + 后100行，中间省略）
    logger.info(f"      📤 Prompt ({len(prompt)} chars, {len(prompt.splitlines())} lines):")
    lines = prompt.split("\n")
    HEAD, TAIL = 100, 100
    if len(lines) <= HEAD + TAIL:
        for line in lines:
            logger.info(f"         {line}")
    else:
        for line in lines[:HEAD]:
            logger.info(f"         {line}")
        logger.info(f"         ... ({len(lines) - HEAD - TAIL} lines omitted) ...")
        for line in lines[-TAIL:]:
            logger.info(f"         {line}")

    result_text = ""
    turn = 0

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            turn += 1
            logger.info(f"      🤖 [Turn {turn}] model={message.model}")
            for block in message.content:
                if hasattr(block, "text") and block.text:
                    text = block.text
                    if len(text) > 500:
                        logger.info(f"         💬 {text[:500]}...")
                    else:
                        logger.info(f"         💬 {text}")
                elif hasattr(block, "name"):
                    tool_input = json.dumps(block.input, ensure_ascii=False)[:500] if hasattr(block, "input") and block.input else ""
                    logger.info(f"         🔧 tool_use: {block.name}({tool_input})")
                elif hasattr(block, "thinking"):
                    logger.info(f"         💭 {block.thinking}")
                else:
                    block_type = type(block).__name__
                    logger.info(f"         ❓ {block_type}")

        elif isinstance(message, UserMessage):
            # 工具返回结果
            tool_result = message.tool_use_result
            if tool_result and isinstance(tool_result, dict):
                is_error = tool_result.get("is_error", False)
                icon = "❌" if is_error else "📥"
                content = tool_result.get("content", "")
                if isinstance(content, str):
                    preview = content[:500] + "..." if len(content) > 500 else content
                elif isinstance(content, list):
                    # 多个 ToolResultBlock
                    parts = []
                    for item in content:
                        if isinstance(item, dict):
                            c = item.get("content", "")
                            if isinstance(c, str):
                                parts.append(c[:200])
                            else:
                                parts.append(str(c)[:200])
                        else:
                            parts.append(str(item)[:200])
                    preview = " | ".join(parts)
                    if len(preview) > 500:
                        preview = preview[:500] + "..."
                else:
                    preview = str(content)[:500]
                logger.info(f"      {icon} tool_result: {preview}")
            elif tool_result:
                # tool_result 是 str 或其他非 dict 类型（SDK 异常）
                preview = str(tool_result)[:500]
                logger.info(f"      📥 tool_result (raw): {preview}")

        elif isinstance(message, ResultMessage):
            logger.info(f"      ✅ ResultMessage (stop_reason={message.stop_reason})")
            if message.total_cost_usd:
                logger.info(f"         💰 cost: ${message.total_cost_usd:.4f}")
            if message.result:
                result_text = message.result
                preview = result_text[:500] if len(result_text) > 500 else result_text
                logger.info(f"         📝 result: {preview}")

    return result_text


def create_claude_code_completer(
    base_url: str = None,
    auth_token: str = None,
    model: str = None,
    max_turns: int = 50,
) -> Callable[[str], str]:
    """创建 Claude Agent SDK 补全函数（聚类用，单 prompt）"""
    import asyncio
    from claude_agent_sdk import ClaudeAgentOptions

    _, _, _, _, _def_base, _def_auth, _def_model = _get_sdk_config()
    _base_url = base_url or _def_base
    _auth_token = auth_token or _def_auth
    _model = model or _def_model

    def completer(prompt: str) -> str:
        options = ClaudeAgentOptions(
            model=_model,
            env={"ANTHROPIC_BASE_URL": _base_url, "ANTHROPIC_AUTH_TOKEN": _auth_token},
            tools=[],
            allowed_tools=[],
            max_turns=max_turns,
        )
        try:
            return asyncio.run(_stream_sdk_messages(prompt, options))
        except Exception as e:
            error_msg = str(e)
            if "maximum number of turns" in error_msg.lower():
                logger.warning(f"      ⚠️ 达到 max_turns({max_turns}) 限制，任务未完成")
            else:
                logger.warning(f"      ⚠️ Claude Code SDK 调用失败: {error_msg}")
            return ""

    return completer


def create_claude_code_doc_completer(
    base_url: str = None,
    auth_token: str = None,
    model: str = None,
    max_turns: int = 50,
    mcp_server_name: str = None,
    mcp_server_command: str = None,
    mcp_server_args: list = None,
) -> Callable[[str, str], str]:
    """创建 Claude Agent SDK 文档生成补全函数（system + user 双 prompt，支持 MCP）"""
    import asyncio
    from claude_agent_sdk import ClaudeAgentOptions

    _, _, _, _, _def_base, _def_auth, _def_model = _get_sdk_config()
    _base_url = base_url or _def_base
    _auth_token = auth_token or _def_auth
    _model = model or _def_model

    # 构建 MCP 服务器配置
    _mcp_servers = {}
    if mcp_server_name and mcp_server_command:
        _mcp_servers[mcp_server_name] = {
            "command": mcp_server_command,
            "args": mcp_server_args or [],
        }
        logger.info(f"   MCP server configured: {mcp_server_name} -> {mcp_server_command}")

    def completer(system_prompt: str, user_prompt: str) -> str:
        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"
        options = ClaudeAgentOptions(
            model=_model,
            env={"ANTHROPIC_BASE_URL": _base_url, "ANTHROPIC_AUTH_TOKEN": _auth_token},
            allowed_tools=["Write", "Read"],
            permission_mode="bypassPermissions",
            mcp_servers=_mcp_servers,
            max_turns=max_turns,
        )
        try:
            return asyncio.run(_stream_sdk_messages(full_prompt, options))
        except Exception as e:
            error_msg = str(e)
            if "maximum number of turns" in error_msg.lower():
                logger.warning(f"      ⚠️ 达到 max_turns({max_turns}) 限制，任务未完成")
            else:
                logger.warning(f"      ⚠️ Claude Code SDK 调用失败: {error_msg}")
            return ""

    return completer


def create_claude_code_overview_completer(
    base_url: str = None,
    auth_token: str = None,
    model: str = None,
    max_turns: int = 3,
) -> Callable[[str, str], str]:
    """
    创建概览文档生成用的补全函数（无工具，纯补全）。

    对应 CodeWiki 的 backend.complete()：概览只需汇总已有文档，不需要探索文件系统。
    不给 Agent 任何工具，避免它自发去 Read/Write/Bash 探索。
    """
    import asyncio
    from claude_agent_sdk import ClaudeAgentOptions

    _, _, _, _, _def_base, _def_auth, _def_model = _get_sdk_config()
    _base_url = base_url or _def_base
    _auth_token = auth_token or _def_auth
    _model = model or _def_model

    def completer(system_prompt: str, user_prompt: str) -> str:
        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"
        options = ClaudeAgentOptions(
            model=_model,
            env={"ANTHROPIC_BASE_URL": _base_url, "ANTHROPIC_AUTH_TOKEN": _auth_token},
            allowed_tools=[],
            max_turns=max_turns,
        )
        try:
            return asyncio.run(_stream_sdk_messages(full_prompt, options))
        except Exception as e:
            logger.warning(f"      ⚠️ 概览生成失败: {str(e)}")
            return ""

    return completer


# ─────────────────────────────────────────────────────────────
# 聚类响应解析
# ─────────────────────────────────────────────────────────────

def parse_cluster_response(response: str) -> Optional[Dict[str, Any]]:
    """
    从 LLM 响应中提取 <GROUPED_COMPONENTS> 标签内的 JSON。

    Returns:
        解析后的 dict，或 None（解析失败）
    """
    if "<GROUPED_COMPONENTS>" not in response or "</GROUPED_COMPONENTS>" not in response:
        logger.warning("LLM response missing <GROUPED_COMPONENTS> tags")
        return None

    content = response.split("<GROUPED_COMPONENTS>")[1].split("</GROUPED_COMPONENTS>")[0].strip()

    try:
        module_tree = json.loads(content)
    except json.JSONDecodeError:
        # 兜底：尝试 eval（CodeWiki 原始代码用的 eval）
        try:
            module_tree = eval(content)
        except Exception as e:
            logger.warning(f"Failed to parse cluster response: {e}")
            return None

    if not isinstance(module_tree, dict):
        logger.warning(f"Expected dict, got {type(module_tree)}")
        return None

    return sanitize_module_tree_keys(module_tree)


# ─────────────────────────────────────────────────────────────
# 核心聚类逻辑（递归 LLM 分割，对应 CodeWiki 原始方案）
# ─────────────────────────────────────────────────────────────

def cluster_modules(
    leaf_nodes: List[str],
    components: Dict[str, Node],
    max_token_per_module: int = 36_369,
    current_module_tree: dict = None,
    current_module_name: str = None,
    current_module_path: List[str] = None,
    completer: Callable[[str], str] = None,
    output_dir: str = None,
) -> Dict[str, Any]:
    """
    递归 LLM 分割聚类：将组件分组为层级模块树。

    流程：
    1. 将叶子节点按文件分组，拼接为文本
    2. 计算 token 数
    3. token ≤ 阈值 → 返回 {}（跳过聚类，整体作为一个模块）
    4. token > 阈值 → 调 LLM 分组
    5. 结果 ≤1 个模块 → 返回 {}
    6. 递归：对每个子模块重复 1-5

    Args:
        leaf_nodes: 叶子节点 ID 列表
        components: 组件字典
        max_token_per_module: token 阈值，超过则触发 LLM 聚类
        current_module_tree: 当前已有的模块树（递归时传入）
        current_module_name: 当前模块名（递归时传入）
        current_module_path: 当前模块路径（递归时传入）
        completer: LLM 补全函数 (prompt) -> str
        output_dir: 未使用，保留兼容

    Returns:
        模块树 dict，格式：
        {
            "ModuleName": {
                "path": "...",
                "components": ["file::Class.method", ...],
                "children": {}
            }
        }
    """
    if current_module_tree is None:
        current_module_tree = {}
    if current_module_path is None:
        current_module_path = []

    if completer is None:
        completer = create_claude_code_completer()

    # ── Step 1: 拼接组件文本 ──
    potential_core_components, potential_core_components_with_code = (
        format_potential_core_components(leaf_nodes, components)
    )

    # ── Step 2: 计算 token ──
    input_tokens = count_tokens(potential_core_components_with_code)
    module_label = current_module_name or "repository"

    logger.info(
        "Module clustering input for %s: %d leaf nodes, %d tokens, threshold %d",
        module_label,
        len(leaf_nodes),
        input_tokens,
        max_token_per_module,
    )

    # ── Step 3: token 在阈值内，跳过聚类 ──
    if input_tokens <= max_token_per_module:
        logger.info(
            "Skipping LLM module clustering for %s because %d tokens fit within the "
            "%d-token threshold; using whole-module documentation mode.",
            module_label,
            input_tokens,
            max_token_per_module,
        )
        return {}

    # ── Step 4: 超过阈值，调 LLM 聚类 ──
    prompt = format_cluster_prompt(
        potential_core_components, current_module_tree, current_module_name
    )
    logger.info(
        "Requesting LLM module clustering for %s because %d tokens exceed the %d-token threshold.",
        module_label,
        input_tokens,
        max_token_per_module,
    )

    response = completer(prompt)

    # ── Step 5: 解析响应 ──
    try:
        if "<GROUPED_COMPONENTS>" not in response or "</GROUPED_COMPONENTS>" not in response:
            logger.warning(
                "Invalid LLM clustering response for %s: missing <GROUPED_COMPONENTS> "
                "tags; falling back to whole-module documentation. Response preview: %s...",
                module_label,
                response[:200],
            )
            return {}

        response_content = response.split("<GROUPED_COMPONENTS>")[1].split("</GROUPED_COMPONENTS>")[0]

        # 先尝试 json.loads，失败再 eval（与 CodeWiki 原始代码一致）
        try:
            module_tree = json.loads(response_content)
        except json.JSONDecodeError:
            module_tree = eval(response_content)

        if not isinstance(module_tree, dict):
            logger.error(f"Invalid module tree format - expected dict, got {type(module_tree)}")
            return {}

        module_tree = sanitize_module_tree_keys(module_tree)

    except Exception as e:
        logger.warning(
            "Failed to parse LLM clustering response for %s; falling back to "
            "whole-module documentation. Error: %s. Response preview: %s...",
            module_label,
            e,
            response[:200],
        )
        return {}

    # ── Step 6: 检查结果有效性 ──
    if len(module_tree) <= 1:
        logger.info(
            "Skipping LLM clustering result for %s because it produced only "
            "%d module(s); using whole-module documentation mode.",
            module_label,
            len(module_tree),
        )
        return {}

    logger.info(
        "LLM module clustering for %s produced %d top-level modules.",
        module_label,
        len(module_tree),
    )

    # ── 合并到当前模块树 ──
    if current_module_tree == {}:
        current_module_tree = module_tree
    else:
        value = current_module_tree
        for key in current_module_path:
            value = value[key]["children"]
        for module_name, module_info in module_tree.items():
            if "path" in module_info:
                del module_info["path"]
            value[module_name] = module_info

    # ── Step 7: 递归聚类子模块 ──
    for module_name, module_info in module_tree.items():
        sub_leaf_nodes = module_info.get("components", [])

        # 过滤无效节点
        valid_sub_leaf_nodes = [n for n in sub_leaf_nodes if n in components]

        current_module_path.append(module_name)
        module_info["children"] = {}
        module_info["children"] = cluster_modules(
            valid_sub_leaf_nodes,
            components,
            max_token_per_module,
            current_module_tree,
            module_name,
            current_module_path,
            completer=completer,
        )
        current_module_path.pop()

    return module_tree


# ─────────────────────────────────────────────────────────────
# 打印模块树
# ─────────────────────────────────────────────────────────────

def print_module_tree(module_tree: Dict[str, Any], components: Dict[str, Node], indent: int = 0):
    """递归打印模块树"""
    prefix = "  " * indent
    for module_name, module_info in module_tree.items():
        comp_ids = module_info.get("components", [])
        children = module_info.get("children", {})

        # 统计模块内的组件类型
        type_counts = defaultdict(int)
        for cid in comp_ids:
            if cid in components:
                type_counts[components[cid].component_type] += 1

        type_str = ", ".join(f"{t}:{c}" for t, c in sorted(type_counts.items()))
        print(f"{prefix}📁 {module_name}  ({len(comp_ids)} components: {type_str})")

        # 列出组件
        for cid in comp_ids:
            if cid in components:
                comp = components[cid]
                short = cid.split("::")[-1] if "::" in cid else cid
                print(f"{prefix}  • {short} ({comp.component_type})")

        # 递归子模块
        if children:
            print_module_tree(children, components, indent + 1)
