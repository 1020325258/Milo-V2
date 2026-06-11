# -*- coding: utf-8 -*-
"""Ke-RAG HTTP client for knowledge retrieval."""
import logging
from typing import Any, Dict, List, Optional

import httpx

from .models import KnowledgeChunk

logger = logging.getLogger(__name__)

# Default Ke-RAG service configuration
DEFAULT_BASE_URL = "https://openapi-ait.ke.com/v1"
DEFAULT_TIMEOUT = 30


class KeRagClient:
    """HTTP client for Ke-RAG knowledge retrieval service.

    This client wraps the Ke-RAG API, providing methods for
    knowledge search with proper error handling.

    Args:
        base_url: The Ke-RAG service base URL.
        api_key: The Bearer token for authentication.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str = "",
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def search(
        self,
        query: str,
        space_id: str,
        mode: str = "normal",
        limit: int = 5,
        user_id: str = "",
        scope_type: str = "file",
    ) -> List[KnowledgeChunk]:
        """Search knowledge base for relevant chunks.

        Args:
            query: The search query string.
            space_id: The knowledge base space ID or file ID.
            mode: Search mode ('fast', 'normal', 'ultra').
            limit: Maximum number of results.
            user_id: User ID for city-based filtering.
            scope_type: Type of scope ('space' or 'file').

        Returns:
            A list of KnowledgeChunk objects, or empty list on error.
        """
        request_body = {
            "query": query,
            "scope": [{"type": scope_type, "ids": [space_id]}],
            "limit": limit,
            "user": user_id,
            "mode": mode,
        }

        try:
            client = await self._get_client()
            response = await client.post("/rag/search", json=request_body)
            response.raise_for_status()

            data = response.json()

            # Check API response code
            if data.get("code") != 0:
                logger.error(
                    "Ke-RAG search failed: code=%s, message=%s",
                    data.get("code"),
                    data.get("message"),
                )
                return []

            # Parse results (API returns "docs" not "results")
            results = data.get("data", {}).get("docs", [])
            logger.info(f"Ke-RAG returned {len(results)} docs")
            for i, doc in enumerate(results[:5]):
                logger.info(f"  Doc {i}: {doc.get('annotation', {}).get('file_name', 'unknown')} - {doc.get('text', '')[:100]}...")
            return self._parse_results(results)

        except httpx.TimeoutException:
            logger.error("Ke-RAG search timeout after %ds", self.timeout)
            return []
        except httpx.HTTPStatusError as e:
            logger.error(
                "Ke-RAG search HTTP error: %s %s",
                e.response.status_code,
                e.response.text,
            )
            return []
        except Exception as e:
            logger.error("Ke-RAG search unexpected error: %s", e)
            return []

    def _parse_results(self, results: List[Dict[str, Any]]) -> List[KnowledgeChunk]:
        """Parse API results into KnowledgeChunk objects.

        Args:
            results: Raw results from the API response.
                     Each item has structure:
                     {
                         "type": "text",
                         "text": "content...",
                         "annotation": {
                             "file_id": "file-xxx",
                             "file_name": "filename.pdf",
                             "paths": [[1, 2, 3]]
                         },
                         "score": 0.75
                     }

        Returns:
            A list of KnowledgeChunk objects.
        """
        chunks = []
        for idx, item in enumerate(results):
            # Extract annotation data
            annotation = item.get("annotation", {})
            file_name = annotation.get("file_name", "")
            file_id = annotation.get("file_id", "")

            # Generate chunk_id from file_id or index
            chunk_id = file_id or f"{file_name}_{idx}"

            # Convert paths to string list
            raw_paths = annotation.get("paths", [])
            paths = [str(p) for p in raw_paths] if raw_paths else []

            chunk = KnowledgeChunk(
                content=item.get("text", ""),
                file_name=file_name,
                file_id=file_id,
                title=file_name,  # API doesn't return title separately
                paths=paths,
                chunk_id=chunk_id,
                metadata={"score": str(item.get("score", 0))},
            )
            chunks.append(chunk)

        return chunks

    async def health_check(self) -> bool:
        """Check if the Ke-RAG service is available.

        Returns:
            True if the service is available, False otherwise.
        """
        try:
            client = await self._get_client()
            # Use a simple search request as health check
            response = await client.post(
                "/rag/search",
                json={
                    "query": "health_check",
                    "scope": [{"type": "space", "ids": ["test"]}],
                    "limit": 1,
                    "user": "system",
                    "mode": "fast",
                },
                timeout=5,
            )
            # Any response (even error) means the service is reachable
            return response.status_code < 500
        except Exception as e:
            logger.warning("Ke-RAG health check failed: %s", e)
            return False
