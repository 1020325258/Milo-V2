# -*- coding: utf-8 -*-
"""Knowledge search tool for AgentScope agents."""
import logging
from typing import Any, Dict, List

from agentscope.tool import ToolBase
from agentscope.permission import PermissionContext, PermissionDecision, PermissionBehavior
from agentscope.message import TextBlock
from agentscope.tool._response import ToolChunk

from .models import RetrievalConfig
from .registry import get_retriever

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_SPACE_ID = "be5fb25a-7ce8-4268-a7ac-cc90010bf976"
DEFAULT_MODE = "normal"
DEFAULT_LIMIT = 5
MAX_CONTENT_LENGTH = 500


class KnowledgeSearchTool(ToolBase):
    """Tool for searching the knowledge base.

    This tool allows the agent to search for relevant knowledge
    from the configured knowledge base (e.g., Ke-RAG).

    The search results are formatted as Markdown for easy consumption
    by the LLM.
    """

    name = "knowledge_search"
    description = (
        "搜索知识库获取相关信息。"
        "当用户问题涉及企业内部知识时使用此工具。"
        "【强制要求】使用此工具后，必须在回答中引用来源。"
        "引用格式必须严格为：[文件名||文件ID]"
        "例如：根据知识库信息 [退款政策.md||file-001] 的说明..."
        "【重要】文件ID来自搜索结果中的'来源：'字段，格式为 file_name||file_id"
        "【禁止】不要只写文件名，必须包含||file_id部分"
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query. Should be concise and focused on key concepts.",
            },
        },
        "required": ["query"],
    }
    is_concurrency_safe = True
    is_read_only = True

    def __init__(
        self,
        space_id: str = DEFAULT_SPACE_ID,
        space_type: str = "file",
        mode: str = DEFAULT_MODE,
        limit: int = DEFAULT_LIMIT,
        user_id: str = "",
    ):
        """Initialize the knowledge search tool.

        Args:
            space_id: The knowledge base space ID or file ID.
            space_type: Type of scope ('space' or 'file').
            mode: Search mode ('fast', 'normal', 'ultra').
            limit: Maximum number of results.
            user_id: User ID for city-based filtering.
        """
        self.space_id = space_id
        self.space_type = space_type
        self.mode = mode
        self.limit = limit
        self.user_id = user_id

    async def check_permissions(
        self,
        tool_input: Dict[str, Any],
        context: PermissionContext,
    ) -> PermissionDecision:
        """Check permissions for knowledge search.

        Knowledge search is always allowed as it's read-only.
        """
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="Knowledge search is always allowed (read-only).",
        )

    async def __call__(self, query: str, **kwargs: Any) -> ToolChunk:
        """Execute the knowledge search.

        Args:
            query: The search query string.

        Returns:
            ToolChunk with formatted search results.
        """
        retriever = get_retriever()
        if retriever is None:
            return ToolChunk(
                content=[
                    TextBlock(
                        id="knowledge_search_error",
                        text="Error: No knowledge retriever is configured.",
                    )
                ],
            )

        config = RetrievalConfig(
            space_id=self.space_id,
            space_type=self.space_type,
            mode=self.mode,
            limit=self.limit,
            user_id=self.user_id,
        )

        try:
            chunks = await retriever.retrieve(query, config)
            formatted = self._format_results(chunks)

            return ToolChunk(
                content=[TextBlock(id="knowledge_search_result", text=formatted)],
            )
        except Exception as e:
            logger.error("Knowledge search failed: %s", e)
            return ToolChunk(
                content=[
                    TextBlock(
                        id="knowledge_search_error",
                        text=f"Knowledge search failed: {str(e)}",
                    )
                ],
            )

    def _format_results(self, chunks: list) -> str:
        """Format knowledge chunks as Markdown.

        Args:
            chunks: List of KnowledgeChunk objects.

        Returns:
            Formatted Markdown string.
        """
        if not chunks:
            return "未找到相关知识，请尝试其他关键词或直接回答。"

        lines = [f"找到 {len(chunks)} 条相关知识：\n"]

        for i, chunk in enumerate(chunks, 1):
            title = chunk.title or chunk.file_name or "未知来源"
            content = chunk.content

            # Truncate content if too long
            if len(content) > MAX_CONTENT_LENGTH:
                content = content[:MAX_CONTENT_LENGTH] + "..."

            # Include file_id in the format for frontend parsing
            file_ref = f"{chunk.file_name}||{chunk.file_id}" if chunk.file_id else chunk.file_name
            lines.append(f"{i}. **{title}** | 来源：{file_ref}")
            lines.append(f"   {content}\n")

        return "\n".join(lines)
