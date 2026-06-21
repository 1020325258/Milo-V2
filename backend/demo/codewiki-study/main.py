#!/usr/bin/env python3
"""
CodeWiki 源码解析 Demo — 可独立运行

对应 CodeWiki 的三个步骤：
  ① build_dependency_graph() — 源码解析 & 依赖图构建
  ② cluster_modules()        — LLM 驱动的递归模块聚类
  ③ generate_documentation() — 按模块树生成文档

用法:
    # 直接运行（使用默认路径）
    python main.py

    # 指定路径
    python main.py /path/to/your/java/project
"""

import os
import sys
import json
import logging
import time
from typing import Dict, List, Any
from collections import defaultdict

from models import Node, CallRelationship
from java_analyzer import analyze_java_file
from graph_builder import (
    build_graph_from_components,
    get_leaf_nodes,
    topological_sort,
    detect_cycles,
)
from cluster_modules import (
    cluster_modules,
    print_module_tree,
    get_clustering_input_token_count,
    create_openai_completer,
    create_claude_code_completer,
    create_claude_code_doc_completer,
    create_claude_code_overview_completer,
)
from doc_generator import generate_documentation



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 1. 扫描目录，收集所有 Java 文件
# ─────────────────────────────────────────────────────────────

def scan_java_files(repo_path: str) -> List[Dict[str, str]]:
    """
    递归扫描目录，收集所有 .java 文件。

    对应 CodeWiki 的 RepoAnalyzer._build_file_tree() + extract_code_files()
    """
    java_files = []
    repo_path = os.path.abspath(repo_path)

    for root, dirs, files in os.walk(repo_path):
        # 跳过隐藏目录和构建目录
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".")
            and d not in ("target", "build", "node_modules", "__pycache__")
        ]

        for filename in sorted(files):
            if filename.endswith(".java"):
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, repo_path)
                java_files.append({
                    "path": full_path,
                    "relative_path": rel_path,
                    "name": filename,
                })

    return java_files


# ─────────────────────────────────────────────────────────────
# 2. 解析所有文件，提取组件和调用关系
# ─────────────────────────────────────────────────────────────

def parse_all_files(
    java_files: List[Dict[str, str]], repo_path: str
) -> Dict[str, Node]:
    """
    逐文件调用 Java Analyzer，汇总所有组件。

    对应 CodeWiki 的 CallGraphAnalyzer.analyze_code_files()
    """
    components: Dict[str, Node] = {}
    all_relationships: List[CallRelationship] = []

    start_time = time.time()

    for idx, file_info in enumerate(java_files, 1):
        file_path = file_info["path"]
        rel_path = file_info["relative_path"]

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            nodes, relationships = analyze_java_file(file_path, content, repo_path)

            for node in nodes:
                components[node.id] = node

            all_relationships.extend(relationships)

            logger.info(
                f"  [{idx}/{len(java_files)}] {rel_path} → "
                f"{len(nodes)} components, {len(relationships)} relationships"
            )

        except Exception as e:
            logger.warning(f"  [{idx}/{len(java_files)}] Failed: {rel_path}: {e}")

    elapsed = time.time() - start_time
    logger.info(
        f"\n✓ Parsing complete: {len(java_files)} files, "
        f"{len(components)} components, {len(all_relationships)} relationships "
        f"({elapsed:.1f}s)"
    )

    # ── 解析调用关系：将 callee 名称匹配到实际组件 ID ──
    resolve_call_relationships(components, all_relationships)

    return components


# ─────────────────────────────────────────────────────────────
# 3. 调用关系解析（对应 CodeWiki 的 _resolve_call_relationships）
# ─────────────────────────────────────────────────────────────

def resolve_call_relationships(
    components: Dict[str, Node], relationships: List[CallRelationship]
):
    """
    将 callee 名称解析为实际的组件 ID，并写入 components 的 depends_on。

    CodeWiki 的策略：精确匹配 → 后缀匹配 → 简名匹配
    这里简化为：精确匹配 → 简名匹配
    """
    # 构建索引
    exact_index: Dict[str, List[str]] = defaultdict(list)   # 全名 → [组件ID]
    simple_index: Dict[str, List[str]] = defaultdict(list)  # 简名 → [组件ID]

    for comp_id, comp in components.items():
        exact_index[comp_id].append(comp_id)
        if comp.qualified_name:
            exact_index[comp.qualified_name].append(comp_id)
        exact_index[comp.name].append(comp_id)

        simple_index[comp.name].append(comp_id)
        if comp.qualified_name:
            simple_index[comp.qualified_name.split(".")[-1]].append(comp_id)
        if "::" in comp_id:
            short = comp_id.split("::")[-1]
            simple_index[short].append(comp_id)

    resolved_count = 0
    for rel in relationships:
        if rel.is_resolved and rel.callee in components:
            # 已解析，直接写入 depends_on
            if rel.caller in components:
                components[rel.caller].depends_on.add(rel.callee)
            resolved_count += 1
            continue

        callee_name = rel.callee
        resolved_id = None

        # 1. 精确匹配
        if callee_name in exact_index and len(exact_index[callee_name]) == 1:
            resolved_id = exact_index[callee_name][0]

        # 2. 简名匹配
        if not resolved_id:
            simple_name = callee_name.split(".")[-1] if "." in callee_name else callee_name
            if simple_name in simple_index and len(simple_index[simple_name]) == 1:
                resolved_id = simple_index[simple_name][0]

        if resolved_id and resolved_id in components:
            rel.callee = resolved_id
            rel.is_resolved = True
            if rel.caller in components:
                components[rel.caller].depends_on.add(resolved_id)
            resolved_count += 1

    logger.info(f"✓ Resolved {resolved_count}/{len(relationships)} call relationships")


# ─────────────────────────────────────────────────────────────
# 4. 打印结果
# ─────────────────────────────────────────────────────────────

def print_summary(components: Dict[str, Node], leaf_nodes: List[str], graph: Dict):
    """打印依赖图摘要"""
    print("\n" + "=" * 70)
    print("  依赖图构建结果")
    print("=" * 70)

    # 组件统计
    type_counts = defaultdict(int)
    for comp in components.values():
        type_counts[comp.component_type] += 1

    print(f"\n📦 组件总数: {len(components)}")
    for comp_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"   {comp_type}: {count}")

    # 依赖关系统计
    total_deps = sum(len(comp.depends_on) for comp in components.values())
    print(f"\n🔗 依赖关系总数: {total_deps}")

    # 依赖图
    print(f"\n📊 有向依赖图 (A → B 表示 A 依赖 B):")
    for comp_id in sorted(components.keys()):
        comp = components[comp_id]
        if comp.depends_on:
            short_id = comp_id.split("::")[-1] if "::" in comp_id else comp_id
            for dep_id in sorted(comp.depends_on):
                short_dep = dep_id.split("::")[-1] if "::" in dep_id else dep_id
                print(f"   {short_id} → {short_dep}")

    # 叶子节点
    print(f"\n🍃 叶子节点 (不被任何组件依赖): {len(leaf_nodes)}")
    for leaf in leaf_nodes:
        comp = components[leaf]
        print(f"   • {comp.name} ({comp.component_type}) @ {comp.relative_path}")

    # 拓扑排序
    topo_order = topological_sort(graph)
    print(f"\n📐 拓扑排序 (依赖在前，被依赖在后):")
    for i, node_id in enumerate(topo_order, 1):
        comp = components.get(node_id)
        if comp:
            print(f"   {i}. {comp.name} ({comp.component_type})")

    # 环检测
    cycles = detect_cycles(graph)
    if cycles:
        print(f"\n⚠️  检测到 {len(cycles)} 个循环依赖:")
        for i, cycle in enumerate(cycles, 1):
            names = []
            for node_id in cycle:
                comp = components.get(node_id)
                names.append(comp.name if comp else node_id.split("::")[-1])
            print(f"   环 {i}: {' → '.join(names)} → {names[0]}")
    else:
        print(f"\n✅ 无循环依赖")

    print("\n" + "=" * 70)


def save_dependency_graph(components: Dict[str, Node], output_path: str):
    """保存依赖图到 JSON 文件"""
    result = {}
    for comp_id, comp in components.items():
        comp_dict = comp.model_dump()
        # set 不能直接 JSON 序列化，转为 list
        if "depends_on" in comp_dict and isinstance(comp_dict["depends_on"], set):
            comp_dict["depends_on"] = list(comp_dict["depends_on"])
        result[comp_id] = comp_dict

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    logger.info(f"✓ Dependency graph saved to {output_path}")


def _export_components_for_mcp(components: Dict[str, Node], output_path: str):
    """导出组件数据为 JSON，供 MCP 服务器读取"""
    result = {}
    for comp_id, comp in components.items():
        result[comp_id] = {
            "name": comp.name,
            "component_type": comp.component_type,
            "relative_path": comp.relative_path,
            "source_code": comp.source_code or "",
        }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    logger.info(f"✓ Exported {len(result)} components for MCP")


# ─────────────────────────────────────────────────────────────
# 5. 主入口
# ─────────────────────────────────────────────────────────────




def main():
    if len(sys.argv) >= 2:
        repo_path = os.path.abspath(sys.argv[1])
    else:
        repo_path = DEFAULT_REPO_PATH
        print(f"(未指定路径，使用默认: {repo_path})")

    if not os.path.isdir(repo_path):
        print(f"错误: 路径不存在或不是目录: {repo_path}")
        sys.exit(1)

    repo_name = os.path.basename(repo_path)

    print(f"\n🔍 CodeWiki 依赖图构建 Demo")
    print(f"   仓库路径: {repo_path}")
    print(f"   仓库名称: {repo_name}")
    print()

    # ── 步骤 1: 扫描 Java 文件 ──
    logger.info("📂 Scanning Java files...")
    java_files = scan_java_files(repo_path)
    logger.info(f"   Found {len(java_files)} Java files")

    if not java_files:
        print("未找到 Java 文件，退出。")
        sys.exit(0)

    # ── 步骤 2: 解析所有文件，提取组件 ──
    logger.info("\n🔬 Parsing Java files with tree-sitter...")
    components = parse_all_files(java_files, repo_path)

    # ── 步骤 3: 构建依赖图 ──
    logger.info("\n📊 Building dependency graph...")
    graph = build_graph_from_components(components)
    logger.info(f"   Graph: {len(graph)} nodes, {sum(len(d) for d in graph.values())} edges")

    # ── 步骤 4: 找叶子节点 ──
    logger.info("\n🍃 Finding leaf nodes...")
    leaf_nodes = get_leaf_nodes(graph, components)
    logger.info(f"   Found {len(leaf_nodes)} leaf nodes")

    # ── 打印依赖图结果 ──
    print_summary(components, leaf_nodes, graph)

    # ── 保存依赖图 JSON ──
    output_path = os.path.join(os.path.dirname(__file__), f"dependency_graph.json")
    save_dependency_graph(components, output_path)

    # ════════════════════════════════════════════════════════════
    #  创建 LLM completer（根据 LLM_BACKEND 配置选择）
    # ════════════════════════════════════════════════════════════

    if LLM_BACKEND == "claude_code":
        cluster_completer = create_claude_code_completer()

        # 导出组件数据供 MCP 服务器使用
        script_dir = os.path.dirname(__file__)
        mcp_components_path = os.path.join(script_dir, "components_for_mcp.json")
        _export_components_for_mcp(components, mcp_components_path)
        mcp_server_path = os.path.join(script_dir, "mcp_component_server.py")
        logger.info(f"   MCP components: {mcp_components_path}")

        doc_completer = create_claude_code_doc_completer(
            mcp_server_name="code-components",
            mcp_server_command="python",
            mcp_server_args=[mcp_server_path, mcp_components_path],
        )
        # 概览用无工具的纯补全，与 CodeWiki 的 backend.complete() 对齐
        overview_completer = create_claude_code_overview_completer()
        logger.info(f"   LLM Backend: Claude Code SDK (mimo-v2.5-pro) + MCP read_code_components")
    else:
        cluster_completer = create_openai_completer()
        # OpenAI 的 doc_completer 需要 system + user 双 prompt
        from openai import OpenAI
        _client = OpenAI(
            base_url="https://token-plan-cn.xiaomimimo.com/v1",
            api_key="tp-cxq9g672kqgmcpmgvzhktpk7vucswrn9atq4i4ehwyxc6ngl",
        )
        def doc_completer(system_prompt: str, user_prompt: str) -> str:
            response = _client.chat.completions.create(
                model="mimo-v2.5-pro",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0, max_tokens=8192,
            )
            result = response.choices[0].message.content
            logger.info(f"      ✅ LLM response: {response.usage.total_tokens} tokens")
            return result
        # OpenAI 路径下概览和叶子模块用同一个 completer（本身就没有工具）
        overview_completer = doc_completer
        logger.info(f"   LLM Backend: OpenAI API (mimo-v2.5-pro)")

    # ════════════════════════════════════════════════════════════
    #  步骤 ②  模块聚类
    # ════════════════════════════════════════════════════════════

    logger.info("\n" + "=" * 70)
    logger.info("  步骤 ②  模块聚类 (cluster_modules)")
    logger.info("=" * 70)

    # ── 检查 token 量 ──
    clustering_tokens = get_clustering_input_token_count(leaf_nodes, components)
    logger.info(f"   叶子节点: {len(leaf_nodes)}")
    logger.info(f"   Token 量: {clustering_tokens}")

    # ── 执行聚类 ──
    cluster_output_dir = os.path.dirname(__file__)  # 中间结果保存到项目目录
    module_tree = cluster_modules(
        leaf_nodes=leaf_nodes,
        components=components,
        max_token_per_module=36_369,
        completer=cluster_completer,
        output_dir=cluster_output_dir,
    )

    # ── 打印聚类结果 ──
    if module_tree:
        print(f"\n{'=' * 70}")
        print(f"  模块聚类结果")
        print(f"{'=' * 70}")
        print(f"\n🌳 模块树 ({len(module_tree)} top-level modules):")
        print_module_tree(module_tree, components)
        print()
    else:
        logger.info("   聚类结果: 不需要聚类（token 在阈值内，整体作为一个模块处理）")

    # ── 保存模块树 JSON ──
    tree_output_path = os.path.join(os.path.dirname(__file__), "module_tree.json")
    with open(tree_output_path, "w", encoding="utf-8") as f:
        json.dump(module_tree, f, indent=2, ensure_ascii=False)
    logger.info(f"✓ Module tree saved to {tree_output_path}")

    # ════════════════════════════════════════════════════════════
    #  步骤 ③  生成模块文档
    # ════════════════════════════════════════════════════════════

    logger.info("\n" + "=" * 70)
    logger.info("  步骤 ③  生成模块文档 (generate_documentation)")
    logger.info("=" * 70)

    # ── 配置 ──
    docs_dir = os.path.join(os.path.dirname(__file__), "output_docs")
    repo_name = os.path.basename(repo_path)

    # ── 执行文档生成 ──
    generate_documentation(
        repo_name=repo_name,
        module_tree=module_tree,
        components=components,
        docs_dir=docs_dir,
        completer=doc_completer,
        overview_completer=overview_completer,
    )

    logger.info(f"\n✅ 文档生成完成！输出目录: {docs_dir}")

# 默认路径，方便 IDE 直接 debug 运行（无需命令行参数）
# DEFAULT_REPO_PATH = "/Users/zqy/work/project/nrs-sales-project"
# DEFAULT_REPO_PATH = "/Users/zqy/work/project/nrs-sales-project/utopia-nrs-sales-project-service/src/main/java/com/ke/utopia/nrs/salesproject/service/contract/v2/personal"
DEFAULT_REPO_PATH = "/Users/zqy/work/project/nrs-sales-project/utopia-nrs-sales-project-service/src/main/java/com/ke/utopia/nrs/salesproject/service/contract"
# DEFAULT_REPO_PATH = "/Users/zqy/work/project/nrs-sales-project/utopia-nrs-sales-project-service/src/main/java/com/ke/utopia/nrs/salesproject/service/contract/v2/createcontractpdfbyself"
# ════════════════════════════════════════════════════════════
#  LLM 后端配置：切换此处即可在 OpenAI / Claude Code SDK 之间切换
# ════════════════════════════════════════════════════════════
LLM_BACKEND = "claude_code"  # "openai" 或 "claude_code"

if __name__ == "__main__":
    main()
