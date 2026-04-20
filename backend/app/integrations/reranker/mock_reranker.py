import re
from typing import Any

from app.core.config import settings
from app.integrations.reranker.base import BaseReranker


class MockReranker(BaseReranker):
    provider_name = "mock"

    def __init__(self) -> None:
        self.model_name = settings.RERANKER_MODEL or "mock-reranker-v1"

    async def rerank(
        self,
        *,
        query: str,
        candidates: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []

        context = context or {}
        review_matches = context.get("review_matches") or []
        image_contexts = context.get("image_contexts") or []
        question_terms = self._terms(query)
        image_terms = self._terms(" ".join(image_contexts))
        has_review_boost = bool(review_matches)

        reranked: list[dict[str, Any]] = []
        for item in candidates:
            snippet_terms = self._terms(item.get("raw_text") or item.get("snippet") or "")
            lexical_overlap = len(question_terms & snippet_terms)
            lexical_boost = min(0.3, lexical_overlap * 0.03)
            image_boost = 0.12 if image_terms and (image_terms & snippet_terms) else 0.0
            review_boost = 0.06 if has_review_boost else 0.0

            base_score = float(item.get("retrieval_score") or item.get("score") or 0.0)
            rerank_score = base_score + lexical_boost + image_boost + review_boost
            reranked.append({
                **item,
                "rerank_score": round(rerank_score, 4),
                "rerank_components": {
                    "base_score": round(base_score, 4),
                    "lexical_boost": round(lexical_boost, 4),
                    "image_boost": round(image_boost, 4),
                    "review_boost": round(review_boost, 4),
                },
                "reranker_provider": self.provider_name,
                "reranker_model": self.model_name,
            })

        reranked.sort(key=lambda item: item.get("rerank_score", 0.0), reverse=True)
        return reranked

    def _terms(self, text: str) -> set[str]:
        latin = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", (text or "").lower())
        cjk = re.findall(r"[\u4e00-\u9fff]{2,8}", text or "")
        return {token for token in [*latin, *cjk] if token}

