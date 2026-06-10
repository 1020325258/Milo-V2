# -*- coding: utf-8 -*-
"""Registry for knowledge retriever implementations."""
from typing import Dict, Optional

from .retriever import KnowledgeRetriever

# Global registry of retriever implementations
_retrievers: Dict[str, KnowledgeRetriever] = {}
_default_retriever_name: Optional[str] = None


def register_retriever(
    name: str,
    retriever: KnowledgeRetriever,
    is_default: bool = False,
) -> None:
    """Register a knowledge retriever implementation.

    Args:
        name: Unique name for the retriever (e.g., 'ke-rag', 'local-es').
        retriever: The retriever instance.
        is_default: If True, set this as the default retriever.
    """
    global _default_retriever_name

    _retrievers[name] = retriever

    if is_default or _default_retriever_name is None:
        _default_retriever_name = name


def get_retriever(name: Optional[str] = None) -> Optional[KnowledgeRetriever]:
    """Get a registered retriever by name, or the default retriever.

    Args:
        name: The retriever name. If None, returns the default retriever.

    Returns:
        The retriever instance, or None if not found.
    """
    if name is None:
        name = _default_retriever_name

    return _retrievers.get(name) if name else None


def list_retrievers() -> Dict[str, KnowledgeRetriever]:
    """List all registered retrievers.

    Returns:
        A dictionary mapping retriever names to instances.
    """
    return _retrievers.copy()
