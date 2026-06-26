"""
依赖图构建与拓扑排序 — 对应 CodeWiki 的:
- codewiki/src/be/dependency_analyzer/topo_sort.py
- codewiki/src/be/dependency_analyzer/dependency_graphs_builder.py

核心功能：
1. build_graph_from_components() — 从组件字典构建有向图
2. get_leaf_nodes() — 找不被任何组件依赖的"叶子"节点
3. topological_sort() — 拓扑排序（依赖在前）
4. detect_cycles() — Tarjan 算法检测环
5. resolve_cycles() — 打破循环依赖
"""

import logging
from typing import Dict, List, Set, Any
from collections import deque

from core.models import Node

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 图构建
# ─────────────────────────────────────────────────────────────

def build_graph_from_components(components: Dict[str, Node]) -> Dict[str, Set[str]]:
    """
    从组件字典构建有向图。

    图的方向: A → B 表示 "A 依赖 B"（A 的 depends_on 中包含 B）

    Args:
        components: 组件字典，key 是组件 ID，value 是 Node

    Returns:
        邻接表: {node_id: {dep_id_1, dep_id_2, ...}}

    示例:
        components = {
            "A": Node(depends_on={"B", "C"}),
            "B": Node(depends_on={"C"}),
            "C": Node(depends_on=set()),
        }
        → graph = {"A": {"B", "C"}, "B": {"C"}, "C": set()}
    """
    graph = {}

    for comp_id, component in components.items():
        if comp_id not in graph:
            graph[comp_id] = set()

        for dep_id in component.depends_on:
            # 只保留仓库内的依赖（过滤掉外部库的引用）
            if dep_id in components:
                graph[comp_id].add(dep_id)

    return graph


# ─────────────────────────────────────────────────────────────
# 环检测（Tarjan 算法）
# ─────────────────────────────────────────────────────────────

def detect_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """
    用 Tarjan 算法检测有向图中的强连通分量（SCC）。
    大小 > 1 的 SCC 就是环。

    Args:
        graph: 邻接表 {node: {neighbors}}

    Returns:
        环的列表，每个环是一个节点列表

    示例:
        A → B → C → A  (环)
        → [["A", "B", "C"]]
    """
    index_counter = [0]
    index = {}       # 节点 → 发现顺序
    lowlink = {}     # 节点 → 能回溯到的最小 index
    onstack = set()  # 当前栈中的节点
    stack = []
    result = []

    def strongconnect(node):
        index[node] = index_counter[0]
        lowlink[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        onstack.add(node)

        for successor in graph.get(node, set()):
            if successor not in index:
                strongconnect(successor)
                lowlink[node] = min(lowlink[node], lowlink[successor])
            elif successor in onstack:
                lowlink[node] = min(lowlink[node], index[successor])

        # 如果是 SCC 的根节点，弹出整个 SCC
        if lowlink[node] == index[node]:
            scc = []
            while True:
                successor = stack.pop()
                onstack.remove(successor)
                scc.append(successor)
                if successor == node:
                    break
            # 只保留大小 > 1 的 SCC（真正的环）
            if len(scc) > 1:
                result.append(scc)

    for node in graph:
        if node not in index:
            strongconnect(node)

    return result


def resolve_cycles(graph: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    """
    打破图中的环，使其变为 DAG。
    策略: 对每个环，移除最后一条边。

    Args:
        graph: 可能含环的邻接表

    Returns:
        无环的邻接表
    """
    cycles = detect_cycles(graph)

    if not cycles:
        logger.debug("No cycles detected in the dependency graph")
        return graph

    logger.debug(f"Detected {len(cycles)} cycles in the dependency graph")

    new_graph = {node: deps.copy() for node, deps in graph.items()}

    for i, cycle in enumerate(cycles):
        logger.debug(f"Cycle {i+1}: {' -> '.join(cycle)}")
        for j in range(len(cycle) - 1):
            current = cycle[j]
            next_node = cycle[j + 1]
            if next_node in new_graph[current]:
                logger.debug(f"Breaking cycle: removing {current} -> {next_node}")
                new_graph[current].remove(next_node)
                break

    return new_graph


# ─────────────────────────────────────────────────────────────
# 拓扑排序
# ─────────────────────────────────────────────────────────────

def topological_sort(graph: Dict[str, Set[str]]) -> List[str]:
    """
    拓扑排序: 依赖在前，被依赖在后。

    使用 Kahn 算法（BFS 方式）：
    1. 找入度为 0 的节点（无依赖的节点）
    2. 将其加入结果，移除其出边
    3. 重复直到所有节点处理完毕

    Args:
        graph: 邻接表 {node: {deps}}，A → B 表示 A 依赖 B

    Returns:
        拓扑序列表，依赖在前

    示例:
        A → B → C
        → [C, B, A]  （C 是最底层依赖，排在最前）
    """
    acyclic_graph = resolve_cycles(graph)

    # 计算入度
    in_degree = {node: 0 for node in acyclic_graph}
    for node, dependencies in acyclic_graph.items():
        for dep in dependencies:
            if dep in in_degree:
                in_degree[dep] += 1

    # BFS
    queue = deque([node for node, degree in in_degree.items() if degree == 0])
    result = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for dependent, deps in acyclic_graph.items():
            if node in deps:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

    if len(result) != len(acyclic_graph):
        logger.warning("Topological sort failed: unresolved cycles remain")
        return list(acyclic_graph.keys())

    # 反转：让依赖在前
    return result[::-1]


def get_leaf_nodes(graph: Dict[str, Set[str]], components: Dict[str, Node]) -> List[str]:
    """
    找叶子节点 — 用于聚类的入口组件。

    与 CodeWiki 保持一致的两阶段筛选：
    1. 先按组件类型过滤（只保留 class/interface/struct 等）
    2. 如果过滤后仍 ≥ 400 个，再按依赖图过滤（只保留不被依赖的节点）

    Args:
        graph: 邻接表 {node: {deps}}
        components: 组件字典

    Returns:
        叶子节点 ID 列表
    """
    acyclic_graph = resolve_cycles(graph)
    all_nodes = set(acyclic_graph.keys())

    # ── 第一步：按组件类型过滤 ──
    valid_types = {"class", "interface", "struct", "enum", "abstract class", "record"}

    # 如果没有上述类型，则保留 function/method
    available_types = {components[n].component_type for n in all_nodes if n in components}
    if not available_types.intersection(valid_types):
        valid_types.add("function")
        valid_types.add("method")

    concise_nodes = [
        node for node in all_nodes
        if node in components and components[node].component_type in valid_types
    ]

    # ── 第二步：≥ 400 时按依赖图过滤（与 CodeWiki 一致）──
    if len(concise_nodes) >= 400:
        logger.info(
            "Leaf nodes too many (%d), applying graph-theoretic filtering",
            len(concise_nodes),
        )
        depended_on = set()
        for node, deps in acyclic_graph.items():
            for dep in deps:
                depended_on.add(dep)

        concise_nodes = [
            node for node in concise_nodes
            if node not in depended_on
        ]

    return sorted(concise_nodes)
