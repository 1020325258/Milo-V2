"""
MCP 服务器：提供 read_code_components 工具

Claude Code SDK 通过 MCP 协议调用此工具，让 LLM 能按需读取组件源码。
对应 CodeWiki 的 codewiki/src/be/agent_tools/read_code_components.py
"""

import json
import sys
from mcp.server.fastmcp import FastMCP

# 从 stdin 读取组件数据（由 main.py 通过 JSON 文件传入）
COMPONENTS_FILE = sys.argv[1] if len(sys.argv) > 1 else "components_for_mcp.json"

with open(COMPONENTS_FILE, "r", encoding="utf-8") as f:
    _components = json.load(f)

mcp = FastMCP("code-components")


@mcp.tool()
def read_code_components(component_ids: list[str]) -> str:
    """Read the source code of specified component IDs.

    Args:
        component_ids: List of component IDs to read, e.g.
            ["auth/login.py::LoginService", "auth/token.py::TokenManager"]
            The part before :: is the file path, the part after :: is the component name.

    Returns:
        The source code of each requested component.
    """
    results = []
    for comp_id in component_ids:
        if comp_id in _components:
            comp = _components[comp_id]
            source = comp.get("source_code", "").strip()
            results.append(f"# Component {comp_id}:\n{source}\n")
        else:
            results.append(f"# Component {comp_id}: NOT FOUND\n")
    return "\n".join(results)


if __name__ == "__main__":
    mcp.run(transport="stdio")
