from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.analytics import RAGQueryEvent


def record_query_event(
    db: Session,
    *,
    class_id: str | None,
    user_id: str | None,
    role: str | None,
    engine: str,
    query_mode: str | None,
    query_method: str | None,
    used_multimodal: bool,
    used_fallback: bool,
    fallback_reason: str | None,
    success: bool,
    latency_ms: float | None,
    confidence: float | None,
    source_count: int,
    extra_data: dict[str, Any] | None = None,
) -> None:
    event = RAGQueryEvent(
        class_id=class_id,
        user_id=user_id,
        role=role,
        engine=engine or "unknown",
        query_mode=query_mode,
        query_method=query_method,
        used_multimodal=1 if used_multimodal else 0,
        used_fallback=1 if used_fallback else 0,
        fallback_reason=fallback_reason,
        success=1 if success else 0,
        latency_ms=latency_ms,
        confidence=confidence,
        source_count=max(0, int(source_count)),
        extra_data=extra_data or {},
    )
    db.add(event)


def get_rag_performance(
    db: Session,
    *,
    days: int = 7,
    class_id: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=days)
    query = db.query(RAGQueryEvent).filter(RAGQueryEvent.created_at >= window_start)
    if class_id:
        query = query.filter(RAGQueryEvent.class_id == class_id)

    rows = query.order_by(RAGQueryEvent.created_at.desc()).all()
    total = len(rows)
    success_count = sum(1 for row in rows if row.success)
    fallback_count = sum(1 for row in rows if row.used_fallback)
    main_chain_success_count = sum(1 for row in rows if row.success and not row.used_fallback)

    latencies = [float(row.latency_ms) for row in rows if row.latency_ms is not None]
    confidences = [float(row.confidence) for row in rows if row.confidence is not None]
    source_counts = [int(row.source_count) for row in rows if row.source_count is not None]

    query_mode_dist = Counter((row.query_mode or "unknown") for row in rows)
    engine_dist = Counter((row.engine or "unknown") for row in rows)
    retrieval_strategy_dist = Counter(
        ((row.extra_data or {}).get("retrieval_strategy") or "unknown")
        for row in rows
    )
    reranker_dist = Counter(
        ((row.extra_data or {}).get("reranker_provider") or "unknown")
        for row in rows
    )
    query_rewrite_dist = Counter(
        (
            "enabled"
            if bool((row.extra_data or {}).get("query_rewrite_enabled"))
            else "disabled"
        )
        for row in rows
    )
    query_rewrite_mode_dist = Counter(
        (
            (row.extra_data or {}).get("query_rewrite_mode")
            or (
                "disabled"
                if not bool((row.extra_data or {}).get("query_rewrite_enabled"))
                else "unknown"
            )
        )
        for row in rows
    )
    query_variant_bucket_dist = Counter(
        _variant_bucket((row.extra_data or {}).get("query_variant_count"))
        for row in rows
    )
    llm_backend_dist = Counter(
        ((row.extra_data or {}).get("llm_backend") or "unknown")
        for row in rows
    )
    embedding_backend_dist = Counter(
        ((row.extra_data or {}).get("embedding_backend") or "unknown")
        for row in rows
    )
    vlm_backend_dist = Counter(
        ((row.extra_data or {}).get("vlm_backend") or "unknown")
        for row in rows
    )
    reranker_backend_dist = Counter(
        ((row.extra_data or {}).get("reranker_backend") or "unknown")
        for row in rows
    )
    confidence_band_dist = Counter(
        ((row.extra_data or {}).get("confidence_band") or _confidence_band(row.confidence))
        for row in rows
    )
    grounding_level_dist = Counter(
        ((row.extra_data or {}).get("grounding_level") or "unknown")
        for row in rows
    )
    fallback_reason_dist = Counter(
        (row.fallback_reason or "unspecified")
        for row in rows
        if row.used_fallback
    )

    return {
        "window_days": days,
        "window_start": window_start,
        "window_end": now,
        "filters": {
            "class_id": class_id,
        },
        "totals": {
            "queries": total,
            "success": success_count,
            "fallback": fallback_count,
            "main_chain_success": main_chain_success_count,
        },
        "rates": {
            "success_rate": _ratio(success_count, total),
            "fallback_rate": _ratio(fallback_count, total),
            "main_chain_success_rate": _ratio(main_chain_success_count, total),
        },
        "latency_ms": _latency_summary(latencies),
        "quality": {
            "avg_confidence": _avg(confidences),
            "avg_source_count": _avg(source_counts),
        },
        "distributions": {
            "query_mode": dict(query_mode_dist),
            "engine": dict(engine_dist),
            "retrieval_strategy": dict(retrieval_strategy_dist),
            "reranker": dict(reranker_dist),
            "query_rewrite": dict(query_rewrite_dist),
            "query_rewrite_mode": dict(query_rewrite_mode_dist),
            "query_variant_bucket": dict(query_variant_bucket_dist),
            "llm_backend": dict(llm_backend_dist),
            "embedding_backend": dict(embedding_backend_dist),
            "vlm_backend": dict(vlm_backend_dist),
            "reranker_backend": dict(reranker_backend_dist),
            "confidence_band": dict(confidence_band_dist),
            "grounding_level": dict(grounding_level_dist),
            "fallback_reason": dict(fallback_reason_dist),
        },
    }


def get_rag_rewrite_ablation(
    db: Session,
    *,
    days: int = 7,
    class_id: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=days)
    query = db.query(RAGQueryEvent).filter(RAGQueryEvent.created_at >= window_start)
    if class_id:
        query = query.filter(RAGQueryEvent.class_id == class_id)

    rows = query.order_by(RAGQueryEvent.created_at.desc()).all()
    by_enabled: dict[str, list[RAGQueryEvent]] = {"enabled": [], "disabled": []}
    by_mode: dict[str, list[RAGQueryEvent]] = defaultdict(list)
    by_bucket: dict[str, list[RAGQueryEvent]] = defaultdict(list)

    for row in rows:
        extra = row.extra_data or {}
        enabled = bool(extra.get("query_rewrite_enabled"))
        enabled_key = "enabled" if enabled else "disabled"
        by_enabled[enabled_key].append(row)

        mode_key = extra.get("query_rewrite_mode") or ("disabled" if not enabled else "unknown")
        by_mode[str(mode_key)].append(row)

        bucket_key = _variant_bucket(extra.get("query_variant_count"))
        by_bucket[bucket_key].append(row)

    return {
        "window_days": days,
        "window_start": window_start,
        "window_end": now,
        "filters": {
            "class_id": class_id,
        },
        "totals": {
            "queries": len(rows),
        },
        "groups": {
            "rewrite_enabled": {
                "enabled": _segment_metrics(by_enabled["enabled"]),
                "disabled": _segment_metrics(by_enabled["disabled"]),
            },
            "rewrite_mode": {
                key: _segment_metrics(group_rows)
                for key, group_rows in sorted(by_mode.items(), key=lambda item: item[0])
            },
            "query_variant_bucket": {
                key: _segment_metrics(group_rows)
                for key, group_rows in sorted(by_bucket.items(), key=lambda item: item[0])
            },
        },
    }


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(part / total, 4)


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def _latency_summary(latencies: list[float]) -> dict[str, float]:
    if not latencies:
        return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0}

    sorted_values = sorted(latencies)
    return {
        "avg": _avg(sorted_values),
        "p50": _percentile(sorted_values, 50),
        "p95": _percentile(sorted_values, 95),
        "max": round(sorted_values[-1], 4),
    }


def _segment_metrics(rows: list[RAGQueryEvent]) -> dict[str, Any]:
    total = len(rows)
    success_count = sum(1 for row in rows if row.success)
    fallback_count = sum(1 for row in rows if row.used_fallback)
    latencies = [float(row.latency_ms) for row in rows if row.latency_ms is not None]
    confidences = [float(row.confidence) for row in rows if row.confidence is not None]
    source_counts = [int(row.source_count) for row in rows if row.source_count is not None]
    return {
        "queries": total,
        "success_rate": _ratio(success_count, total),
        "fallback_rate": _ratio(fallback_count, total),
        "avg_confidence": _avg(confidences),
        "avg_source_count": _avg(source_counts),
        "latency_ms": _latency_summary(latencies),
    }


def _percentile(sorted_values: list[float], percentile: int) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return round(sorted_values[0], 4)
    k = (len(sorted_values) - 1) * (percentile / 100)
    lower = int(k)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = k - lower
    value = sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
    return round(value, 4)


def _variant_bucket(value: Any) -> str:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return "unknown"

    if count <= 0:
        return "0"
    if count == 1:
        return "1"
    if count == 2:
        return "2"
    if count == 3:
        return "3"
    return "4+"


def _confidence_band(value: Any) -> str:
    try:
        confidence = float(value or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.6:
        return "medium"
    if confidence > 0:
        return "low"
    return "none"
