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
from agentscope.mcp import MCPClient, StdioMCPConfig, HttpMCPConfig

from apollo.client import ApolloClient
from apollo.tools import ApolloQueryTool
from rag import register_retriever
from rag.ke_rag_retriever import KeRagRetriever
from rag.tools import KnowledgeSearchTool
from rag.api import router as rag_router
from credential_loader import ensure_all_existing_users
from credential_api import router as credential_api_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 从环境变量读取配置
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# Apollo configuration
APOLLO_BASE_URL = os.getenv("APOLLO_BASE_URL", "http://apollo.portal.life.ke.com")
APOLLO_TOKEN = os.getenv("APOLLO_TOKEN", "")
APOLLO_DEFAULT_ENV = os.getenv("APOLLO_DEFAULT_ENV", "PROD")
APOLLO_DEFAULT_APP_ID = os.getenv("APOLLO_DEFAULT_APP_ID", "utopia-nrs-sales-project")
APOLLO_DEFAULT_CLUSTER = os.getenv("APOLLO_DEFAULT_CLUSTER", "default")
APOLLO_DEFAULT_NAMESPACE = os.getenv("APOLLO_DEFAULT_NAMESPACE", "application")

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

# 全局 Skill 目录 - 所有新 workspace 自动继承
GLOBAL_SKILLS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "global_skills",
)


def _collect_global_skill_paths() -> list[str]:
    """扫描全局 skill 目录，返回所有包含 SKILL.md 的子目录路径"""
    skill_paths = []
    if not os.path.isdir(GLOBAL_SKILLS_DIR):
        return skill_paths

    for name in os.listdir(GLOBAL_SKILLS_DIR):
        skill_dir = os.path.join(GLOBAL_SKILLS_DIR, name)
        skill_md = os.path.join(skill_dir, "SKILL.md")
        if os.path.isdir(skill_dir) and os.path.isfile(skill_md):
            skill_paths.append(skill_dir)
            logger.info("Found global skill: %s", name)

    return skill_paths

# 全局默认 MCP - 所有新 workspace 自动继承
def _build_default_mcps() -> list[MCPClient]:
    """构建全局默认 MCP 列表"""
    mcps = []

    # 示例 1: Playwright MCP (本地 stdio)
    # mcps.append(
    #     MCPClient(
    #         name="playwright",
    #         mcp_config=StdioMCPConfig(
    #             command="npx",
    #             args=["@playwright/mcp@latest"],
    #         ),
    #         is_stateful=True,
    #     )
    # )

    # 示例 2: 远程 HTTP MCP
    # mcps.append(
    #     MCPClient(
    #         name="remote-tools",
    #         mcp_config=HttpMCPConfig(
    #             url="http://localhost:3000/mcp",
    #         ),
    #         is_stateful=False,
    #     )
    # )

    return mcps


# Apollo 客户端（全局复用）
_apollo_client = ApolloClient(
    base_url=APOLLO_BASE_URL,
    token=APOLLO_TOKEN,
)


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
        ApolloQueryTool(
            client=_apollo_client,
            default_env=APOLLO_DEFAULT_ENV,
            default_app_id=APOLLO_DEFAULT_APP_ID,
            default_cluster=APOLLO_DEFAULT_CLUSTER,
            default_namespace=APOLLO_DEFAULT_NAMESPACE,
        ),
    ]


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
        default_mcps=_build_default_mcps(),
        skill_paths=_collect_global_skill_paths(),
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
)

# Register RAG API router
app.include_router(rag_router)

# Register system credential API router
app.include_router(credential_api_router)


@app.on_event("startup")
async def _on_startup():
    """Create system credentials for all existing users at startup."""
    try:
        await ensure_all_existing_users(app.state.storage)
    except Exception:
        logger.exception("Failed to load system credentials at startup")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )
