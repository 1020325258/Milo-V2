# -*- coding: utf-8 -*-
"""Data models for RAG knowledge retrieval."""
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class RetrievalConfig(BaseModel):
    """Configuration for knowledge retrieval.

    Attributes:
        space_id: The knowledge base space ID or file ID.
        space_type: Type of scope ('space' or 'file').
        mode: Search mode - 'fast', 'normal', or 'ultra'.
        limit: Maximum number of results to return.
        user_id: User ID for city-based filtering.
    """

    space_id: str
    space_type: Literal["space", "file"] = "file"
    mode: Literal["fast", "normal", "ultra"] = "normal"
    limit: int = Field(default=5, ge=1, le=20)
    user_id: str = ""


class KnowledgeChunk(BaseModel):
    """A single knowledge chunk retrieved from the knowledge base.

    Attributes:
        content: The text content of the knowledge chunk.
        file_name: The source file name.
        title: The knowledge title.
        paths: Logical location paths for citation.
        chunk_id: Unique identifier for citation links.
        metadata: Additional metadata from the knowledge base.
    """

    content: str
    file_name: str = ""
    title: str = ""
    paths: List[str] = Field(default_factory=list)
    chunk_id: str = ""
    metadata: Dict[str, str] = Field(default_factory=dict)
