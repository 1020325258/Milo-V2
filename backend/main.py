# -*- coding: utf-8 -*-
"""Milo V2 - 基于 AgentScope 原生后端模板的服务"""
import os
import logging
from pathlib import Path

from dotenv import load_dotenv

# 加载 .env 文件
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)
# 也加载项目根目录的 .env
load_dotenv(Path(__file__).parent.parent / ".env")

import uvicorn
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware

from agentscope.app import create_app
from agentscope.app.message_bus import RedisMessageBus
from agentscope.app.storage import RedisStorage
from agentscope.app.workspace_manager import LocalWorkspaceManager

from rag import register_retriever
from rag.ke_rag_retriever import KeRagRetriever
from rag.tools import KnowledgeSearchTool
from rag.middleware import RagMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 从环境变量读取配置
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# Ke-RAG configuration
KE_RAG_SPACE_ID = os.getenv("KE_RAG_SPACE_ID", "be5fb25a-7ce8-4268-a7ac-cc90010bf976")
KE_RAG_SPACE_TYPE = os.getenv("KE_RAG_SPACE_TYPE", "space")
KE_RAG_USER_ID = os.getenv("KE_RAG_USER_ID", "1000000030973949")
KE_RAG_MODE = os.getenv("KE_RAG_MODE", "normal")
KE_RAG_LIMIT = int(os.getenv("KE_RAG_LIMIT", "20"))

# Initialize and register the Ke-RAG retriever
_ke_rag_retriever = KeRagRetriever()
register_retriever("ke-rag", _ke_rag_retriever, is_default=True)
logger.info("Ke-RAG retriever registered")


async def _create_agent_tools(user_id: str, agent_id: str, session_id: str):
    """Factory function to create extra tools for agents.

    This function is called by AgentScope for each agent invocation.
    It returns the knowledge_search tool configured with user-specific settings.
    """
    return [
        KnowledgeSearchTool(
            space_id=KE_RAG_SPACE_ID,
            space_type=KE_RAG_SPACE_TYPE,
            mode=KE_RAG_MODE,
            limit=KE_RAG_LIMIT,
            user_id=KE_RAG_USER_ID or user_id,
        ),
    ]


async def _create_agent_middlewares(user_id: str, agent_id: str, session_id: str):
    """Factory function to create extra middlewares for agents.

    This function is called by AgentScope for each agent invocation.
    It returns the RAG middleware for injecting citation instructions.
    """
    return [RagMiddleware()]


app = create_app(
    RedisStorage(
        host=REDIS_HOST,
        port=REDIS_PORT,
    ),
    RedisMessageBus(
        host=REDIS_HOST,
        port=REDIS_PORT,
    ),
    workspace_manager=LocalWorkspaceManager(
        basedir=os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "workspaces",
        ),
    ),
    extra_middlewares=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        ),
    ],
    extra_agent_tools=_create_agent_tools,
    extra_agent_middlewares=_create_agent_middlewares,
)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )
