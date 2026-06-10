# -*- coding: utf-8 -*-
"""RAG middleware for injecting knowledge context into system prompt."""
import logging
import os
from typing import TYPE_CHECKING

from agentscope.middleware import MiddlewareBase

from .models import RetrievalConfig
from .prompts import format_rag_context
from .registry import get_retriever

if TYPE_CHECKING:
    from agentscope.agent import Agent

logger = logging.getLogger(__name__)


class RagMiddleware(MiddlewareBase):
    """Middleware that injects RAG context into the system prompt.

    This middleware:
    1. Retrieves knowledge chunks from the knowledge base
    2. Formats them with reference_id
    3. Injects into system prompt before LLM call
    """

    def __init__(self):
        self._space_id = os.getenv("KE_RAG_SPACE_ID", "be5fb25a-7ce8-4268-a7ac-cc90010bf976")
        self._space_type = os.getenv("KE_RAG_SPACE_TYPE", "space")
        self._user_id = os.getenv("KE_RAG_USER_ID", "1000000030973949")
        self._mode = os.getenv("KE_RAG_MODE", "normal")
        self._limit = int(os.getenv("KE_RAG_LIMIT", "20"))

    async def on_system_prompt(
        self,
        agent: "Agent",
        current_prompt: str,
    ) -> str:
        """Inject RAG context into the system prompt.

        This method:
        1. Extracts the user's latest query from agent state
        2. Retrieves relevant knowledge chunks
        3. Formats and injects them into the system prompt

        Args:
            agent: The Agent instance.
            current_prompt: The current system prompt.

        Returns:
            The system prompt with RAG context injected.
        """
        logger.info("RagMiddleware.on_system_prompt called")

        # Get the user's latest query from agent state
        query = self._extract_latest_query(agent)
        if not query:
            logger.warning("No query found, skipping RAG injection")
            return current_prompt

        logger.info(f"Extracted query: {query[:100]}...")

        # Get retriever
        retriever = get_retriever()
        if retriever is None:
            logger.warning("No retriever registered, skipping RAG injection")
            return current_prompt

        # Execute retrieval
        try:
            config = RetrievalConfig(
                space_id=self._space_id,
                space_type=self._space_type,
                mode=self._mode,
                limit=self._limit,
                user_id=self._user_id,
            )
            chunks = await retriever.retrieve(query, config)

            if not chunks:
                logger.info(f"No chunks retrieved for query: {query[:50]}...")
                return current_prompt

            logger.info(f"Retrieved {len(chunks)} chunks, injecting into system prompt")

            # Format and inject into prompt
            rag_context = format_rag_context(chunks)
            logger.info(f"RAG context length: {len(rag_context)} chars")

            return current_prompt + "\n\n" + rag_context

        except Exception as e:
            logger.error(f"RAG retrieval failed: {e}", exc_info=True)
            return current_prompt

    def _extract_latest_query(self, agent: "Agent") -> str:
        """Extract the user's latest query from agent state.

        Args:
            agent: The Agent instance.

        Returns:
            The latest user query, or empty string if not found.
        """
        try:
            # Get from agent.state.context (AgentScope stores messages here)
            if hasattr(agent, 'state') and hasattr(agent.state, 'context'):
                context = agent.state.context
                if context:
                    # Find the last user message
                    for msg in reversed(context):
                        if hasattr(msg, 'role') and msg.role == 'user':
                            # Extract text from content
                            if hasattr(msg, 'content'):
                                if isinstance(msg.content, str):
                                    return msg.content
                                elif isinstance(msg.content, list):
                                    # Extract from content blocks
                                    texts = []
                                    for block in msg.content:
                                        if hasattr(block, 'text'):
                                            texts.append(block.text)
                                    return " ".join(texts)

            # Fallback: try _input_messages
            if hasattr(agent, '_input_messages') and agent._input_messages:
                for msg in reversed(agent._input_messages):
                    if hasattr(msg, 'role') and msg.role == 'user':
                        if hasattr(msg, 'content'):
                            if isinstance(msg.content, str):
                                return msg.content
                            elif isinstance(msg.content, list):
                                texts = []
                                for block in msg.content:
                                    if hasattr(block, 'text'):
                                        texts.append(block.text)
                                return " ".join(texts)

        except Exception as e:
            logger.debug(f"Failed to extract query: {e}")

        return ""
