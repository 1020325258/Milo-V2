"""
模块聚类 — 对应 CodeWiki 的 codewiki/src/be/cluster_modules.py

核心流程：
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
import json
import logging
from typing import Dict, List, Any, Optional, Callable
from collections import defaultdict

import tiktoken

from models import Node

logger = logging.getLogger(__name__)

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

def _build_component_summary(comp: Node) -> str:
    """构建组件的简要摘要（依赖 + 行数 + Javadoc），帮助 LLM 理解职责"""
    parts = []

    # 行数
    if comp.start_line and comp.end_line:
        lines = comp.end_line - comp.start_line + 1
        parts.append(f"{lines} lines")

    # 依赖的其他组件
    if comp.depends_on:
        short_deps = [d.split("::")[-1] if "::" in d else d for d in sorted(comp.depends_on)]
        parts.append(f"depends on: {', '.join(short_deps)}")

    # Javadoc（取前 200 字符）
    if comp.docstring:
        doc = comp.docstring[:200].replace("\n", " ").strip()
        parts.append(f"doc: {doc}")

    return " | ".join(parts) if parts else ""


def format_potential_core_components(
    leaf_nodes: List[str], components: Dict[str, Node]
) -> tuple[str, str, str]:
    """
    将叶子节点按文件分组，生成三份文本：
    1. 纯列表（组件 ID）
    2. 带源码（组件 ID + 源代码）
    3. 带摘要（组件 ID + 依赖/行数/Javadoc）

    对应 CodeWiki 的同名函数。
    """
    valid_leaf_nodes = [n for n in leaf_nodes if n in components]

    leaf_nodes_by_file = defaultdict(list)
    for leaf_node in valid_leaf_nodes:
        leaf_nodes_by_file[components[leaf_node].relative_path].append(leaf_node)

    potential_core_components = ""
    potential_core_components_with_code = ""
    potential_core_components_with_summary = ""

    for file, nodes in sorted(leaf_nodes_by_file.items()):
        potential_core_components += f"# {file}\n"
        potential_core_components_with_code += f"# {file}\n"
        potential_core_components_with_summary += f"# {file}\n"
        for node_id in nodes:
            comp = components[node_id]
            potential_core_components += f"\t{node_id}\n"
            potential_core_components_with_code += f"\t{node_id}\n"
            potential_core_components_with_code += f"{comp.source_code}\n"
            # 带摘要的版本
            summary = _build_component_summary(comp)
            if summary:
                potential_core_components_with_summary += f"\t{node_id}  [{summary}]\n"
            else:
                potential_core_components_with_summary += f"\t{node_id}\n"

    return potential_core_components, potential_core_components_with_code, potential_core_components_with_summary


def get_clustering_input_token_count(
    leaf_nodes: List[str], components: Dict[str, Node]
) -> int:
    """计算聚类输入的 token 数"""
    _, with_code, _ = format_potential_core_components(leaf_nodes, components)
    return count_tokens(with_code)


# ─────────────────────────────────────────────────────────────
# Prompt 模板（对应 CodeWiki 的 prompt_template.py）
# ─────────────────────────────────────────────────────────────

CLUSTER_REPO_PROMPT = """以下是仓库中所有潜在核心组件的列表：
<POTENTIAL_CORE_COMPONENTS>
{potential_core_components}
</POTENTIAL_CORE_COMPONENTS>

请将这些组件分组，每组内的组件彼此紧密相关，共同构成一个模块。不要包含对仓库而言非核心的组件。

每个组件 ID 的格式为 `<文件路径>::<名称>`。请原样返回 ID，不要去掉 `<文件路径>::` 前缀，也不要将 ID 缩短为仅名称。

要求：
- 模块名必须使用英文，采用 PascalCase 命名（如 ContractCore、AuthModule）
- 不要使用中文作为模块名

请先分析组件之间的关系，然后进行分组，按以下格式返回结果：
<GROUPED_COMPONENTS>
{{
    "ModuleName1": {{
        "path": "<module_path>",
        "components": [
            "<component_id_1>",
            "<component_id_2>"
        ]
    }},
    "ModuleName2": {{
        "path": "<module_path>",
        "components": [
            "<component_id_1>",
            "<component_id_2>"
        ]
    }}
}}
</GROUPED_COMPONENTS>"""


CLUSTER_MODULE_PROMPT = """以下是仓库的模块树：

<MODULE_TREE>
{module_tree}
</MODULE_TREE>

以下是模块 {module_name} 中所有潜在核心组件的列表：
<POTENTIAL_CORE_COMPONENTS>
{potential_core_components}
</POTENTIAL_CORE_COMPONENTS>

请将这些组件分组，每组内的组件彼此紧密相关，共同构成一个更小的子模块。不要包含对该模块而言非核心的组件。

每个组件 ID 的格式为 `<文件路径>::<名称>`。请原样返回 ID，不要去掉 `<文件路径>::` 前缀，也不要将 ID 缩短为仅名称。

要求：
- 子模块名必须使用英文，采用 PascalCase 命名（如 DataValidation、PdfGenerator）
- 不要使用中文作为模块名

请先根据已有上下文分析组件之间的关系，然后进行分组，按以下格式返回结果：
<GROUPED_COMPONENTS>
{{
    "SubModuleName1": {{
        "path": "<module_path>",
        "components": [
            "<component_id_1>",
            "<component_id_2>"
        ]
    }},
    "SubModuleName2": {{
        "path": "<module_path>",
        "components": [
            "<component_id_1>",
            "<component_id_2>"
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

    两个分支对应递归聚类的两个阶段：
    - if not module_tree: 首次聚类（仓库级），只有组件列表，LLM 自由分组
    - else: 递归聚类（子模块级），额外传入已有模块树作为上下文，
            避免 LLM 把同一组件重复归类到不同模块
    """
    if not module_tree:
        # 首次聚类：没有已有模块树，只传组件列表
        return CLUSTER_REPO_PROMPT.format(
            potential_core_components=potential_core_components,
        )
    else:
        # 递归聚类：已有部分模块树，格式化为可读文本作为 LLM 上下文
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
    from claude_agent_sdk import query, AssistantMessage, ResultMessage

    # 打印 prompt
    logger.info(f"      📤 Prompt ({len(prompt)} chars):")
    for line in prompt.split("\n"):
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

        elif isinstance(message, ResultMessage):
            logger.info(f"      ✅ ResultMessage (stop_reason={message.stop_reason})")
            if message.total_cost_usd:
                logger.info(f"         💰 cost: ${message.total_cost_usd:.4f}")
            if message.result:
                result_text = message.result
                preview = result_text[:500] if len(result_text) > 500 else result_text
                logger.info(f"         📝 result: {preview}")

    return result_text


def create_claude_code_completer(  # 实际使用 claude_agent_sdk
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

    return module_tree


# ─────────────────────────────────────────────────────────────
# 核心聚类逻辑
# ─────────────────────────────────────────────────────────────

def cluster_modules(
    leaf_nodes: List[str],
    components: Dict[str, Node],
    max_token_per_module: int = 36_369,
    current_module_tree: dict = None,
    current_module_name: str = None,
    current_module_path: List[str] = None,
    completer: Callable[[str], str] = None,
) -> Dict[str, Any]:
    """
    递归聚类：将组件分组为层级模块树。

    流程：
    1. 格式化组件列表 + 源码
    2. 计算 token 量
    3. 如果 ≤ 阈值 → 不需要聚类，返回 {}
    4. 如果 > 阈值 → 调用 LLM 聚类
    5. 对每个子模块递归调用自身

    Args:
        leaf_nodes: 叶子节点 ID 列表
        components: 组件字典
        max_token_per_module: token 阈值（超过则需要聚类）
        current_module_tree: 当前已有的模块树（递归时用）
        current_module_name: 当前模块名（递归时用）
        current_module_path: 当前模块路径（递归时用）
        completer: LLM 补全函数 (prompt) -> str

    Returns:
        模块树 dict，格式：
        {
            "模块A": {
                "path": "src/a/",
                "components": ["comp1", "comp2"],
                "children": {}  # 递归子模块
            }
        }
        如果不需要聚类，返回 {}
    """
    if current_module_tree is None:
        current_module_tree = {}
    if current_module_path is None:
        current_module_path = []

    if completer is None:
        completer = create_claude_code_completer()

    # ── 1. 格式化组件 ──
    # with_summary: 组件 ID + 依赖/行数/Javadoc（发给 LLM 做聚类）
    # with_code:    组件 ID + 完整源码（仅用于计算 token 数）
    _, potential_core_components_with_code, potential_core_components_with_summary = (
        format_potential_core_components(leaf_nodes, components)
    )

    # ── 2. 计算 token ──
    input_tokens = count_tokens(potential_core_components_with_code)
    module_label = current_module_name or "repository"

    logger.info(
        "Module clustering input for %s: %d leaf nodes, %d tokens, threshold %d",
        module_label, len(leaf_nodes), input_tokens, max_token_per_module,
    )

    # ── 3. 判断是否需要聚类 ──
    if input_tokens <= max_token_per_module:
        logger.info(
            "Skipping LLM clustering for %s (%d tokens ≤ %d threshold)",
            module_label, input_tokens, max_token_per_module,
        )
        return {}

    # ── 4. 调用 LLM 聚类 ──
    # 使用带摘要的版本，让 LLM 看到依赖/行数/Javadoc，更好地理解组件职责
    prompt = format_cluster_prompt(
        potential_core_components_with_summary, current_module_tree, current_module_name
    )

    logger.info("Requesting LLM clustering for %s...", module_label)
    response = completer(prompt)

    # ── 5. 解析响应 ──
    module_tree = parse_cluster_response(response)

    if module_tree is None:
        logger.warning("Clustering failed for %s, falling back to whole-module", module_label)
        return {}

    if len(module_tree) <= 1:
        logger.info(
            "LLM returned ≤1 module for %s, skipping clustering", module_label
        )
        return {}

    logger.info(
        "LLM clustering for %s produced %d top-level modules: %s",
        module_label, len(module_tree), list(module_tree.keys()),
    )

    # ── 6. 合并到总模块树 ──
    if not current_module_tree:
        # 首次聚类：直接用 LLM 返回的模块树初始化
        current_module_tree = module_tree
    else:
        # 递归聚类：把新的子模块树合并到已有树的对应位置
        # current_module_path 指向当前正在递归的父模块路径，如 ["ContractCore"]
        value = current_module_tree
        for key in current_module_path:
            # 确保 children 字段存在（递归时可能还没设置）
            if "children" not in value[key]:
                value[key]["children"] = {}
            value = value[key]["children"]
        for name, info in module_tree.items():
            info.pop("path", None)
            value[name] = info

    # ── 7. 递归聚类每个子模块 ──
    for module_name, module_info in module_tree.items():
        sub_leaf_nodes = module_info.get("components", [])
        valid_sub_nodes = [n for n in sub_leaf_nodes if n in components]

        current_module_path.append(module_name)
        module_info["children"] = cluster_modules(
            valid_sub_nodes,
            components,
            max_token_per_module,
            current_module_tree,
            module_name,
            current_module_path,
            completer,
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
