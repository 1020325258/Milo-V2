# -*- coding: utf-8 -*-
"""RAG (Retrieval-Augmented Generation) module for knowledge retrieval.

This module provides an abstraction layer for knowledge retrieval,
supporting multiple backend implementations (e.g., ke-rag, local ES).
"""
from .models import KnowledgeChunk, RetrievalConfig
from .retriever import KnowledgeRetriever
from .registry import get_retriever, register_retriever

__all__ = [
    "KnowledgeChunk",
    "RetrievalConfig",
    "KnowledgeRetriever",
    "get_retriever",
    "register_retriever",
]
