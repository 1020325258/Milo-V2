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

    # 打印 prompt（日志中截断 AVAILABLE_COMPONENTS 部分，避免日志膨胀）
    logger.info(f"      📤 Prompt ({len(prompt)} chars):")
    in_available = False
    line_count = 0
    MAX_LOG_LINES = 500
    for line in prompt.split("\n"):
        if "<AVAILABLE_COMPONENTS>" in line:
            in_available = True
        if in_available and "</AVAILABLE_COMPONENTS>" in line:
            in_available = False
            logger.info(f"         ... (AVAILABLE_COMPONENTS 已省略)")
            logger.info(f"         {line}")
            continue
        if in_available:
            line_count += 1
            if line_count <= 20:
                logger.info(f"         {line}")
            elif line_count == 21:
                logger.info(f"         ... (省略剩余行)")
            continue
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
            allowed_tools=[],   # 不给任何工具，与 CodeWiki 的 complete() 一致
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
    output_dir: str = None,
) -> Dict[str, Any]:
    """
    聚类：将组件分组为层级模块树。

    方案 B 流程（类级摘要 + 业务概念 + 依赖图预聚类）：
    1. 聚合方法级组件 → 类级摘要
    2. 提取业务概念（OpenAI 批量调用）
    3. 依赖图预聚类（networkx 社区检测）
    4. 基于业务概念 + 预聚类的 LLM 聚类
    5. 映射回方法级 ID

    Args:
        leaf_nodes: 叶子节点 ID 列表
        components: 组件字典
        max_token_per_module: token 阈值（当前未使用，保留兼容）
        current_module_tree: 当前已有的模块树（当前未使用）
        current_module_name: 当前模块名（当前未使用）
        current_module_path: 当前模块路径（当前未使用）
        completer: LLM 补全函数 (prompt) -> str（OpenAI 用于聚类）
        output_dir: 中间结果保存目录（None 则不保存）

    Returns:
        模块树 dict，格式：
        {
            "模块A": {
                "components": ["file::Class.method1", "file::Class.method2", ...],
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

    module_label = current_module_name or "repository"

    # ── Step 1: 聚合为类级摘要 ──
    logger.info("  📊 Step 1: 聚合方法级组件 → 类级摘要")
    class_summaries = build_class_summaries(components)
    logger.info(f"    {len(components)} 个组件 → {len(class_summaries)} 个类")

    if output_dir:
        save_intermediate_result(class_summaries, "class_summaries.json", output_dir)

    # ── Step 2: 提取业务概念 ──
    logger.info("  🏷️  Step 2: 从类源码中提取业务概念")
    business_concepts = extract_business_concepts(class_summaries, completer, batch_size=10)
    logger.info(f"    提取到 {len(business_concepts)} 个类的业务概念")

    if output_dir:
        save_intermediate_result(business_concepts, "business_concepts.json", output_dir)

    # ── Step 3: 依赖图预聚类 ──
    logger.info("  🔗 Step 3: 依赖图预聚类")
    pre_clusters = precluster_by_dependency_graph(class_summaries, components)

    if output_dir:
        save_intermediate_result(pre_clusters, "pre_clusters.json", output_dir)

    # ── Step 4: 基于业务概念的 LLM 聚类 ──
    logger.info("  🤖 Step 4: 基于业务概念的 LLM 聚类")
    class_clusters = cluster_with_business_concepts(
        class_summaries, business_concepts, pre_clusters, completer
    )

    if not class_clusters:
        logger.warning(f"  ⚠️ 聚类失败，使用预聚类结果作为兜底")
        class_clusters = pre_clusters

    if not class_clusters:
        logger.warning(f"  ⚠️ 预聚类也为空，跳过聚类")
        return {}

    if output_dir:
        save_intermediate_result(class_clusters, "class_clusters.json", output_dir)

    # ── Step 5: 映射回方法级 ID ──
    logger.info("  🔄 Step 5: 映射回方法级组件 ID")
    module_tree = map_classes_to_method_ids(class_clusters, class_summaries, components)

    if output_dir:
        save_intermediate_result(module_tree, "module_tree.json", output_dir)

    logger.info(f"  ✅ 聚类完成: {len(module_tree)} 个模块")
    for name, info in sorted(module_tree.items(), key=lambda x: -len(x[1].get("components", []))):
        logger.info(f"    {name} ({len(info['components'])} 个组件)")

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


# ═══════════════════════════════════════════════════════════════
#  方案 B：类级摘要 + 业务概念提取 + 依赖图预聚类
# ═══════════════════════════════════════════════════════════════


# ─────────────────────────────────────────────────────────────
# Step 1: 聚合方法级组件 → 类级摘要
# ─────────────────────────────────────────────────────────────

def build_class_summaries(components: Dict[str, Node]) -> Dict[str, dict]:
    """
    将方法级组件聚合为类级摘要。

    输入：886 个组件（56 类 + 830 方法）
    输出：56 个类级摘要

    每个摘要包含：
      - class_name: 类名
      - file_path: 文件绝对路径
      - relative_path: 相对路径
      - methods: 方法名列表
      - total_lines: 所有方法行数之和
      - depends_on: 所有方法的依赖取并集（类名级别）
      - key_methods: 行数最大的 5 个方法名
      - source_code_head: 源码前 N 字符（用于 LLM 提取业务概念）
    """
    classes: Dict[str, dict] = {}

    for comp_id, comp in components.items():
        short = comp_id.split("::")[-1] if "::" in comp_id else comp_id

        # 判断是类还是方法
        if "." in short:
            class_name = short.split(".")[0]
            method_name = short.split(".")[-1]
        else:
            class_name = short
            method_name = None

        class_key = f"{comp.relative_path}::{class_name}"

        if class_key not in classes:
            classes[class_key] = {
                "class_name": class_name,
                "file_path": comp.file_path,
                "relative_path": comp.relative_path,
                "methods": [],
                "total_lines": 0,
                "depends_on": set(),
                "best_doc": "",
                "source_code_head": "",
            }

        info = classes[class_key]

        if method_name is None:
            # 类级组件：记录源码头部（用于业务概念提取）
            code = comp.source_code or ""
            info["source_code_head"] = code[:2000]
            if comp.docstring and len(comp.docstring) > len(info["best_doc"]):
                info["best_doc"] = comp.docstring
        else:
            # 方法级组件
            info["methods"].append(method_name)
            if comp.start_line and comp.end_line:
                info["total_lines"] += comp.end_line - comp.start_line + 1
            if comp.depends_on:
                for dep in comp.depends_on:
                    # 提取类名（去掉方法名部分）
                    dep_short = dep.split("::")[-1] if "::" in dep else dep
                    dep_class = dep_short.split(".")[0]
                    info["depends_on"].add(dep_class)

    # 后处理：取 key_methods、转 set 为 list
    for info in classes.values():
        # key_methods：取行数最大的 5 个方法
        # 这里简单取前 5 个，因为方法没有行数信息
        info["key_methods"] = info["methods"][:5]
        info["depends_on"] = sorted(info["depends_on"])
        info["method_count"] = len(info["methods"])

    return classes


# ─────────────────────────────────────────────────────────────
# Step 2: 从类源码中提取业务概念（OpenAI 批量调用）
# ─────────────────────────────────────────────────────────────

EXTRACT_CONCEPTS_PROMPT = """请从以下 Java 类的源码中，提取每个类的业务领域和业务概念。

<CLASSES>
{classes_text}
</CLASSES>

对每个类，请分析：
1. **业务领域**（domain）：该类属于哪个业务子系统，用 2-6 个字概括（如"合同提交"、"PDF生成"、"签约管理"）
2. **业务概念**（concepts）：该类涉及的 3-5 个关键业务概念，用简短的中文词组

请严格按以下 JSON 格式返回，不要添加任何其他内容：
{{
    "ClassName1": {{
        "domain": "业务领域",
        "concepts": ["概念1", "概念2", "概念3"]
    }},
    "ClassName2": {{
        "domain": "业务领域",
        "concepts": ["概念1", "概念2"]
    }}
}}"""


def _format_class_for_extraction(class_info: dict) -> str:
    """格式化单个类的信息，用于 LLM 提取业务概念"""
    parts = [f"## {class_info['class_name']} ({class_info['relative_path']})"]
    parts.append(f"方法数: {class_info['method_count']}, 总行数: {class_info['total_lines']}")
    if class_info["depends_on"]:
        parts.append(f"依赖: {', '.join(class_info['depends_on'][:10])}")
    if class_info["key_methods"]:
        parts.append(f"关键方法: {', '.join(class_info['key_methods'])}")
    if class_info["source_code_head"]:
        parts.append(f"源码:\n```java\n{class_info['source_code_head']}\n```")
    return "\n".join(parts)


def extract_business_concepts(
    class_summaries: Dict[str, dict],
    completer: Callable[[str], str],
    batch_size: int = 10,
) -> Dict[str, dict]:
    """
    批量调用 OpenAI 从类源码中提取业务概念。

    Args:
        class_summaries: build_class_summaries() 的输出
        completer: OpenAI completer (prompt) -> str
        batch_size: 每批处理的类数量

    Returns:
        {class_name: {"domain": "...", "concepts": [...]}}
    """
    all_concepts = {}
    class_items = list(class_summaries.items())

    for i in range(0, len(class_items), batch_size):
        batch = class_items[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(class_items) + batch_size - 1) // batch_size

        logger.info(f"    提取业务概念: 批次 {batch_num}/{total_batches} ({len(batch)} 个类)")

        # 格式化批次内容
        classes_text = "\n\n".join(
            _format_class_for_extraction(info)
            for _, info in batch
        )

        prompt = EXTRACT_CONCEPTS_PROMPT.format(classes_text=classes_text)
        response = completer(prompt)

        # 解析 JSON 响应
        try:
            # 尝试提取 JSON
            if "{" in response and "}" in response:
                json_str = response[response.index("{"):response.rindex("}") + 1]
                batch_concepts = json.loads(json_str)
                all_concepts.update(batch_concepts)
                logger.info(f"      ✅ 提取到 {len(batch_concepts)} 个类的业务概念")
            else:
                logger.warning(f"      ⚠️ 响应中无 JSON: {response[:200]}")
        except json.JSONDecodeError as e:
            logger.warning(f"      ⚠️ JSON 解析失败: {e}")
            logger.warning(f"      响应内容: {response[:500]}")

    return all_concepts


# ─────────────────────────────────────────────────────────────
# Step 3: 依赖图预聚类（networkx 社区检测）
# ─────────────────────────────────────────────────────────────

def precluster_by_dependency_graph(
    class_summaries: Dict[str, dict],
    components: Dict[str, Node],
) -> Dict[str, List[str]]:
    """
    用 networkx 对依赖图做社区检测，返回预聚类结果。

    Args:
        class_summaries: 类级摘要
        components: 原始组件字典（用于提取方法级调用关系）

    Returns:
        {community_name: [class_name1, class_name2, ...]}
    """
    try:
        import networkx as nx
        from networkx.algorithms.community import greedy_modularity_communities
    except ImportError:
        logger.warning("    ⚠️ networkx 未安装，跳过依赖图预聚类")
        return {}

    # 构建类级无向图
    G = nx.Graph()

    # 添加所有类作为节点
    for class_key, info in class_summaries.items():
        G.add_node(info["class_name"])

    # 从方法级调用关系构建类间边
    edge_weights: Dict[tuple, int] = defaultdict(int)

    for comp_id, comp in components.items():
        short = comp_id.split("::")[-1] if "::" in comp_id else comp_id
        if "." not in short:
            continue  # 跳过类级组件本身

        caller_class = short.split(".")[0]

        for dep in comp.depends_on:
            dep_short = dep.split("::")[-1] if "::" in dep else dep
            dep_class = dep_short.split(".")[0]

            if caller_class != dep_class:
                # 无向边，归一化方向
                edge = tuple(sorted([caller_class, dep_class]))
                edge_weights[edge] += 1

    # 添加带权重的边
    for (a, b), weight in edge_weights.items():
        if a in G.nodes and b in G.nodes:
            G.add_edge(a, b, weight=weight)

    logger.info(f"    依赖图: {G.number_of_nodes()} 个节点, {G.number_of_edges()} 条边")

    if G.number_of_edges() == 0:
        logger.warning("    ⚠️ 依赖图无边，跳过预聚类")
        return {}

    # 贪心社区检测
    communities = list(greedy_modularity_communities(G.to_undirected()))

    # 对每个社区命名（取中心度最高的类名）
    result = {}
    for i, comm in enumerate(communities):
        # 计算社区内节点的度中心度
        subgraph = G.subgraph(comm)
        centrality = nx.degree_centrality(subgraph)
        center_node = max(centrality, key=centrality.get)

        comm_name = f"Group{i+1}_{center_node}"
        result[comm_name] = sorted(comm)

    logger.info(f"    预聚类结果: {len(result)} 个社区")
    for name, members in sorted(result.items(), key=lambda x: -len(x[1])):
        logger.info(f"      {name} ({len(members)} 个类): {', '.join(members[:5])}{'...' if len(members) > 5 else ''}")

    return result


# ─────────────────────────────────────────────────────────────
# Step 4: 基于业务概念 + 预聚类的 LLM 聚类
# ─────────────────────────────────────────────────────────────

CLUSTER_WITH_CONCEPTS_PROMPT = """以下是仓库中所有核心类的业务领域和业务概念：

<CLASS_CONCEPTS>
{class_concepts_text}
</CLASS_CONCEPTS>

{pre_clustering_section}

请将这些类分组为模块。分组时请遵循以下优先级：
1. 业务领域：相同或相近业务领域的类 → 放同一模块
2. 业务概念：共享核心业务概念的类 → 放同一模块
3. 调用关系：两个类之间有直接调用关系 → 倾向放同一模块
4. 命名模式：相同前缀/后缀 → 倾向放同一模块

要求：
- 模块名必须使用英文，采用 PascalCase 命名（如 ContractOperations、PdfGeneration）
- 每个模块至少包含 2 个类（除非该类独立性很强）
- 不要创建超过 12 个模块

请先分析各类之间的业务关联，然后进行分组，按以下格式返回结果：
<GROUPED_COMPONENTS>
{{
    "ModuleName1": {{
        "components": [
            "ClassName1",
            "ClassName2"
        ]
    }},
    "ModuleName2": {{
        "components": [
            "ClassName3",
            "ClassName4"
        ]
    }}
}}
</GROUPED_COMPONENTS>"""


def cluster_with_business_concepts(
    class_summaries: Dict[str, dict],
    business_concepts: Dict[str, dict],
    pre_clusters: Dict[str, List[str]],
    completer: Callable[[str], str],
) -> Dict[str, List[str]]:
    """
    基于业务概念和预聚类结果，调用 LLM 进行最终聚类。

    Args:
        class_summaries: 类级摘要
        business_concepts: Step 2 的输出
        pre_clusters: Step 3 的输出
        completer: LLM completer

    Returns:
        {module_name: [class_name1, class_name2, ...]}
    """
    # 格式化业务概念文本
    lines = []
    for class_key, info in sorted(class_summaries.items()):
        cname = info["class_name"]
        concepts = business_concepts.get(cname, {})
        domain = concepts.get("domain", "未知")
        concept_list = concepts.get("concepts", [])
        deps = ", ".join(info["depends_on"][:5]) if info["depends_on"] else "无"

        lines.append(f"{cname}")
        lines.append(f"  业务领域: {domain}")
        lines.append(f"  业务概念: {', '.join(concept_list)}")
        lines.append(f"  依赖: {deps}")
        lines.append(f"  方法数: {info['method_count']}, 行数: {info['total_lines']}")
        lines.append("")

    class_concepts_text = "\n".join(lines)

    # 格式化预聚类文本
    pre_clustering_section = ""
    if pre_clusters:
        pre_lines = ["以下是基于调用关系自动检测的模块划分（仅供参考，请根据业务职责调整）：", ""]
        for name, members in sorted(pre_clusters.items(), key=lambda x: -len(x[1])):
            pre_lines.append(f"## {name} ({len(members)} classes)")
            pre_lines.append(f"  {', '.join(members)}")
            pre_lines.append("")
        pre_clustering_section = "<PRE_CLUSTERING>\n" + "\n".join(pre_lines) + "\n</PRE_CLUSTERING>"

    prompt = CLUSTER_WITH_CONCEPTS_PROMPT.format(
        class_concepts_text=class_concepts_text,
        pre_clustering_section=pre_clustering_section,
    )

    logger.info(f"    调用 LLM 进行最终聚类 (prompt: {len(prompt)} chars)...")
    response = completer(prompt)

    # 解析响应
    if "<GROUPED_COMPONENTS>" not in response or "</GROUPED_COMPONENTS>" not in response:
        logger.warning(f"    ⚠️ 响应中无 <GROUPED_COMPONENTS> 标签")
        logger.warning(f"    响应预览: {response[:500]}")
        return {}

    content = response.split("<GROUPED_COMPONENTS>")[1].split("</GROUPED_COMPONENTS>")[0].strip()

    try:
        module_tree = json.loads(content)
    except json.JSONDecodeError:
        try:
            module_tree = eval(content)
        except Exception as e:
            logger.warning(f"    ⚠️ JSON 解析失败: {e}")
            return {}

    if not isinstance(module_tree, dict):
        logger.warning(f"    ⚠️ 期望 dict，得到 {type(module_tree)}")
        return {}

    # 提取 components 列表
    result = {}
    for module_name, module_info in module_tree.items():
        if isinstance(module_info, dict):
            result[module_name] = module_info.get("components", [])
        elif isinstance(module_info, list):
            result[module_name] = module_info

    logger.info(f"    最终聚类结果: {len(result)} 个模块")
    for name, members in sorted(result.items(), key=lambda x: -len(x[1])):
        logger.info(f"      {name} ({len(members)} 个类): {', '.join(members[:5])}{'...' if len(members) > 5 else ''}")

    return result


# ─────────────────────────────────────────────────────────────
# Step 5: 映射回方法级 ID
# ─────────────────────────────────────────────────────────────

def map_classes_to_method_ids(
    class_clusters: Dict[str, List[str]],
    class_summaries: Dict[str, dict],
    components: Dict[str, Node],
) -> Dict[str, Any]:
    """
    将类级聚类结果映射回方法级组件 ID，构建 module_tree。

    Args:
        class_clusters: {module_name: [class_name1, class_name2, ...]}
        class_summaries: 类级摘要（用于获取 relative_path）
        components: 原始组件字典

    Returns:
        module_tree（方法级 ID）
    """
    # 构建 class_name → class_key 的映射
    class_name_to_key = {}
    for class_key, info in class_summaries.items():
        class_name_to_key[info["class_name"]] = class_key

    # 构建 class_key → [method_ids] 的映射
    class_key_to_methods: Dict[str, List[str]] = defaultdict(list)
    for comp_id in components:
        short = comp_id.split("::")[-1] if "::" in comp_id else comp_id
        if "." in short:
            class_name = short.split(".")[0]
            rel_path = components[comp_id].relative_path
            class_key = f"{rel_path}::{class_name}"
            class_key_to_methods[class_key].append(comp_id)

    # 映射
    module_tree = {}
    for module_name, class_names in class_clusters.items():
        method_ids = []
        for cname in class_names:
            class_key = class_name_to_key.get(cname)
            if class_key and class_key in class_key_to_methods:
                method_ids.extend(class_key_to_methods[class_key])
            else:
                logger.warning(f"    ⚠️ 类 {cname} 未找到对应的方法级组件")

        if method_ids:
            module_tree[module_name] = {
                "components": method_ids,
                "children": {},
            }

    return module_tree


# ─────────────────────────────────────────────────────────────
# 保存中间结果
# ─────────────────────────────────────────────────────────────

def save_intermediate_result(data: Any, filename: str, output_dir: str = "."):
    """保存中间结果为 JSON 文件"""
    filepath = os.path.join(output_dir, filename)

    # 处理 set 类型
    def default_serializer(obj):
        if isinstance(obj, set):
            return sorted(list(obj))
        raise TypeError(f"Type {type(obj)} not serializable")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=default_serializer)

    logger.info(f"    💾 中间结果已保存: {filepath}")
