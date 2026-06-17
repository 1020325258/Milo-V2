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
    """Get file content by file_id.

    This endpoint calls the Ke-RAG file content API directly
    to retrieve the full content of a specific file.

    Args:
        request: FileContentRequest with file_id.

    Returns:
        FileContentResponse with file content.
    """
    if not request.file_id:
        raise HTTPException(
            status_code=400,
            detail="file_id is required"
        )

    try:
        user_id = os.getenv("KE_RAG_USER_ID", "")
        content = await _ke_rag_client.get_file_content(
            file_id=request.file_id,
            user_id=user_id,
        )

        if content is None:
            raise HTTPException(
                status_code=404,
                detail="File not found or failed to retrieve content"
            )

        return FileContentResponse(
            file_id=request.file_id,
            file_name=request.file_name,
            content=content,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file content: {e}")
        raise HTTPException(status_code=500, detail=str(e))
