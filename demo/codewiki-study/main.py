#!/usr/bin/env python3
"""
CodeWiki 源码解析 Demo — 可独立运行

三个核心步骤：
  ① 解析源码 & 构建依赖图
  ② LLM 驱动的递归模块聚类
  ③ 按模块树生成文档

支持语言: Java (.java) / Python (.py)

用法:
    python main.py                        # 使用默认路径
    python main.py /path/to/your/project  # 指定路径
"""

import os
import sys
import json
import logging
import time
from typing import Dict, List
from collections import defaultdict

from core.models import Node, CallRelationship
from analyzers.java_analyzer import analyze_java_file
from analyzers.python_analyzer import analyze_python_file
from core.graph_builder import build_graph_from_components, get_leaf_nodes
from core.cluster_modules import cluster_modules, print_module_tree, get_clustering_input_token_count
from core.doc_generator import generate_documentation
from core.llm_backends import create_backends

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════════════════════════

def main():
    # ── 初始化 ──
    repo_path = _resolve_repo_path()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    log_path = _setup_log_file()

    print(f"\n🔍 CodeWiki 源码解析")
    print(f"   仓库: {repo_path}")
    print(f"   输出: {OUTPUT_DIR}")
    print(f"   日志: {log_path}\n")

    # ── ① 解析源码 & 构建依赖图 ──
    components, leaf_nodes = step1_build_dependency_graph(repo_path)

    # ── ② 模块聚类 ──
    module_tree = step2_cluster_modules(leaf_nodes, components)

    # ── ③ 生成文档 ──
    step3_generate_docs(repo_path, module_tree, components)


# ═══════════════════════════════════════════════════════════════
#  步骤实现
# ═══════════════════════════════════════════════════════════════

def step1_build_dependency_graph(repo_path: str):
    """① 扫描源码 → 解析组件 → 构建依赖图 → 找叶子节点"""
    logger.info("=" * 50)
    logger.info("  步骤 ①  解析源码 & 构建依赖图")
    logger.info("=" * 50)

    # 扫描文件
    code_files = _scan_code_files(repo_path)
    if not code_files:
        print("未找到支持的源码文件（.java / .py），退出。")
        sys.exit(0)

    # 解析组件
    components = _parse_all_files(code_files, repo_path)

    # 构建依赖图
    graph = build_graph_from_components(components)
    logger.info(f"   依赖图: {len(graph)} nodes, {sum(len(d) for d in graph.values())} edges")

    # 找叶子节点
    leaf_nodes = get_leaf_nodes(graph, components)
    logger.info(f"   叶子节点: {len(leaf_nodes)}")

    # 保存依赖图
    dep_graph_path = os.path.join(OUTPUT_DIR, "dependency_graph.json")
    _save_json(components, dep_graph_path, serialize_sets=True)

    return components, leaf_nodes


def step2_cluster_modules(leaf_nodes: List[str], components: Dict[str, Node]) -> dict:
    """② LLM 驱动的递归模块聚类"""
    logger.info("\n" + "=" * 50)
    logger.info("  步骤 ②  模块聚类")
    logger.info("=" * 50)

    tree_path = os.path.join(OUTPUT_DIR, "module_tree.json")

    # 缓存命中
    if os.path.exists(tree_path):
        with open(tree_path, "r", encoding="utf-8") as f:
            module_tree = json.load(f)
        logger.info(f"   ✓ 使用缓存: {len(module_tree)} 个模块")
        return module_tree

    # 创建聚类用 completer
    cluster_completer, _, _ = create_backends(LLM_BACKEND, OUTPUT_DIR, SCRIPT_DIR, components)

    # 检查 token 量
    tokens = get_clustering_input_token_count(leaf_nodes, components)
    logger.info(f"   叶子节点: {len(leaf_nodes)}, Token: {tokens}")

    # 聚类
    module_tree = cluster_modules(
        leaf_nodes=leaf_nodes,
        components=components,
        max_token_per_module=36_369,
        completer=cluster_completer,
    )

    # 保存
    _save_json(module_tree, tree_path)

    if module_tree:
        print(f"\n🌳 模块树 ({len(module_tree)} modules):")
        print_module_tree(module_tree, components)
    else:
        logger.info("   聚类结果: token 在阈值内，整体作为一个模块处理")

    return module_tree


def step3_generate_docs(repo_path: str, module_tree: dict, components: Dict[str, Node]):
    """③ 按模块树生成文档"""
    logger.info("\n" + "=" * 50)
    logger.info("  步骤 ③  生成文档")
    logger.info("=" * 50)

    # 创建文档生成用 completer
    _, doc_completer, overview_completer = create_backends(LLM_BACKEND, OUTPUT_DIR, SCRIPT_DIR, components)

    docs_dir = os.path.join(OUTPUT_DIR, "docs")
    repo_name = os.path.basename(repo_path)

    generate_documentation(
        repo_name=repo_name,
        module_tree=module_tree,
        components=components,
        docs_dir=docs_dir,
        completer=doc_completer,
        overview_completer=overview_completer,
    )

    logger.info(f"\n✅ 完成！文档目录: {docs_dir}")


# ═══════════════════════════════════════════════════════════════
#  内部工具函数
# ═══════════════════════════════════════════════════════════════

LANGUAGE_EXTENSIONS = {".java": "java", ".py": "python"}
SKIP_DIRS = {"__pycache__", "node_modules", "target", "build", ".git", ".idea",
             ".venv", "venv", ".mypy_cache", ".pytest_cache", "dist", ".tox", "egg-info"}


def _resolve_repo_path() -> str:
    if len(sys.argv) >= 2:
        return os.path.abspath(sys.argv[1])
    print(f"(未指定路径，使用默认: {DEFAULT_REPO_PATH})")
    return DEFAULT_REPO_PATH


def _setup_log_file() -> str:
    from datetime import datetime
    logs_dir = os.path.join(OUTPUT_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_path = os.path.join(logs_dir, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    logging.getLogger().addHandler(fh)
    return log_path


def _scan_code_files(repo_path: str) -> List[Dict[str, str]]:
    """递归扫描目录，收集 .java / .py 文件"""
    code_files = []
    repo_path = os.path.abspath(repo_path)
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS]
        for filename in sorted(files):
            ext = os.path.splitext(filename)[1]
            language = LANGUAGE_EXTENSIONS.get(ext)
            if language:
                full_path = os.path.join(root, filename)
                code_files.append({
                    "path": full_path,
                    "relative_path": os.path.relpath(full_path, repo_path),
                    "name": filename,
                    "language": language,
                })
    lang_counts = defaultdict(int)
    for f in code_files:
        lang_counts[f["language"]] += 1
    for lang, count in sorted(lang_counts.items()):
        logger.info(f"   {lang}: {count} files")
    return code_files


def _parse_all_files(code_files: List[Dict[str, str]], repo_path: str) -> Dict[str, Node]:
    """逐文件解析组件和调用关系"""
    analyzers = {"java": analyze_java_file, "python": analyze_python_file}
    components: Dict[str, Node] = {}
    all_relationships: List[CallRelationship] = []
    t0 = time.time()

    for idx, fi in enumerate(code_files, 1):
        analyzer = analyzers.get(fi["language"])
        if not analyzer:
            continue
        try:
            with open(fi["path"], "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            nodes, rels = analyzer(fi["path"], content, repo_path)
            for n in nodes:
                components[n.id] = n
            all_relationships.extend(rels)
            logger.info(f"  [{idx}/{len(code_files)}] [{fi['language']}] {fi['relative_path']} → {len(nodes)} components, {len(rels)} rels")
        except Exception as e:
            logger.warning(f"  [{idx}/{len(code_files)}] Failed: {fi['relative_path']}: {e}")

    # 解析调用关系
    _resolve_call_relationships(components, all_relationships)

    elapsed = time.time() - t0
    logger.info(f"\n✓ 解析完成: {len(code_files)} files, {len(components)} components, {len(all_relationships)} rels ({elapsed:.1f}s)")
    return components


def _resolve_call_relationships(components: Dict[str, Node], relationships: List[CallRelationship]):
    """将 callee 名称解析为实际组件 ID，写入 depends_on"""
    exact_idx: Dict[str, List[str]] = defaultdict(list)
    simple_idx: Dict[str, List[str]] = defaultdict(list)

    for cid, comp in components.items():
        exact_idx[cid].append(cid)
        if comp.qualified_name:
            exact_idx[comp.qualified_name].append(cid)
        exact_idx[comp.name].append(cid)
        simple_idx[comp.name].append(cid)
        if comp.qualified_name:
            simple_idx[comp.qualified_name.split(".")[-1]].append(cid)
        if "::" in cid:
            simple_idx[cid.split("::")[-1]].append(cid)

    resolved = 0
    for rel in relationships:
        if rel.is_resolved and rel.callee in components:
            if rel.caller in components:
                components[rel.caller].depends_on.add(rel.callee)
            resolved += 1
            continue

        rid = None
        if rel.callee in exact_idx and len(exact_idx[rel.callee]) == 1:
            rid = exact_idx[rel.callee][0]
        if not rid:
            sn = rel.callee.split(".")[-1] if "." in rel.callee else rel.callee
            if sn in simple_idx and len(simple_idx[sn]) == 1:
                rid = simple_idx[sn][0]
        if rid and rid in components:
            rel.callee = rid
            rel.is_resolved = True
            if rel.caller in components:
                components[rel.caller].depends_on.add(rid)
            resolved += 1

    logger.info(f"   调用关系解析: {resolved}/{len(relationships)}")


def _save_json(data, path: str, serialize_sets: bool = False):
    """保存 JSON 文件"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if serialize_sets:
            def default_ser(obj):
                if isinstance(obj, set):
                    return sorted(list(obj))
                raise TypeError(f"Type {type(obj)} not serializable")
            json.dump(data, f, indent=2, ensure_ascii=False, default=default_ser)
        else:
            json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"✓ Saved: {path}")


# ═══════════════════════════════════════════════════════════════
#  配置
# ═══════════════════════════════════════════════════════════════

DEFAULT_REPO_PATH = "/Users/zqy/work/project/nrs-sales-project/utopia-nrs-sales-project-service/src/main/java/com/ke/utopia/nrs/salesproject/service/contract/v2/personal"
LLM_BACKEND = "claude_code"  # "openai" 或 "claude_code"

if __name__ == "__main__":
    main()
