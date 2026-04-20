from abc import ABC, abstractmethod
from typing import Any


class BaseReranker(ABC):
    provider_name: str = "unknown"
    model_name: str = "unknown"

    @abstractmethod
    async def rerank(
        self,
        *,
        query: str,
        candidates: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return reranked candidates with provider-specific score fields."""

