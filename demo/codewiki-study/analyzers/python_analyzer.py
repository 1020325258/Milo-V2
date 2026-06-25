"""
Python 语言 Analyzer — 移植自 CodeWiki 的 codewiki/src/be/dependency_analyzer/analyzers/python.py

使用 Python 内置 ast 模块解析源码，提取：
1. 类声明 → Node (component_type="class")
2. 顶层函数声明 → Node (component_type="function")
3. 依赖关系 → CallRelationship:
   - 继承 (class A(B))
   - 函数/方法调用
"""

import ast
import os
import logging
import warnings
from typing import List, Tuple, Optional

from core.models import Node, CallRelationship

logger = logging.getLogger(__name__)


class PythonASTAnalyzer(ast.NodeVisitor):
    """
    使用 Python ast 模块解析源码，提取类、函数和调用关系。

    工作流程：
    1. analyze() → ast.parse → visit
    2. visit_ClassDef → 提取类声明为 Node
    3. visit_FunctionDef / visit_AsyncFunctionDef → 提取顶层函数为 Node
    4. visit_Call → 提取调用关系为 CallRelationship
    """

    # Python 内置函数/类型，不需要记录调用关系
    PYTHON_BUILTINS = {
        "print", "len", "str", "int", "float", "bool", "list", "dict", "tuple", "set",
        "range", "enumerate", "zip", "isinstance", "hasattr", "getattr", "setattr",
        "open", "super", "__import__", "type", "object", "Exception", "ValueError",
        "TypeError", "KeyError", "IndexError", "AttributeError", "ImportError",
        "max", "min", "sum", "abs", "round", "sorted", "reversed", "filter", "map",
        "any", "all", "next", "iter", "callable", "repr", "format", "exec", "eval",
        "staticmethod", "classmethod", "property", "None", "True", "False",
        "NotImplementedError", "RuntimeError", "StopIteration", "OSError",
        "FileNotFoundError", "PermissionError", "ConnectionError", "TimeoutError",
    }

    def __init__(self, file_path: str, content: str, repo_path: Optional[str] = None):
        self.file_path = file_path
        self.repo_path = repo_path
        self.content = content
        self.lines = content.splitlines()
        self.nodes: List[Node] = []
        self.call_relationships: List[CallRelationship] = []
        self.current_class_name: Optional[str] = None
        self.current_function_name: Optional[str] = None

        # 名称 → Node 的索引（用于关系解析）
        self.top_level_nodes = {}

    # ────────── 路径/名称工具方法 ──────────

    def _get_relative_path(self) -> str:
        """获取相对于仓库根目录的路径"""
        if self.repo_path:
            return os.path.relpath(self.file_path, self.repo_path)
        return str(self.file_path)

    def _get_module_path(self) -> str:
        """将文件路径转为 Python 模块路径（如 a/b/c.py → a.b.c）"""
        relative_path = self._get_relative_path()
        path = relative_path
        for ext in [".py", ".pyx"]:
            if path.endswith(ext):
                path = path[:-len(ext)]
                break
        return path.replace("/", ".").replace("\\", ".")

    def _get_component_id(self, name: str) -> str:
        """生成组件 ID: 相对路径::名称"""
        rel_path = self._get_relative_path()
        if self.current_class_name:
            return f"{rel_path}::{self.current_class_name}.{name}"
        return f"{rel_path}::{name}"

    # ────────── AST 遍历方法 ──────────

    def visit_ClassDef(self, node: ast.ClassDef):
        """访问类定义，提取为 Node 并记录继承关系。"""
        base_classes = [self._extract_base_class_name(base) for base in node.bases]
        base_classes = [name for name in base_classes if name is not None]

        component_id = f"{self._get_relative_path()}::{node.name}"
        relative_path = self._get_relative_path()

        class_node = Node(
            id=component_id,
            name=node.name,
            component_type="class",
            file_path=str(self.file_path),
            relative_path=relative_path,
            source_code="\n".join(self.lines[node.lineno - 1: node.end_lineno or node.lineno]),
            start_line=node.lineno,
            end_line=node.end_lineno,
            has_docstring=bool(ast.get_docstring(node)),
            docstring=ast.get_docstring(node) or "",
            parameters=None,
            node_type="class",
            base_classes=base_classes if base_classes else None,
            class_name=None,
            display_name=f"class {node.name}",
            component_id=component_id,
            language="python",
            qualified_name=self._get_module_path() + "." + node.name if self._get_module_path() else node.name,
        )
        self.nodes.append(class_node)
        self.top_level_nodes[node.name] = class_node

        # 记录继承关系（仅项目内的基类）
        for base_name in base_classes:
            if base_name in self.top_level_nodes:
                self.call_relationships.append(CallRelationship(
                    caller=component_id,
                    callee=f"{self._get_relative_path()}::{base_name}",
                    call_line=node.lineno,
                    is_resolved=True,
                ))

        # 遍历类体，提取方法
        self.current_class_name = node.name
        self.generic_visit(node)
        self.current_class_name = None

    def _extract_base_class_name(self, base) -> Optional[str]:
        """从 AST 节点提取基类名称"""
        if isinstance(base, ast.Name):
            return base.id
        elif isinstance(base, ast.Attribute):
            parts = []
            node = base
            while isinstance(node, ast.Attribute):
                parts.append(node.attr)
                node = node.value
            if isinstance(node, ast.Name):
                parts.append(node.id)
            return ".".join(reversed(parts))
        return None

    def _process_function_node(self, node):
        """
        处理函数定义。
        - 顶层函数：创建 Node 并加入索引
        - 类方法：不创建独立 Node（归属于类），但记录当前函数名用于调用关系
        """
        if not self.current_class_name:
            # 顶层函数
            component_id = f"{self._get_relative_path()}::{node.name}"
            relative_path = self._get_relative_path()

            func_node = Node(
                id=component_id,
                name=node.name,
                component_type="function",
                file_path=str(self.file_path),
                relative_path=relative_path,
                source_code="\n".join(self.lines[node.lineno - 1: node.end_lineno or node.lineno]),
                start_line=node.lineno,
                end_line=node.end_lineno,
                has_docstring=bool(ast.get_docstring(node)),
                docstring=ast.get_docstring(node) or "",
                parameters=[arg.arg for arg in node.args.args if arg.arg != "self"],
                node_type="function",
                base_classes=None,
                class_name=None,
                display_name=f"function {node.name}",
                component_id=component_id,
                language="python",
                qualified_name=self._get_module_path() + "." + node.name if self._get_module_path() else node.name,
            )
            if self._should_include_function(func_node):
                self.nodes.append(func_node)
                self.top_level_nodes[node.name] = func_node

        self.current_function_name = node.name
        self.generic_visit(node)
        self.current_function_name = None

    def _should_include_function(self, func: Node) -> bool:
        """过滤测试函数等不需要分析的函数"""
        if func.name.startswith("_test_"):
            return False
        return True

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._process_function_node(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._process_function_node(node)

    def visit_Call(self, node: ast.Call):
        """访问函数调用，记录调用者 → 被调用者的关系。"""
        if self.current_class_name or self.current_function_name:
            call_name = self._get_call_name(node.func)
            if call_name:
                if self.current_class_name:
                    caller_id = f"{self._get_relative_path()}::{self.current_class_name}"
                else:
                    caller_id = f"{self._get_relative_path()}::{self.current_function_name}"

                if call_name in self.top_level_nodes:
                    callee_id = f"{self._get_relative_path()}::{call_name}"
                else:
                    callee_id = call_name

                self.call_relationships.append(CallRelationship(
                    caller=caller_id,
                    callee=callee_id,
                    call_line=node.lineno,
                    is_resolved=call_name in self.top_level_nodes,
                ))

        self.generic_visit(node)

    def _get_call_name(self, node) -> Optional[str]:
        """
        从调用节点提取函数名。
        支持简单名称、属性访问 (obj.method)，并过滤内置函数。
        """
        if isinstance(node, ast.Name):
            if node.id in self.PYTHON_BUILTINS:
                return None
            return node.id
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                if node.value.id in self.PYTHON_BUILTINS:
                    return None
                return f"{node.value.id}.{node.attr}"
            elif isinstance(node.value, ast.Attribute):
                base_name = self._get_call_name(node.value)
                if base_name:
                    return f"{base_name}.{node.attr}"
            return node.attr
        return None

    # ────────── 主分析入口 ──────────

    def analyze(self):
        """解析 Python 文件，提取组件和调用关系。"""
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=SyntaxWarning)
                tree = ast.parse(self.content)
            self.visit(tree)

            logger.debug(
                f"Python analysis complete for {self.file_path}: {len(self.nodes)} nodes, "
                f"{len(self.call_relationships)} relationships"
            )
        except SyntaxError as e:
            logger.warning(f"Could not parse {self.file_path}: {e}")
        except Exception as e:
            logger.error(f"Error analyzing {self.file_path}: {e}", exc_info=True)


def analyze_python_file(
    file_path: str, content: str, repo_path: Optional[str] = None
) -> Tuple[List[Node], List[CallRelationship]]:
    """
    分析单个 Python 文件，返回 (组件列表, 调用关系列表)。

    这是外部调用的入口函数，与 analyze_java_file 对应。
    """
    analyzer = PythonASTAnalyzer(file_path, content, repo_path)
    analyzer.analyze()
    return analyzer.nodes, analyzer.call_relationships
