# -*- coding: utf-8 -*-
"""API endpoints for RAG knowledge retrieval."""
import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .ke_rag_client import KeRagClient

# Load env
load_dotenv(Path(__file__).parent.parent / ".env")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])

# Initialize client
_ke_rag_client = KeRagClient(
    base_url=os.getenv("KE_RAG_BASE_URL", "https://openapi-ait.ke.com/v1"),
    api_key=os.getenv("KE_RAG_API_KEY", ""),
)


class FileContentRequest(BaseModel):
    """Request model for file content query."""
    file_id: str = ""
    file_name: str = ""


class FileContentResponse(BaseModel):
    """Response model for file content query."""
    file_id: str
    file_name: str
    content: str


@router.post("/file-content", response_model=FileContentResponse)
async def get_file_content(request: FileContentRequest):
    """Get file content by file_id or file_name.

    This endpoint queries the ke-rag API to retrieve the full content
    of a specific file. It supports two modes:
    1. By file_id: Direct query with file scope
    2. By file_name: Search in space scope and filter by file name

    Args:
        request: FileContentRequest with file_id or file_name.

    Returns:
        FileContentResponse with file content.
    """
    try:
        results = []

        if request.file_id:
            # Mode 1: Query by file_id with file scope
            results = await _ke_rag_client.search(
                query=request.file_name or "全部内容",
                space_id=request.file_id,
                mode="normal",
                limit=10,
                user_id=os.getenv("KE_RAG_USER_ID", ""),
                scope_type="file",
            )
        elif request.file_name:
            # Mode 2: Search by file_name in space scope
            space_id = os.getenv("KE_RAG_SPACE_ID", "")
            all_results = await _ke_rag_client.search(
                query=request.file_name,
                space_id=space_id,
                mode="normal",
                limit=20,
                user_id=os.getenv("KE_RAG_USER_ID", ""),
                scope_type="space",
            )
            # Filter results by file_name
            results = [r for r in all_results if r.file_name == request.file_name]

            # If exact match not found, use all results
            if not results and all_results:
                results = all_results
        else:
            raise HTTPException(
                status_code=400,
                detail="Either file_id or file_name must be provided"
            )

        if not results:
            raise HTTPException(status_code=404, detail="File not found or empty")

        # Combine all chunks into full content
        file_id = results[0].file_id if results else ""
        file_name = results[0].file_name if results else ""
        content_parts = [chunk.content for chunk in results]
        full_content = "\n\n---\n\n".join(content_parts)

        return FileContentResponse(
            file_id=file_id,
            file_name=file_name,
            content=full_content,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file content: {e}")
        raise HTTPException(status_code=500, detail=str(e))
