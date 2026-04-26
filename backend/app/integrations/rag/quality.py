from __future__ import annotations

from typing import Any


def build_evidence_quality(
    sources: list[dict] | None,
    confidence: float | None,
) -> dict[str, Any]:
    """Summarize retrieval grounding in a stable shape for APIs and metrics."""

    normalized_sources = [source for source in (sources or []) if isinstance(source, dict)]
    scores = [
        score
        for score in (_safe_float(source.get("score") or source.get("retrieval_score")) for source in normalized_sources)
        if score is not None
    ]
    confidence_value = _clamp(_safe_float(confidence) or 0.0)
    source_count = len(normalized_sources)
    avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
    max_score = round(max(scores), 4) if scores else 0.0
    coverage_score = round(min(1.0, source_count / 3), 4)
    evidence_score = round(
        confidence_value * 0.4
        + avg_score * 0.4
        + coverage_score * 0.2,
        4,
    )
    grounding_level = _grounding_level(
        confidence=confidence_value,
        source_count=source_count,
        avg_score=avg_score,
    )
    return {
        "confidence": round(confidence_value, 4),
        "confidence_band": _confidence_band(confidence_value),
        "source_count": source_count,
        "scored_source_count": len(scores),
        "avg_source_score": avg_score,
        "max_source_score": max_score,
        "coverage_score": coverage_score,
        "evidence_score": evidence_score,
        "grounded": grounding_level in {"strong", "adequate"},
        "grounding_level": grounding_level,
        "needs_teacher_review": confidence_value < 0.7 or source_count == 0,
        "rationale": _quality_rationale(grounding_level),
    }


def build_review_context(
    sources: list[dict] | None,
    confidence: float | None,
    *,
    trigger: str = "low_confidence",
    feedback: str | None = None,
) -> dict[str, Any]:
    quality = build_evidence_quality(sources, confidence)
    reasons = _review_reasons(quality, feedback=feedback)
    priority = _review_priority(quality, reasons=reasons, trigger=trigger)
    needs_teacher_review = trigger == "manual" or bool(reasons)
    return {
        "trigger": trigger,
        "feedback": feedback,
        "needs_teacher_review": needs_teacher_review,
        "review_priority": priority,
        "review_reasons": reasons,
        "review_reason_labels": [_review_reason_label(reason) for reason in reasons],
        "recommended_action": _recommended_action(needs_teacher_review, priority=priority),
        "quality": quality,
    }


def _confidence_band(value: float) -> str:
    if value >= 0.8:
        return "high"
    if value >= 0.6:
        return "medium"
    if value > 0:
        return "low"
    return "none"


def _grounding_level(*, confidence: float, source_count: int, avg_score: float) -> str:
    if source_count <= 0:
        return "ungrounded"
    if confidence >= 0.8 and source_count >= 2 and avg_score >= 0.55:
        return "strong"
    if confidence >= 0.6 and avg_score >= 0.35:
        return "adequate"
    return "weak"


def _quality_rationale(level: str) -> str:
    return {
        "strong": "Multiple scored sources support the answer with high confidence.",
        "adequate": "At least one source supports the answer, but evidence should still be checked for important decisions.",
        "weak": "The answer has limited or low-scoring evidence and may need teacher review.",
        "ungrounded": "No usable course evidence was attached to the answer.",
    }.get(level, "Evidence quality could not be determined.")


def _review_reasons(quality: dict[str, Any], *, feedback: str | None = None) -> list[str]:
    reasons: list[str] = []
    confidence = _safe_float(quality.get("confidence")) or 0.0
    source_count = int(quality.get("source_count") or 0)
    evidence_score = _safe_float(quality.get("evidence_score")) or 0.0
    grounding_level = str(quality.get("grounding_level") or "")

    if confidence < 0.7:
        reasons.append("confidence_below_threshold")
    if source_count == 0:
        reasons.append("no_supporting_sources")
    elif source_count == 1:
        reasons.append("limited_source_coverage")
    if evidence_score < 0.45:
        reasons.append("low_evidence_score")
    if grounding_level in {"weak", "ungrounded"}:
        reasons.append("weak_grounding")
    if str(feedback or "").strip().lower() == "dislike":
        reasons.append("negative_user_feedback")
    return reasons


def _review_priority(
    quality: dict[str, Any],
    *,
    reasons: list[str],
    trigger: str,
) -> str:
    if trigger == "manual":
        return "high"
    if not reasons:
        return "none"
    confidence = _safe_float(quality.get("confidence")) or 0.0
    if "negative_user_feedback" in reasons or "no_supporting_sources" in reasons or confidence < 0.4:
        return "high"
    if "weak_grounding" in reasons or "low_evidence_score" in reasons:
        return "medium"
    return "low"


def _recommended_action(needs_teacher_review: bool, *, priority: str) -> str:
    if needs_teacher_review:
        return "teacher_review"
    if priority in {"low", "medium"}:
        return "answer_with_caution"
    return "direct_answer"


def _review_reason_label(reason: str) -> str:
    return {
        "confidence_below_threshold": "Answer confidence is below the review threshold.",
        "no_supporting_sources": "No supporting course evidence was retrieved.",
        "limited_source_coverage": "Only one supporting source was retrieved.",
        "low_evidence_score": "The combined evidence score is low.",
        "weak_grounding": "The retrieved evidence is weakly grounded.",
        "negative_user_feedback": "The student marked the answer as unhelpful.",
    }.get(reason, "Review is recommended due to evidence risk.")


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
