import math
import re
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.reranker.base import BaseReranker

logger = get_logger(__name__)


class LocalReranker(BaseReranker):
    provider_name = "local"

    def __init__(self) -> None:
        configured_model = (settings.RERANKER_LOCAL_MODEL or "").strip() or "local-heuristic-v1"
        self.model_name = configured_model
        self._cross_encoder = None
        if configured_model not in {"local-heuristic-v1", "heuristic"}:
            try:
                from sentence_transformers import CrossEncoder  # type: ignore

                self._cross_encoder = CrossEncoder(configured_model)
            except Exception as exc:  # pragma: no cover - dependency and runtime environment specific
                logger.warning(
                    "local_reranker_model_unavailable",
                    model=configured_model,
                    reason=str(exc),
                    fallback="local-heuristic-v1",
                )
                self.model_name = "local-heuristic-v1"

    async def rerank(
        self,
        *,
        query: str,
        candidates: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        _ = context
        if not candidates:
            return []

        if self._cross_encoder is not None:
            try:
                return self._rerank_with_cross_encoder(query=query, candidates=candidates)
            except Exception as exc:  # pragma: no cover - runtime environment specific
                logger.warning(
                    "local_reranker_runtime_fallback",
                    model=self.model_name,
                    reason=str(exc),
                    fallback="local-heuristic-v1",
                )

        return self._rerank_with_heuristic(query=query, candidates=candidates)

    def _rerank_with_cross_encoder(
        self,
        *,
        query: str,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        pairs = [(query, self._candidate_text(item)) for item in candidates]
        raw_scores = self._cross_encoder.predict(pairs)
        scores = [self._sigmoid(float(value)) for value in raw_scores]

        outputs: list[dict[str, Any]] = []
        for idx, item in enumerate(candidates):
            base_score = float(item.get("retrieval_score") or item.get("score") or 0.0)
            semantic_score = float(scores[idx])
            rerank_score = base_score * 0.2 + semantic_score * 0.8
            outputs.append({
                **item,
                "rerank_score": round(rerank_score, 4),
                "rerank_components": {
                    "base_score": round(base_score, 4),
                    "semantic_score": round(semantic_score, 4),
                },
                "reranker_provider": self.provider_name,
                "reranker_model": self.model_name,
            })

        outputs.sort(key=lambda item: item.get("rerank_score", 0.0), reverse=True)
        return outputs

    def _rerank_with_heuristic(
        self,
        *,
        query: str,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        query_terms = self._terms(query)
        outputs: list[dict[str, Any]] = []
        for item in candidates:
            base_score = float(item.get("retrieval_score") or item.get("score") or 0.0)
            text_terms = self._terms(self._candidate_text(item))

            overlap = len(query_terms & text_terms)
            query_recall = overlap / max(len(query_terms), 1)
            term_precision = overlap / max(len(text_terms), 1)
            f1 = 0.0
            if query_recall > 0 and term_precision > 0:
                f1 = 2 * query_recall * term_precision / (query_recall + term_precision)

            length_bonus = 0.04 if 15 <= len(text_terms) <= 80 else 0.0
            rerank_score = base_score + f1 * 0.35 + length_bonus
            outputs.append({
                **item,
                "rerank_score": round(rerank_score, 4),
                "rerank_components": {
                    "base_score": round(base_score, 4),
                    "query_recall": round(query_recall, 4),
                    "term_precision": round(term_precision, 4),
                    "overlap_f1": round(f1, 4),
                    "length_bonus": round(length_bonus, 4),
                },
                "reranker_provider": self.provider_name,
                "reranker_model": "local-heuristic-v1" if self._cross_encoder is None else self.model_name,
            })

        outputs.sort(key=lambda item: item.get("rerank_score", 0.0), reverse=True)
        return outputs

    def _candidate_text(self, item: dict[str, Any]) -> str:
        return (
            item.get("raw_text")
            or item.get("snippet")
            or item.get("text")
            or ""
        )

    def _terms(self, text: str) -> set[str]:
        latin = re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}", (text or "").lower())
        cjk = re.findall(r"[\u4e00-\u9fff]{2,8}", text or "")
        return {token for token in [*latin, *cjk] if token}

    def _sigmoid(self, value: float) -> float:
        if value >= 0:
            z = math.exp(-value)
            return 1.0 / (1.0 + z)
        z = math.exp(value)
        return z / (1.0 + z)
