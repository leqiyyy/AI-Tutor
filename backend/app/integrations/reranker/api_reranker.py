from typing import Any

import httpx

from app.core.config import settings
from app.integrations.reranker.base import BaseReranker


class APIReranker(BaseReranker):
    provider_name = "api"

    def __init__(self) -> None:
        self.model_name = settings.RERANKER_MODEL or "api-reranker-v1"
        self._base = (settings.RERANKER_API_BASE or "").strip().rstrip("/")
        self._path = self._normalized_path(settings.RERANKER_API_PATH)
        self._endpoint = f"{self._base}{self._path}" if self._base else ""
        self._timeout = max(1.0, float(settings.RERANKER_API_TIMEOUT_SECONDS or 20.0))
        self._api_key = (
            settings.RERANKER_API_KEY
            or settings.EFFECTIVE_EMBEDDING_API_KEY
            or settings.EFFECTIVE_EXTRACT_API_KEY
            or settings.EFFECTIVE_LLM_API_KEY
        )

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

        try:
            remote_scores = await self._fetch_scores(query=query, candidates=candidates)
            if len(remote_scores) != len(candidates):
                raise ValueError("reranker_api_response_size_mismatch")
        except Exception as exc:
            return self._fallback_by_base_score(candidates=candidates, error=exc)

        outputs: list[dict[str, Any]] = []
        for idx, item in enumerate(candidates):
            base_score = float(item.get("retrieval_score") or item.get("score") or 0.0)
            remote_score = float(remote_scores[idx])
            rerank_score = base_score * 0.2 + remote_score * 0.8
            outputs.append({
                **item,
                "rerank_score": round(rerank_score, 4),
                "rerank_components": {
                    "base_score": round(base_score, 4),
                    "remote_score": round(remote_score, 4),
                },
                "reranker_provider": self.provider_name,
                "reranker_model": self.model_name,
            })

        outputs.sort(key=lambda item: item.get("rerank_score", 0.0), reverse=True)
        return outputs

    async def _fetch_scores(
        self,
        *,
        query: str,
        candidates: list[dict[str, Any]],
    ) -> list[float]:
        if not self._endpoint:
            raise RuntimeError("reranker_api_endpoint_not_configured")

        payload = {
            "model": self.model_name,
            "query": query,
            "documents": [self._candidate_text(item) for item in candidates],
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
            headers["x-api-key"] = self._api_key

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(self._endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        return self._parse_scores(data=data, size=len(candidates))

    def _parse_scores(self, *, data: Any, size: int) -> list[float]:
        if isinstance(data, list):
            return self._as_score_list(data, size=size)

        if not isinstance(data, dict):
            raise ValueError("reranker_api_invalid_response")

        if isinstance(data.get("scores"), list):
            return self._as_score_list(data["scores"], size=size)
        if isinstance(data.get("results"), list):
            return self._from_results(data["results"], size=size)
        if isinstance(data.get("data"), list):
            return self._from_results(data["data"], size=size)
        raise ValueError("reranker_api_missing_scores")

    def _from_results(self, rows: list[Any], *, size: int) -> list[float]:
        if not rows:
            raise ValueError("reranker_api_empty_results")

        if all(isinstance(row, (int, float)) for row in rows):
            return self._as_score_list(rows, size=size)

        indexed: list[float | None] = [None] * size
        sequential: list[float] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            score = row.get("relevance_score", row.get("score"))
            if score is None:
                continue
            try:
                score_value = float(score)
            except (TypeError, ValueError):
                continue
            index = row.get("index")
            if isinstance(index, int) and 0 <= index < size:
                indexed[index] = score_value
            else:
                sequential.append(score_value)

        if all(value is not None for value in indexed):
            return [float(value) for value in indexed]

        if len(sequential) >= size:
            return [float(value) for value in sequential[:size]]

        raise ValueError("reranker_api_unusable_results")

    def _as_score_list(self, values: list[Any], *, size: int) -> list[float]:
        if len(values) < size:
            raise ValueError("reranker_api_short_scores")
        scores: list[float] = []
        for value in values[:size]:
            scores.append(float(value))
        return scores

    def _fallback_by_base_score(
        self,
        *,
        candidates: list[dict[str, Any]],
        error: Exception,
    ) -> list[dict[str, Any]]:
        outputs = []
        for item in candidates:
            base_score = float(item.get("retrieval_score") or item.get("score") or 0.0)
            outputs.append({
                **item,
                "rerank_score": round(base_score, 4),
                "rerank_components": {
                    "base_score": round(base_score, 4),
                    "api_fallback": True,
                },
                "reranker_provider": self.provider_name,
                "reranker_model": self.model_name,
                "rerank_fallback_reason": error.__class__.__name__,
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

    def _normalized_path(self, path: str | None) -> str:
        normalized = (path or "/rerank").strip()
        if not normalized.startswith("/"):
            return "/" + normalized
        return normalized
