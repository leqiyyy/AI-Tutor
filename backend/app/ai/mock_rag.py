"""Compatibility wrapper around the current simple RAG engine."""

from app.integrations.rag import get_rag_engine

__all__ = ["get_rag_engine"]
