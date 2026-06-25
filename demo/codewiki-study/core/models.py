"""
数据模型 — 对应 CodeWiki 的 codewiki/src/be/dependency_analyzer/models/core.py

每个代码组件（类、接口、方法等）被抽象为一个 Node，
通过 depends_on 字段形成有向依赖图。
"""

from pydantic import BaseModel
from typing import List, Optional, Set


class Node(BaseModel):
    """代码组件节点 — 依赖图的基本单元"""

    # 唯一标识，格式: "相对路径::类名.方法名" 或 "相对路径::类名"
    id: str

    # 组件名，如 "LoginService"、"LoginService.login"
    name: str

    # 组件类型: class / interface / enum / method / function / struct / abstract class
    component_type: str

    # 文件绝对路径
    file_path: str

    # 相对于仓库根目录的路径
    relative_path: str

    # 依赖的其他组件 ID 集合
    depends_on: Set[str] = set()

    # 源代码片段
    source_code: Optional[str] = None

    # 行号范围
    start_line: int = 0
    end_line: int = 0

    # 是否有文档注释
    has_docstring: bool = False
    docstring: str = ""

    # 方法参数列表
    parameters: Optional[List[str]] = None

    # 节点类型（与 component_type 类似，用于更细粒度区分）
    node_type: Optional[str] = None

    # 基类列表（继承关系）
    base_classes: Optional[List[str]] = None

    # 所属类名（用于方法节点）
    class_name: Optional[str] = None

    # 显示名，如 "class LoginService"
    display_name: Optional[str] = None

    # 组件 ID（与 id 字段相同，兼容 CodeWiki 原有结构）
    component_id: Optional[str] = None

    # 编程语言
    language: Optional[str] = None

    # 全限定名，如 "com.ke.utopia.nrs.salesproject.service.PersonalRelationHandler"
    qualified_name: Optional[str] = None

    def get_display_name(self) -> str:
        return self.display_name or self.name


class CallRelationship(BaseModel):
    """调用关系 — 表示 caller 调用了 callee"""

    caller: str           # 调用者组件 ID
    callee: str           # 被调用者组件 ID
    call_line: Optional[int] = None   # 调用所在行号
    is_resolved: bool = False          # callee 是否已解析为实际组件 ID
