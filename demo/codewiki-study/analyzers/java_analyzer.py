"""
Java 语言 Analyzer — 对应 CodeWiki 的 codewiki/src/be/dependency_analyzer/analyzers/java.py

使用 tree-sitter 解析 Java 源码，提取：
1. 类/接口/枚举/记录等类型声明 → Node
2. 方法声明 → Node
3. 五种依赖关系 → CallRelationship:
   - 继承 (extends)
   - 实现 (implements)
   - 字段类型引用
   - 方法调用
   - 对象创建 (new)
"""

import os
import re
import logging
from typing import List, Tuple, Optional
from pathlib import Path

from tree_sitter import Parser, Language
import tree_sitter_java

from core.models import Node, CallRelationship

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Java 外部符号过滤（简化版，对应 CodeWiki 的 external_symbols.py）
# 过滤掉 JDK/第三方库的类型，只保留项目内的依赖关系
# ─────────────────────────────────────────────────────────────

# java.lang 常见类型（不需要 import 就能用）
JAVA_LANG_TYPES = {
    "Object", "String", "Integer", "Long", "Double", "Float", "Boolean",
    "Byte", "Short", "Character", "Void", "Class", "Number", "Enum",
    "Exception", "RuntimeException", "Throwable", "Error",
    "StringBuilder", "StringBuffer", "Math", "System", "Thread",
    "Runnable", "Comparable", "Iterable", "Cloneable",
    "Override", "Deprecated", "SuppressWarnings", "FunctionalInterface",
}

# java.lang.Object 的方法（所有类都继承）
JAVA_OBJECT_METHODS = {
    "equals", "hashCode", "toString", "getClass", "clone", "finalize",
    "notify", "notifyAll", "wait",
}

# JDK 包前缀
JDK_PACKAGE_PREFIXES = (
    "java.", "javax.", "jdk.", "sun.", "com.sun.",
    "org.xml.", "org.w3c.", "org.ietf.", "org.jcp.",
)

# 常见第三方库前缀（按需扩展）
THIRD_PARTY_PREFIXES = (
    "org.springframework.", "org.apache.", "com.alibaba.",
    "cn.hutool.", "com.google.", "org.slf4j.", "ch.qos.logback.",
    "lombok.", "org.junit.", "org.mockito.",
)


def is_external_symbol(language: str, qualified_name: str) -> bool:
    """判断一个全限定名是否是外部符号（JDK/第三方库）"""
    for prefix in JDK_PACKAGE_PREFIXES:
        if qualified_name.startswith(prefix):
            return True
    for prefix in THIRD_PARTY_PREFIXES:
        if qualified_name.startswith(prefix):
            return True
    return False


# ─────────────────────────────────────────────────────────────
# Java AST Analyzer（核心逻辑）
# ─────────────────────────────────────────────────────────────

class TreeSitterJavaAnalyzer:
    """
    使用 tree-sitter 解析 Java 文件，提取组件和调用关系。

    工作流程：
    1. _analyze() → 解析 AST
    2. _extract_nodes() → 遍历 AST 提取类/接口/方法声明 → Node
    3. _extract_relationships() → 遍历 AST 提取依赖关系 → CallRelationship
    """

    def __init__(self, file_path: str, content: str, repo_path: str = None):
        self.file_path = Path(file_path)
        self.content = content
        self.repo_path = repo_path or ""
        self.nodes: List[Node] = []
        self.call_relationships: List[CallRelationship] = []
        self.package_name = self._extract_package_name()
        self.import_map, self.wildcard_imports = self._extract_imports()
        self._analyze()

    # ────────── 路径/名称工具方法 ──────────

    def _get_relative_path(self) -> str:
        """获取相对于仓库根目录的路径"""
        if self.repo_path:
            try:
                return os.path.relpath(str(self.file_path), self.repo_path)
            except ValueError:
                return str(self.file_path)
        return str(self.file_path)

    def _get_component_id(self, name: str) -> str:
        """生成组件 ID: 相对路径::名称"""
        rel_path = self._get_relative_path()
        return f"{rel_path}::{name}"

    def _extract_package_name(self) -> str:
        """从源码中提取 package 声明"""
        match = re.search(r"^\s*package\s+([\w.]+)\s*;", self.content, re.MULTILINE)
        return match.group(1) if match else ""

    def _extract_imports(self) -> tuple[dict[str, str], list[str]]:
        """
        提取 import 语句，构建映射表：
        - import_map: 简单名 → 全限定名，如 "LoginService" → "com.xxx.LoginService"
        - wildcards: 通配符导入，如 "com.xxx.*" → "com.xxx"
        """
        import_map: dict[str, str] = {}
        wildcards: list[str] = []
        for match in re.finditer(
            r"^\s*import\s+(?:static\s+)?([\w.]+)(\.\*)?\s*;",
            self.content, re.MULTILINE
        ):
            import_name = match.group(1)
            if match.group(2):
                wildcards.append(import_name)
            else:
                import_map[import_name.rsplit(".", 1)[-1]] = import_name
        return import_map, wildcards

    # ────────── 核心分析方法 ──────────

    def _analyze(self):
        """主分析入口：解析 AST → 提取节点 → 提取关系"""
        language_capsule = tree_sitter_java.language()
        java_language = Language(language_capsule)
        parser = Parser(java_language)
        tree = parser.parse(bytes(self.content, "utf8"))
        root = tree.root_node
        lines = self.content.splitlines()

        top_level_nodes = {}  # 名称 → Node 的索引（用于后续关系解析）

        # 第一遍：提取所有类型声明和方法声明
        self._extract_nodes(root, top_level_nodes, lines)

        # 第二遍：提取所有依赖关系
        self._extract_relationships(root, top_level_nodes)

    def _extract_nodes(self, node, top_level_nodes, lines):
        """
        递归遍历 AST，提取类/接口/枚举/方法等声明为 Node。

        tree-sitter Java 的节点类型：
        - class_declaration     → 类
        - interface_declaration → 接口
        - enum_declaration      → 枚举
        - record_declaration    → 记录（Java 16+）
        - annotation_type_declaration → 注解
        - method_declaration    → 方法
        """
        node_type = None
        node_name = None
        qualified_name = None
        class_name = None

        # ── 识别节点类型 ──
        if node.type == "class_declaration":
            is_abstract = any(
                c.type == "modifier" and c.text.decode() == "abstract"
                for c in node.children
            )
            node_type = "abstract class" if is_abstract else "class"
            name_node = next((c for c in node.children if c.type == "identifier"), None)
            node_name = name_node.text.decode() if name_node else None
            qualified_name = self._qualified_type_name(
                node_name, self._find_containing_type_names(node)
            )

        elif node.type == "interface_declaration":
            node_type = "interface"
            name_node = next((c for c in node.children if c.type == "identifier"), None)
            node_name = name_node.text.decode() if name_node else None
            qualified_name = self._qualified_type_name(
                node_name, self._find_containing_type_names(node)
            )

        elif node.type == "enum_declaration":
            node_type = "enum"
            name_node = next((c for c in node.children if c.type == "identifier"), None)
            node_name = name_node.text.decode() if name_node else None
            qualified_name = self._qualified_type_name(
                node_name, self._find_containing_type_names(node)
            )

        elif node.type == "record_declaration":
            node_type = "record"
            name_node = next((c for c in node.children if c.type == "identifier"), None)
            node_name = name_node.text.decode() if name_node else None
            qualified_name = self._qualified_type_name(
                node_name, self._find_containing_type_names(node)
            )

        elif node.type == "annotation_type_declaration":
            node_type = "annotation"
            name_node = next((c for c in node.children if c.type == "identifier"), None)
            node_name = name_node.text.decode() if name_node else None
            qualified_name = self._qualified_type_name(
                node_name, self._find_containing_type_names(node)
            )

        elif node.type == "method_declaration":
            node_type = "method"
            name_node = next((c for c in node.children if c.type == "identifier"), None)
            if name_node:
                method_name = name_node.text.decode()
                containing_types = self._find_containing_type_names(node)
                if containing_types:
                    class_name = containing_types[-1]
                    node_name = f"{class_name}.{method_name}"
                    qualified_name = self._qualified_member_name(containing_types, method_name)
                else:
                    node_name = method_name
                    qualified_name = self._qualify_name(method_name)

        # ── 创建 Node 并加入索引 ──
        if node_type and node_name:
            component_id = self._get_component_id(node_name)
            relative_path = self._get_relative_path()

            # 提取 @AiDoc 注解和 Javadoc
            ai_doc = self._extract_ai_doc(node, lines)
            javadoc = self._extract_javadoc(node, lines)
            docstring = ai_doc if ai_doc else javadoc

            node_obj = Node(
                id=component_id,
                name=node_name,
                component_type=node_type,
                file_path=str(self.file_path),
                relative_path=relative_path,
                source_code="\n".join(lines[node.start_point[0]:node.end_point[0]+1]),
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                has_docstring=bool(docstring),
                docstring=docstring or "",
                parameters=None,
                node_type=node_type,
                base_classes=None,
                class_name=class_name,
                display_name=f"{node_type} {node_name}",
                component_id=component_id,
                language="java",
                qualified_name=qualified_name,
            )
            self.nodes.append(node_obj)

            # 多维度索引：短名、组件ID、全限定名都能找到这个 Node
            top_level_nodes[node_name] = node_obj
            top_level_nodes[component_id] = node_obj
            if qualified_name:
                top_level_nodes[qualified_name] = node_obj
                top_level_nodes.setdefault(qualified_name.split(".")[-1], node_obj)

        # 递归处理子节点
        for child in node.children:
            self._extract_nodes(child, top_level_nodes, lines)

    def _extract_ai_doc(self, node, lines) -> Optional[str]:
        """
        提取 @AiDoc 注解的 summary 和 description。
        在 AST 中查找 class_declaration 前的 annotation 节点。
        """
        # @AiDoc 注解在 class_declaration 的前一行或几行
        # 通过正则从源码中提取更可靠
        start = max(0, node.start_point[0] - 10)  # 往上看 10 行
        context = "\n".join(lines[start:node.start_point[0] + 5])

        match = re.search(
            r'@AiDoc\s*\(\s*summary\s*=\s*"([^"]+)"(?:\s*,\s*description\s*=\s*"([^"]*)")?\s*\)',
            context
        )
        if match:
            summary = match.group(1)
            description = match.group(2) or ""
            if description:
                return f"[AI] {summary}\n{description}"
            return f"[AI] {summary}"
        return None

    def _extract_javadoc(self, node, lines) -> Optional[str]:
        """提取类/方法上方的 Javadoc 注释"""
        start = max(0, node.start_point[0] - 20)
        context_lines = lines[start:node.start_point[0]]
        context = "\n".join(context_lines)

        # 匹配 /** ... */ 格式的 Javadoc
        match = re.search(r'/\*\*(.*?)\*/', context, re.DOTALL)
        if match:
            doc = match.group(1)
            # 清理 * 前缀
            doc = re.sub(r'^\s*\*\s?', '', doc, flags=re.MULTILINE)
            doc = doc.strip()
            if doc:
                return doc
        return None

    def _extract_relationships(self, node, top_level_nodes):
        """
        递归遍历 AST，提取五种依赖关系：

        1. 继承:       class A extends B        → A depends_on B
        2. 实现:       class A implements B      → A depends_on B
        3. 字段类型:   private B field;          → A depends_on B
        4. 方法调用:   obj.method() / B.static() → caller depends_on B.method
        5. 对象创建:   new B()                   → A depends_on B
        """

        # ── 1. 继承关系 ──
        if node.type == "class_declaration":
            class_name = self._get_identifier_name(node)
            extends_node = next((c for c in node.children if c.type == "superclass"), None)
            if extends_node:
                base_class_name = self._get_type_name(extends_node)
                if class_name and base_class_name and not self._skip_type(base_class_name, node):
                    caller_id = self._get_component_id(class_name)
                    callee_id = self._resolve_java_type(base_class_name, node, top_level_nodes)
                    self.call_relationships.append(CallRelationship(
                        caller=caller_id,
                        callee=callee_id,
                        call_line=node.start_point[0] + 1,
                        is_resolved=False,
                    ))

        # ── 2. 实现关系 ──
        if node.type in ["class_declaration", "enum_declaration", "record_declaration"]:
            implementer_name = self._get_identifier_name(node)
            implements_node = next(
                (c for c in node.children if c.type == "super_interfaces"), None
            )
            if implements_node and implementer_name:
                for child in implements_node.children:
                    if child.type == "type_list":
                        for type_child in child.children:
                            if type_child.type in ["type_identifier", "generic_type"]:
                                interface_name = self._get_type_name(type_child)
                                if interface_name and not self._skip_type(interface_name, node):
                                    caller_id = self._get_component_id(implementer_name)
                                    callee_id = self._resolve_java_type(
                                        interface_name, node, top_level_nodes
                                    )
                                    self.call_relationships.append(CallRelationship(
                                        caller=caller_id,
                                        callee=callee_id,
                                        call_line=node.start_point[0] + 1,
                                        is_resolved=False,
                                    ))

        # ── 3. 字段类型引用 ──
        if node.type == "field_declaration":
            containing_class = self._find_containing_class(node, top_level_nodes)
            type_node = next(
                (c for c in node.children if c.type in ["type_identifier", "generic_type"]),
                None,
            )
            if containing_class and type_node:
                field_type_name = self._get_type_name(type_node)
                if field_type_name and not self._skip_type(field_type_name, node):
                    self.call_relationships.append(CallRelationship(
                        caller=containing_class,
                        callee=self._resolve_java_type(field_type_name, node, top_level_nodes),
                        call_line=node.start_point[0] + 1,
                        is_resolved=False,
                    ))

        # ── 4. 方法调用 ──
        if node.type == "method_invocation":
            containing_class = self._find_containing_class(node, top_level_nodes)
            containing_method = self._find_containing_method(node)
            if containing_class:
                object_name = None
                method_name = None

                identifiers = [
                    child.text.decode()
                    for child in node.children
                    if child.type == "identifier"
                ]
                if len(identifiers) >= 2:
                    object_name = identifiers[0]
                    method_name = identifiers[1]
                elif identifiers:
                    method_name = identifiers[0]

                if method_name:
                    target_type = None
                    caller_id = containing_method or containing_class

                    # 静态调用: ClassName.method()
                    if object_name and object_name[:1].isupper() and object_name in top_level_nodes:
                        target_type = object_name
                    # 实例调用: variable.method()
                    elif object_name:
                        target_type = self._find_variable_type(node, object_name, top_level_nodes)
                        if not target_type and object_name in top_level_nodes:
                            target_type = object_name
                        if not target_type and object_name[:1].isupper() and not object_name.isupper():
                            target_type = object_name  # CamelCase 可能是外部类型

                    if target_type and not self._skip_type(target_type, node):
                        callee = self._resolve_java_member(
                            method_name, node, top_level_nodes, target_type
                        )
                        # 过滤掉继承自 Object 的方法
                        if callee not in top_level_nodes and method_name in JAVA_OBJECT_METHODS:
                            callee = None
                        if callee:
                            self.call_relationships.append(CallRelationship(
                                caller=caller_id,
                                callee=callee,
                                call_line=node.start_point[0] + 1,
                                is_resolved=False,
                            ))
                    elif not object_name:
                        # 无前缀的方法调用（本类方法或静态导入）
                        callee = self._resolve_java_member(method_name, node, top_level_nodes)
                        if callee in top_level_nodes or self.import_map.get(method_name) == callee:
                            self.call_relationships.append(CallRelationship(
                                caller=caller_id,
                                callee=callee,
                                call_line=node.start_point[0] + 1,
                                is_resolved=False,
                            ))

        # ── 5. 对象创建 ──
        if node.type == "object_creation_expression":
            containing_class = self._find_containing_class(node, top_level_nodes)
            type_node = next(
                (c for c in node.children if c.type in ["type_identifier", "generic_type"]),
                None,
            )
            if containing_class and type_node:
                created_type = self._get_type_name(type_node)
                if created_type and not self._skip_type(created_type, node):
                    self.call_relationships.append(CallRelationship(
                        caller=containing_class,
                        callee=self._resolve_java_type(created_type, node, top_level_nodes),
                        call_line=node.start_point[0] + 1,
                        is_resolved=False,
                    ))

        # 递归处理子节点
        for child in node.children:
            self._extract_relationships(child, top_level_nodes)

    # ────────── 类型解析方法 ──────────

    def _is_primitive_type(self, type_name: str) -> bool:
        """判断是否是 Java 基本类型或 JDK 类型"""
        primitives = {"boolean", "byte", "char", "double", "float", "int", "long", "short", "void", "var"}
        simple = self._simple_type_name(type_name)
        if simple in primitives:
            return True
        if simple in JAVA_LANG_TYPES:
            return True
        # 通过 import 映射判断全限定名
        qualified = self.import_map.get(simple)
        if qualified is None:
            for wildcard in self.wildcard_imports:
                if is_external_symbol("java", f"{wildcard}.{simple}"):
                    return True
            qualified = simple
        return is_external_symbol("java", qualified)

    def _resolve_java_type(self, type_name: str, context_node=None, top_level_nodes=None) -> str:
        """
        将简单类型名解析为全限定名。
        优先级: import 映射 > 包内类 > 当前包前缀
        """
        if not type_name:
            return type_name
        type_name = self._simple_type_name(type_name)
        if "." in type_name:
            return type_name
        if type_name in self.import_map:
            return self.import_map[type_name]
        if context_node is not None and top_level_nodes is not None:
            containing_types = self._find_containing_type_names(context_node)
            for idx in range(len(containing_types), 0, -1):
                candidate = self._qualify_name(".".join([*containing_types[:idx], type_name]))
                if candidate in top_level_nodes:
                    return candidate
        if self.package_name:
            return f"{self.package_name}.{type_name}"
        return type_name

    def _resolve_java_member(
        self, member_name: str, context_node, top_level_nodes, target_type: str = None
    ) -> str:
        """解析方法调用的目标，返回全限定的方法名"""
        if target_type:
            qualified_type = self._resolve_java_type(target_type, context_node, top_level_nodes)
            candidate = f"{qualified_type}.{member_name}"
            if candidate in top_level_nodes:
                return candidate
            simple_type = qualified_type.split(".")[-1]
            simple_candidate = f"{simple_type}.{member_name}"
            if simple_candidate in top_level_nodes:
                return simple_candidate
            return candidate

        containing_types = self._find_containing_type_names(context_node)
        for idx in range(len(containing_types), 0, -1):
            candidate = self._qualified_member_name(containing_types[:idx], member_name)
            if candidate in top_level_nodes:
                return candidate
        if member_name in self.import_map:
            return self.import_map[member_name]
        return self._qualify_name(member_name)

    def _skip_type(self, type_name: str, context_node) -> bool:
        """判断是否应跳过该类型（基本类型、JDK 类型、泛型参数）"""
        if self._is_primitive_type(type_name):
            return True
        return self._simple_type_name(type_name) in self._find_type_parameters(context_node)

    # ────────── AST 辅助方法 ──────────

    def _find_type_parameters(self, node) -> set:
        """查找当前作用域内的泛型参数名（如 K, V, T）"""
        params = set()
        current = node
        while current:
            if current.type in [
                "class_declaration", "interface_declaration",
                "record_declaration", "method_declaration",
            ]:
                type_parameters = next(
                    (c for c in current.children if c.type == "type_parameters"), None
                )
                if type_parameters:
                    for param in type_parameters.children:
                        if param.type == "type_parameter":
                            for child in param.children:
                                if child.type in ["type_identifier", "identifier"]:
                                    params.add(child.text.decode())
                                    break
            current = current.parent
        return params

    def _simple_type_name(self, type_name: str) -> str:
        """去掉泛型参数，如 List<String> → List"""
        return type_name.strip().split("<", 1)[0].strip()

    def _qualify_name(self, name: str) -> str:
        """加上包名前缀"""
        return f"{self.package_name}.{name}" if self.package_name else name

    def _qualified_type_name(self, name: str, containing_types: list[str]) -> str:
        parts = [*containing_types, name] if name else containing_types
        return self._qualify_name(".".join(parts)) if parts else ""

    def _qualified_member_name(self, containing_types: list[str], member_name: str) -> str:
        return self._qualify_name(".".join([*containing_types, member_name]))

    def _get_identifier_name(self, node):
        name_node = next((c for c in node.children if c.type == "identifier"), None)
        return name_node.text.decode() if name_node else None

    def _get_type_name(self, node):
        if node.type == "type_identifier":
            return node.text.decode()
        elif node.type == "generic_type":
            type_node = next((c for c in node.children if c.type == "type_identifier"), None)
            return type_node.text.decode() if type_node else None
        elif node.type == "superclass":
            type_node = next((c for c in node.children if c.type == "type_identifier"), None)
            return type_node.text.decode() if type_node else None
        return None

    def _find_containing_class(self, node, top_level_nodes):
        """向上查找包含当前节点的类声明"""
        current = node.parent
        while current:
            if current.type in [
                "class_declaration", "interface_declaration",
                "enum_declaration", "record_declaration", "annotation_type_declaration",
            ]:
                class_name = self._get_identifier_name(current)
                if class_name and class_name in top_level_nodes:
                    return self._get_component_id(class_name)
            current = current.parent
        return None

    def _find_variable_type(self, node, variable_name, top_level_nodes):
        """
        查找变量的类型。
        搜索顺序: 方法参数 → 方法内局部变量 → 类字段
        """
        # 先找方法声明
        method_node = node.parent
        while method_node and method_node.type not in ["method_declaration", "constructor_declaration"]:
            method_node = method_node.parent

        if method_node:
            for child in method_node.children:
                if child.type in ["block", "constructor_body"]:
                    var_type = self._search_variable_declaration(child, variable_name)
                    if var_type:
                        return var_type
                elif child.type == "formal_parameters":
                    for param in child.children:
                        if param.type in ["formal_parameter", "spread_parameter"]:
                            type_node = next(
                                (c for c in param.children if c.type in ["type_identifier", "generic_type"]),
                                None,
                            )
                            identifier_node = next(
                                (c for c in param.children if c.type == "identifier"), None
                            )
                            if (
                                type_node and identifier_node
                                and identifier_node.text.decode() == variable_name
                            ):
                                return self._get_type_name(type_node)

        # 再找类字段
        class_node = node.parent
        while class_node and class_node.type != "class_declaration":
            class_node = class_node.parent

        if class_node:
            for child in class_node.children:
                if child.type == "class_body":
                    for body_child in child.children:
                        if body_child.type == "field_declaration":
                            identifier_node = None
                            type_node = None
                            for field_child in body_child.children:
                                if field_child.type in ["type_identifier", "generic_type"]:
                                    type_node = field_child
                                elif field_child.type == "variable_declarator":
                                    identifier_node = next(
                                        (c for c in field_child.children if c.type == "identifier"),
                                        None,
                                    )
                            if (
                                identifier_node and type_node
                                and identifier_node.text.decode() == variable_name
                            ):
                                return self._get_type_name(type_node)

        return None

    def _search_variable_declaration(self, block_node, variable_name):
        """在代码块中搜索局部变量声明"""
        for child in block_node.children:
            if child.type == "local_variable_declaration":
                type_node = None
                identifier_node = None
                for decl_child in child.children:
                    if decl_child.type in ["type_identifier", "generic_type"]:
                        type_node = decl_child
                    elif decl_child.type == "variable_declarator":
                        identifier_node = next(
                            (c for c in decl_child.children if c.type == "identifier"), None
                        )
                if (
                    identifier_node and type_node
                    and identifier_node.text.decode() == variable_name
                ):
                    return self._get_type_name(type_node)
            elif child.type == "block":
                result = self._search_variable_declaration(child, variable_name)
                if result:
                    return result
        return None

    def _find_containing_class_name(self, node):
        names = self._find_containing_type_names(node)
        return names[-1] if names else None

    def _find_containing_type_names(self, node) -> list[str]:
        """向上查找所有包含当前节点的类型名（由外到内）"""
        names = []
        current = node.parent
        while current:
            if current.type in [
                "class_declaration", "interface_declaration",
                "enum_declaration", "record_declaration", "annotation_type_declaration",
            ]:
                name_node = next((c for c in current.children if c.type == "identifier"), None)
                if name_node:
                    names.append(name_node.text.decode())
            current = current.parent
        return list(reversed(names))

    def _find_containing_method(self, node):
        """向上查找包含当前节点的方法声明，返回方法的组件 ID"""
        current = node.parent
        while current:
            if current.type == "method_declaration":
                method_name = self._get_identifier_name(current)
                class_name = self._find_containing_class_name(current)
                if method_name and class_name:
                    return self._get_component_id(f"{class_name}.{method_name}")
            current = current.parent
        return None


def analyze_java_file(
    file_path: str, content: str, repo_path: str = None
) -> Tuple[List[Node], List[CallRelationship]]:
    """
    分析单个 Java 文件，返回 (组件列表, 调用关系列表)。

    这是外部调用的入口函数，对应 CodeWiki 中的同名函数。
    """
    analyzer = TreeSitterJavaAnalyzer(file_path, content, repo_path)
    return analyzer.nodes, analyzer.call_relationships
