"""
模块文档生成 — 对应 CodeWiki 的:
- codewiki/src/be/documentation_generator.py
- codewiki/src/be/prompt_template.py

核心流程：
1. 按拓扑序遍历模块树（叶子在前，父在后）
2. 叶子模块 → LLM 生成详细文档（含源码上下文）
3. 父模块 → LLM 汇总子模块文档生成概览
4. 最后生成仓库总览 overview.md

简化设计（对比 CodeWiki 原始实现）：
- 不使用 Agent 工具（str_replace_editor / read_code_components）
- 直接把源码和依赖信息放入 prompt，单次 LLM 调用生成文档
- 效果略弱于 CodeWiki 的多轮 Agent，但速度快、实现简单
"""

import os
import re
import json
import logging
from typing import Dict, List, Any, Callable
from collections import defaultdict

from models import Node

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Mermaid 语法验证（对应 CodeWiki 的 codewiki/src/be/utils.py）
# ─────────────────────────────────────────────────────────────

def extract_mermaid_blocks(content: str) -> List[tuple[int, str]]:
    """
    从 Markdown 内容中提取所有 Mermaid 代码块。

    Returns:
        [(起始行号, 图表内容), ...]
    """
    blocks = []
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("```mermaid"):
            start_line = i + 1
            diagram_lines = []
            i += 1
            while i < len(lines):
                if lines[i].strip() == "```":
                    break
                diagram_lines.append(lines[i])
                i += 1
            if diagram_lines:
                blocks.append((start_line, "\n".join(diagram_lines)))
        i += 1
    return blocks


def validate_mermaid_diagram(diagram_content: str, diagram_num: int, line_start: int) -> str:
    """
    验证单个 Mermaid 图表的语法。

    对应 CodeWiki 的 validate_single_diagram()。
    使用 mermaid-py 库进行语法检查。

    Returns:
        错误信息（空字符串表示语法正确）
    """
    try:
        import mermaid as md
        md.Mermaid(diagram_content)
        return ""
    except Exception as e:
        error_str = str(e)
        # 提取行号信息
        line_match = re.search(r"line (\d+)", error_str)
        if line_match:
            error_line = int(line_match.group(1))
            actual_line = line_start + error_line
            return f"Diagram {diagram_num}: Parse error on line {actual_line}:\n{error_str}"
        return f"Diagram {diagram_num}: {error_str}"


def validate_mermaid_in_markdown(content: str) -> str:
    """
    验证 Markdown 中所有 Mermaid 图表的语法。

    对应 CodeWiki 的 validate_mermaid_diagrams()。

    Returns:
        "All mermaid diagrams are syntax correct" 或错误详情
    """
    blocks = extract_mermaid_blocks(content)
    if not blocks:
        return "No mermaid diagrams found"

    errors = []
    for i, (line_start, diagram_content) in enumerate(blocks, 1):
        error = validate_mermaid_diagram(diagram_content, i, line_start)
        if error:
            errors.append(error)

    if errors:
        return "Mermaid syntax errors found:\n" + "\n".join(errors)
    return "All mermaid diagrams are syntax correct"


# ─────────────────────────────────────────────────────────────
# Prompt 模板（对应 CodeWiki 的 prompt_template.py，改为中文）
# ─────────────────────────────────────────────────────────────

# 叶子模块的 System Prompt
LEAF_SYSTEM_PROMPT = """<ROLE>
你是一名 AI 文档助手。你的任务是根据给定的模块名称和核心代码组件，生成全面的系统文档。
</ROLE>

<OBJECTIVES>
创建帮助开发者和维护者理解以下内容的文档：
1. 模块的目的和核心功能
2. 架构和组件关系
3. 模块如何融入整体系统
</OBJECTIVES>

<DOCUMENTATION_REQUIREMENTS>
按以下要求生成文档：
1. 结构：简要介绍 → 包含 Mermaid 图表的综合文档
2. 图表：包含架构图、依赖关系图、数据流图、组件交互图、流程图（按需）
3. 引用：链接到其他模块文档，避免重复信息
</DOCUMENTATION_REQUIREMENTS>

<MERMAID_SYNTAX_RULES>
生成 Mermaid 图表时，必须严格遵守以下语法规则，否则会导致渲染失败：
1. 节点 ID 只能包含字母、数字、下划线，不能包含空格、括号、点号等特殊字符
2. 节点标签用 [] 包裹，如 `NodeA[节点A的描述]`，标签内不要使用引号
3. 箭头用 --> 表示，如 `A --> B`
4. 注释用 %% 表示，独占一行
5. subgraph 语法：`subgraph ID[标题]` ... `end`
6. 不要在标签中使用 Markdown 语法（如 **粗体**）
7. 中文标签放在 [] 内，不要放在 ID 位置
8. 每个图表类型的关键字必须正确：
   - 流程图：graph TD 或 graph LR
   - 时序图：sequenceDiagram
   - 类图：classDiagram
   - 状态图：stateDiagram-v2
   - 饼图：pie
</MERMAID_SYNTAX_RULES>

<AVAILABLE_TOOLS>
- read_code_components: 读取指定组件的源码。参数为组件 ID 列表，如 ["auth/login.py::LoginService"]
</AVAILABLE_TOOLS>

<WORKFLOW>
1. 分析提供的核心代码组件和模块结构
2. 查看核心组件的 depends_on 依赖关系，使用 read_code_components 读取被依赖组件的源码以理解完整逻辑
3. 直接输出完整的 {module_name}.md 文档正文（从 # 标题开始，不要输出目录或概览）
</WORKFLOW>
{custom_instructions}"""

# 父模块的 System Prompt
PARENT_SYSTEM_PROMPT = """<ROLE>
你是一名 AI 文档助手。你的任务是根据子模块的文档，生成父模块的概览文档。
</ROLE>

<OBJECTIVES>
创建帮助开发者和维护者理解以下内容的文档：
1. 父模块的目的和核心功能
2. 子模块之间的关系和协作方式
3. 架构图和数据流
</OBJECTIVES>

<WORKFLOW>
1. 分析子模块的文档
2. 理解子模块之间的依赖关系
3. 生成父模块的概览文档，包含 Mermaid 架构图
</WORKFLOW>
{custom_instructions}"""

# 用户 Prompt：叶子模块
LEAF_USER_PROMPT = """请为 {module_name} 模块生成综合文档。

<MODULE_TREE>
{module_tree}
</MODULE_TREE>
* 注意：你可以参考模块树中的其他模块，基于它们与当前模块核心组件之间的依赖关系，使文档更有结构，避免重复信息。所有文档文件保存在同一目录下，引用格式：[链接文本](模块名.md)

<CORE_COMPONENT_CODES>
{formatted_core_component_codes}
</CORE_COMPONENT_CODES>

<AVAILABLE_COMPONENTS>
以下是仓库中所有可用的组件，按文件分组。如果核心组件依赖了其他组件，请直接读取对应源码文件以理解完整逻辑：
{available_components}
</AVAILABLE_COMPONENTS>

重要要求：
1. 直接输出完整的 {module_name}.md 文档正文，从 # 标题开始
2. 不要输出任何前缀说明（如"文档已生成"、"Now I have enough context"等）
3. 不要输出文档目录或结构概览
4. 不要描述你要写什么，直接写出来
5. 文档应包含：模块概述、架构图、核心组件详解、依赖关系、数据流、关键设计模式等"""

# 用户 Prompt：父模块概览
PARENT_USER_PROMPT = """请为 {module_name} 模块生成简要概览文档。

概览应包含：
- 模块的目的
- 模块的架构（用 Mermaid 图表展示）
- 子模块文档的引用

以下是模块结构和子模块文档：
<REPO_STRUCTURE>
{repo_structure}
</REPO_STRUCTURE>

请生成 {module_name} 的概览文档，使用 Markdown 格式：

<OVERVIEW>
overview_content
</OVERVIEW>"""

# 仓库总览 Prompt
REPO_OVERVIEW_PROMPT = """请为 {repo_name} 仓库生成简要概览文档。

概览应包含：
- 仓库的目的
- 端到端架构（用 Mermaid 图表展示）
- 核心模块文档的引用

以下是仓库结构和核心模块文档：
<REPO_STRUCTURE>
{repo_structure}
</REPO_STRUCTURE>

请生成 {repo_name} 仓库的概览文档，使用 Markdown 格式：

<OVERVIEW>
overview_content
</OVERVIEW>"""


# ─────────────────────────────────────────────────────────────
# 文档扩展名到语言的映射
# ─────────────────────────────────────────────────────────────

EXTENSION_TO_LANGUAGE = {
    ".py": "python", ".java": "java", ".js": "javascript", ".ts": "typescript",
    ".cpp": "cpp", ".c": "c", ".cs": "csharp", ".kt": "kotlin", ".php": "php",
    ".go": "go", ".rs": "rust", ".rb": "ruby", ".sh": "bash", ".sql": "sql",
}


# ─────────────────────────────────────────────────────────────
# Prompt 格式化
# ─────────────────────────────────────────────────────────────

def _format_module_tree_text(module_tree: dict, target_module: str = None, indent: int = 0) -> str:
    """将模块树格式化为可读文本"""
    lines = []

    def _format(tree, level):
        for key, value in tree.items():
            marker = " (current module)" if key == target_module else ""
            lines.append(f"{'  ' * level}{key}{marker}")

            by_file = defaultdict(list)
            for c in value.get("components", []):
                if "::" in c:
                    fpath, name = c.split("::", 1)
                    by_file[fpath].append(name)
                else:
                    by_file[""].append(c)
            for fpath, names in by_file.items():
                prefix = f"{fpath}: " if fpath else ""
                lines.append(f"{'  ' * (level + 1)} {prefix}{', '.join(names)}")

            children = value.get("children", {})
            if isinstance(children, dict) and children:
                lines.append(f"{'  ' * (level + 1)} Children:")
                _format(children, level + 2)

    _format(module_tree, indent)
    return "\n".join(lines)


def _format_component_codes(component_ids: List[str], components: Dict[str, Node]) -> str:
    """将组件源码格式化为 prompt 文本（按文件分组）"""
    grouped = defaultdict(list)
    for cid in component_ids:
        if cid in components:
            grouped[components[cid].relative_path].append(cid)

    result = ""
    for path, ids in sorted(grouped.items()):
        result += f"# File: {path}\n\n"
        result += "## Core Components in this file:\n"
        for cid in ids:
            result += f"- {cid}\n"

        # 读取文件内容
        comp = components[ids[0]]
        lang = EXTENSION_TO_LANGUAGE.get(
            "." + path.rsplit(".", 1)[-1] if "." in path else "", ""
        )
        try:
            with open(comp.file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            result += f"\n## File Content:\n```{lang}\n{content}\n```\n\n"
        except Exception as e:
            result += f"\n## File Content:\n# Error reading file: {e}\n\n"

    return result


def _format_available_components(components: Dict[str, Node]) -> str:
    """
    格式化所有可用组件的列表（按文件分组，只列 ID 和类型，不包含源码）。
    让 LLM 知道有哪些组件可以读取。
    """
    by_file = defaultdict(list)
    for comp_id, comp in components.items():
        by_file[comp.relative_path].append((comp_id, comp.component_type))

    lines = []
    for path, comps in sorted(by_file.items()):
        lines.append(f"# {path}")
        for comp_id, comp_type in comps:
            short = comp_id.split("::")[-1] if "::" in comp_id else comp_id
            lines.append(f"\t{short} ({comp_type})")
    return "\n".join(lines)


def format_leaf_prompt(
    module_name: str,
    component_ids: List[str],
    components: Dict[str, Node],
    module_tree: dict,
    all_components: Dict[str, Node] = None,
) -> str:
    """格式化叶子模块的文档生成 Prompt"""
    tree_text = _format_module_tree_text(module_tree, target_module=module_name)
    codes = _format_component_codes(component_ids, components)
    available = _format_available_components(all_components or components)
    return LEAF_USER_PROMPT.format(
        module_name=module_name,
        module_tree=tree_text,
        formatted_core_component_codes=codes,
        available_components=available,
    )


def format_parent_prompt(module_name: str, repo_structure: dict) -> str:
    """格式化父模块的概览生成 Prompt"""
    return PARENT_USER_PROMPT.format(
        module_name=module_name,
        repo_structure=json.dumps(repo_structure, indent=2, ensure_ascii=False),
    )


def format_repo_overview_prompt(repo_name: str, repo_structure: dict) -> str:
    """格式化仓库总览的生成 Prompt"""
    return REPO_OVERVIEW_PROMPT.format(
        repo_name=repo_name,
        repo_structure=json.dumps(repo_structure, indent=2, ensure_ascii=False),
    )


# ─────────────────────────────────────────────────────────────
# 模块树遍历
# ─────────────────────────────────────────────────────────────

def get_processing_order(module_tree: dict, parent_path: list = None) -> List[tuple]:
    """
    获取模块的处理顺序：叶子在前，父在后（拓扑序）。

    对应 CodeWiki 的 DocumentationGenerator.get_processing_order()
    """
    if parent_path is None:
        parent_path = []

    processing_order = []

    def collect(tree, path):
        for name, info in tree.items():
            current_path = path + [name]
            children = info.get("children", {})
            if isinstance(children, dict) and children:
                collect(children, current_path)
                processing_order.append((current_path, name))
            else:
                processing_order.append((current_path, name))

    collect(module_tree, parent_path)
    return processing_order


def is_leaf_module(module_info: dict) -> bool:
    """判断是否是叶子模块（无子模块或子模块为空）"""
    children = module_info.get("children", {})
    return not children or (isinstance(children, dict) and len(children) == 0)


# ─────────────────────────────────────────────────────────────
# 父模块概览构建
# ─────────────────────────────────────────────────────────────

def build_overview_structure(
    module_tree: dict, module_path: List[str], docs_dir: str
) -> dict:
    """
    构建父模块概览的上下文：注入子模块的文档内容。

    对应 CodeWiki 的 DocumentationGenerator.build_overview_structure()
    """
    from copy import deepcopy

    tree = deepcopy(module_tree)

    # 定位到目标模块并标记
    node = tree
    for i, part in enumerate(module_path):
        node = node[part]
        if i < len(module_path) - 1:
            node = node.get("children", {})

    if "children" in node:
        node = node["children"]

    # 为每个子模块注入文档内容
    for child_name, child_info in node.items():
        doc_path = _resolve_doc_path(docs_dir, child_name)
        if doc_path:
            try:
                with open(doc_path, "r", encoding="utf-8") as f:
                    child_info["docs"] = f.read()
            except Exception:
                child_info["docs"] = ""
        else:
            child_info["docs"] = ""

    return tree


def _resolve_doc_path(docs_dir: str, module_name: str) -> str | None:
    """尝试多种命名变体查找子模块的 .md 文件"""
    candidates = set()
    for variant in [module_name, module_name.replace(" ", "_"), module_name.replace(" ", "-")]:
        for cased in [variant, variant.lower()]:
            candidates.add(f"{cased}.md")

    for filename in candidates:
        path = os.path.join(docs_dir, filename)
        if os.path.exists(path):
            return path
    return None


# ─────────────────────────────────────────────────────────────
# 核心文档生成逻辑
# ─────────────────────────────────────────────────────────────

def generate_documentation(
    repo_name: str,
    module_tree: dict,
    components: Dict[str, Node],
    docs_dir: str,
    completer: Callable[[str, str], str],
) -> str:
    """
    生成所有模块的文档。

    对应 CodeWiki 的 DocumentationGenerator.generate_module_documentation()

    Args:
        repo_name: 仓库名称
        module_tree: 模块树（来自聚类步骤）
        components: 所有组件字典
        docs_dir: 文档输出目录
        completer: LLM 调用函数 (system_prompt, user_prompt) -> str

    Returns:
        docs_dir: 文档输出目录
    """
    os.makedirs(docs_dir, exist_ok=True)

    if not module_tree:
        # 没有模块树 → 整体作为一个模块处理
        logger.info("No module tree, processing whole repo as one module")
        _generate_single_module_docs(
            repo_name, list(components.keys()), components, module_tree, docs_dir, completer
        )
        _rename_to_overview(docs_dir, repo_name)
        return docs_dir

    # 获取拓扑处理顺序
    processing_order = get_processing_order(module_tree)
    logger.info(f"Processing {len(processing_order)} modules in topological order")

    for module_path, module_name in processing_order:
        module_key = "/".join(module_path)

        # 定位模块信息
        module_info = module_tree
        for part in module_path:
            module_info = module_info[part]
            if part != module_path[-1]:
                module_info = module_info.get("children", {})

        if is_leaf_module(module_info):
            logger.info(f"  📄 Processing leaf module: {module_key}")
            _generate_leaf_module_docs(
                module_name, module_info, components, module_tree, docs_dir, completer
            )
        else:
            logger.info(f"  📁 Processing parent module: {module_key}")
            _generate_parent_module_docs(
                module_name, module_path, module_tree, docs_dir, completer
            )

    # 生成仓库总览
    logger.info(f"  📚 Generating repository overview")
    _generate_repo_overview(repo_name, module_tree, docs_dir, completer)

    return docs_dir


def _generate_leaf_module_docs(
    module_name: str,
    module_info: dict,
    components: Dict[str, Node],
    module_tree: dict,
    docs_dir: str,
    completer: Callable[[str, str], str],
    max_retries: int = 2,
):
    """为叶子模块生成文档，包含 Mermaid 语法验证 + 自动重试"""
    doc_path = os.path.join(docs_dir, f"{module_name}.md")
    if os.path.exists(doc_path):
        logger.info(f"    ✓ {module_name}.md already exists, skipping")
        return

    component_ids = module_info.get("components", [])
    if not component_ids:
        logger.warning(f"    No components for {module_name}, skipping")
        return

    system_prompt = LEAF_SYSTEM_PROMPT.format(module_name=module_name, custom_instructions="")
    user_prompt = format_leaf_prompt(module_name, component_ids, components, module_tree, all_components=components)

    for attempt in range(max_retries + 1):
        # 调用 LLM
        if attempt == 0:
            logger.info(f"    Calling LLM for {module_name}.md...")
        else:
            logger.info(f"    Retrying {module_name}.md (attempt {attempt + 1}, fixing Mermaid errors)...")

        response = completer(system_prompt, user_prompt)

        # 检查 LLM 是否返回了内容
        if not response or not response.strip():
            logger.warning(f"    ⚠️ LLM 返回为空，跳过 {module_name}.md")
            return

        # 验证 Mermaid 语法
        mermaid_result = validate_mermaid_in_markdown(response)
        if "errors" not in mermaid_result.lower():
            # 验证通过，保存文档
            with open(doc_path, "w", encoding="utf-8") as f:
                f.write(response)
            logger.info(f"    ✓ Saved {module_name}.md ({len(response)} chars)")
            return

        # 验证失败，记录错误并重试
        logger.warning(f"    ⚠️ Mermaid validation failed for {module_name}.md: {mermaid_result}")

        # 如果还有重试机会，构造修复 prompt
        if attempt < max_retries:
            user_prompt = (
                f"你上次生成的 {module_name}.md 中 Mermaid 图表有语法错误，请修复后重新生成完整文档。\n\n"
                f"错误信息：\n{mermaid_result}\n\n"
                f"请重新生成完整的 {module_name}.md 文档，确保所有 Mermaid 图表语法正确。"
            )

    # 所有重试都失败，保存最后一次的结果
    logger.warning(f"    ⚠️ Mermaid still has errors after {max_retries + 1} attempts, saving anyway")
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write(response)
    logger.info(f"    ✓ Saved {module_name}.md ({len(response)} chars, with Mermaid warnings)")


def _generate_parent_module_docs(
    module_name: str,
    module_path: List[str],
    module_tree: dict,
    docs_dir: str,
    completer: Callable[[str, str], str],
    max_retries: int = 2,
):
    """为父模块生成概览文档，包含 Mermaid 语法验证 + 自动重试"""
    doc_path = os.path.join(docs_dir, f"{module_name}.md")
    if os.path.exists(doc_path):
        logger.info(f"    ✓ {module_name}.md already exists, skipping")
        return

    repo_structure = build_overview_structure(module_tree, module_path, docs_dir)
    system_prompt = PARENT_SYSTEM_PROMPT.format(custom_instructions="")
    user_prompt = format_parent_prompt(module_name, repo_structure)

    for attempt in range(max_retries + 1):
        if attempt == 0:
            logger.info(f"    Calling LLM for {module_name}.md (parent overview)...")
        else:
            logger.info(f"    Retrying {module_name}.md (attempt {attempt + 1})...")

        response = completer(system_prompt, user_prompt)

        # 检查 LLM 是否返回了内容
        if not response or not response.strip():
            logger.warning(f"    ⚠️ LLM 返回为空，跳过 {module_name}.md")
            return

        content = _extract_overview(response)

        # 验证 Mermaid 语法
        mermaid_result = validate_mermaid_in_markdown(content)
        if "errors" not in mermaid_result.lower():
            with open(doc_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"    ✓ Saved {module_name}.md ({len(content)} chars)")
            return

        logger.warning(f"    ⚠️ Mermaid validation failed: {mermaid_result}")
        if attempt < max_retries:
            user_prompt = (
                f"你上次生成的 {module_name} 概览中 Mermaid 图表有语法错误，请修复后重新生成。\n\n"
                f"错误信息：\n{mermaid_result}\n\n"
                f"请重新生成完整的概览文档，确保 Mermaid 语法正确。"
            )

    logger.warning(f"    ⚠️ Mermaid still has errors after {max_retries + 1} attempts, saving anyway")
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"    ✓ Saved {module_name}.md ({len(content)} chars, with Mermaid warnings)")


def _generate_repo_overview(
    repo_name: str,
    module_tree: dict,
    docs_dir: str,
    completer: Callable[[str, str], str],
    max_retries: int = 2,
):
    """生成仓库总览文档，包含 Mermaid 语法验证 + 自动重试"""
    overview_path = os.path.join(docs_dir, "overview.md")
    if os.path.exists(overview_path):
        logger.info(f"    ✓ overview.md already exists, skipping")
        return

    repo_structure = build_overview_structure(module_tree, [], docs_dir)
    system_prompt = "你是一名 AI 文档助手。请为仓库生成简要概览文档。"
    user_prompt = format_repo_overview_prompt(repo_name, repo_structure)

    for attempt in range(max_retries + 1):
        if attempt == 0:
            logger.info(f"    Calling LLM for overview.md...")
        else:
            logger.info(f"    Retrying overview.md (attempt {attempt + 1})...")

        response = completer(system_prompt, user_prompt)

        # 检查 LLM 是否返回了内容
        if not response or not response.strip():
            logger.warning(f"    ⚠️ LLM 返回为空，跳过 overview.md")
            return

        content = _extract_overview(response)

        mermaid_result = validate_mermaid_in_markdown(content)
        if "errors" not in mermaid_result.lower():
            with open(overview_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"    ✓ Saved overview.md ({len(content)} chars)")
            return

        logger.warning(f"    ⚠️ Mermaid validation failed: {mermaid_result}")
        if attempt < max_retries:
            user_prompt = (
                f"你上次生成的仓库概览中 Mermaid 图表有语法错误，请修复后重新生成。\n\n"
                f"错误信息：\n{mermaid_result}\n\n"
                f"请重新生成完整的概览文档，确保 Mermaid 语法正确。"
            )

    logger.warning(f"    ⚠️ Mermaid still has errors after {max_retries + 1} attempts, saving anyway")
    with open(overview_path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"    ✓ Saved overview.md ({len(content)} chars, with Mermaid warnings)")


def _generate_single_module_docs(
    repo_name: str,
    component_ids: List[str],
    components: Dict[str, Node],
    module_tree: dict,
    docs_dir: str,
    completer: Callable[[str, str], str],
):
    """当没有模块树时，整体作为一个模块生成文档"""
    system_prompt = LEAF_SYSTEM_PROMPT.format(module_name=repo_name, custom_instructions="")
    user_prompt = format_leaf_prompt(repo_name, component_ids, components, module_tree, all_components=components)

    logger.info(f"    Calling LLM for {repo_name}.md...")
    response = completer(system_prompt, user_prompt)

    if not response or not response.strip():
        logger.warning(f"    ⚠️ LLM 返回为空，跳过 {repo_name}.md")
        return

    doc_path = os.path.join(docs_dir, f"{repo_name}.md")
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write(response)
    logger.info(f"    ✓ Saved {repo_name}.md ({len(response)} chars)")


def _rename_to_overview(docs_dir: str, repo_name: str):
    """将仓库文档重命名为 overview.md"""
    src = os.path.join(docs_dir, f"{repo_name}.md")
    dst = os.path.join(docs_dir, "overview.md")
    if os.path.exists(src) and not os.path.exists(dst):
        os.rename(src, dst)
        logger.info(f"    ✓ Renamed {repo_name}.md → overview.md")


def _extract_overview(response: str) -> str:
    """从 LLM 响应中提取 <OVERVIEW> 标签内容"""
    if "<OVERVIEW>" in response and "</OVERVIEW>" in response:
        return response.split("<OVERVIEW>")[1].split("</OVERVIEW>")[0].strip()
    return response.strip()
