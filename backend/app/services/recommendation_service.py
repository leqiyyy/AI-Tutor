"""Explainable recommendation scoring utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.models.personalization import RecommendationEvent


DEFAULT_WEIGHTS = {
    "knowledge_gap_score": 0.35,
    "content_relevance": 0.20,
    "urgency": 0.15,
    "difficulty_match": 0.10,
    "user_preference": 0.10,
    "freshness": 0.10,
}


@dataclass(frozen=True)
class RecommendationCandidate:
    target_id: str
    target_type: str
    title: str
    signals: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def score_candidate(
    candidate: RecommendationCandidate,
    *,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    active_weights = weights or DEFAULT_WEIGHTS
    evidence_signals = {
        key: _clamp01(candidate.signals.get(key, 0.0))
        for key in active_weights
    }
    score = sum(evidence_signals[key] * active_weights[key] for key in active_weights)
    return {
        "target_id": candidate.target_id,
        "target_type": candidate.target_type,
        "title": candidate.title,
        "score": round(score, 4),
        "reason": build_recommendation_reason(evidence_signals),
        "evidence_signals": evidence_signals,
        "metadata": candidate.metadata,
        "algorithm": {
            "name": "explainable_weighted_rules_v2",
            "weights": active_weights,
        },
    }


def rank_candidates(
    candidates: list[RecommendationCandidate],
    *,
    weights: dict[str, float] | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    scored = [score_candidate(candidate, weights=weights) for candidate in candidates]
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[: max(1, int(limit))]


def rank_learning_resources_for_student(
    db: "Session",
    *,
    user_id: str,
    class_id: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Rank resources linked to weak concepts using the explainable scorer."""

    from app.models.personalization import LearningResourceLink, StudentConceptMastery

    mastery_rows = (
        db.query(StudentConceptMastery)
        .filter(
            StudentConceptMastery.user_id == user_id,
            StudentConceptMastery.class_id == class_id,
        )
        .all()
    )
    mastery_by_concept = {
        row.concept_id: row
        for row in mastery_rows
        if row.concept_id
    }
    mastery_by_name = {
        row.concept_name: row
        for row in mastery_rows
        if row.concept_name
    }

    links = (
        db.query(LearningResourceLink)
        .filter(LearningResourceLink.class_id == class_id)
        .order_by(LearningResourceLink.created_at.desc())
        .limit(100)
        .all()
    )
    candidates: list[RecommendationCandidate] = []
    for link in links:
        mastery = mastery_by_concept.get(link.concept_id)
        if not mastery and link.title:
            mastery = mastery_by_name.get(link.title)
        mastery_score = float(mastery.mastery_score) if mastery else None
        candidates.append(
            RecommendationCandidate(
                target_id=link.resource_id,
                target_type=link.resource_type,
                title=link.title or link.resource_id,
                signals={
                    "knowledge_gap_score": build_mastery_gap_signal(mastery_score),
                    "content_relevance": link.relevance,
                    "difficulty_match": build_difficulty_match_signal(
                        mastery_score=mastery_score,
                        resource_difficulty=link.difficulty,
                    ),
                    "freshness": 0.5,
                },
                metadata={
                    "concept_id": link.concept_id,
                    "link_id": link.id,
                    "mastery_score": mastery_score,
                },
            )
        )
    return rank_candidates(candidates, limit=limit)


def record_recommendation_event(
    db: "Session",
    *,
    user_id: str,
    recommendation_type: str,
    target_id: str,
    event_type: str,
    class_id: str | None = None,
    score: float | None = None,
    extra_data: dict[str, Any] | None = None,
) -> RecommendationEvent:
    from app.models.personalization import RecommendationEvent

    row = RecommendationEvent(
        user_id=user_id,
        class_id=class_id,
        recommendation_type=recommendation_type,
        target_id=target_id,
        event_type=event_type,
        score=score,
        extra_data=extra_data or {},
    )
    db.add(row)
    db.flush()
    return row


def build_recommendation_reason(signals: dict[str, float]) -> str:
    ordered = sorted(signals.items(), key=lambda item: item[1], reverse=True)
    strongest = [(key, value) for key, value in ordered if value > 0.0][:3]
    if not strongest:
        return "Recommended as a fallback course resource."
    labels = {
        "knowledge_gap_score": "targets a weak concept",
        "content_relevance": "matches the current course topic",
        "urgency": "is timely for current learning needs",
        "difficulty_match": "matches the learner's current level",
        "user_preference": "matches prior learning preferences",
        "freshness": "is recent course material",
    }
    return "; ".join(labels.get(key, key) for key, _ in strongest)


def build_mastery_gap_signal(mastery_score: float | None) -> float:
    if mastery_score is None:
        return 0.5
    return _clamp01(1.0 - float(mastery_score))


def build_difficulty_match_signal(
    *,
    mastery_score: float | None,
    resource_difficulty: float | None,
) -> float:
    if mastery_score is None or resource_difficulty is None:
        return 0.5
    # A resource is ideal when it is slightly above current mastery.
    ideal = _clamp01(float(mastery_score) + 0.15)
    distance = abs(_clamp01(float(resource_difficulty)) - ideal)
    return _clamp01(1.0 - distance)


def _clamp01(value: float | int | None) -> float:
    try:
        numeric = float(value if value is not None else 0.0)
    except (TypeError, ValueError):
        numeric = 0.0
    return round(max(0.0, min(1.0, numeric)), 4)
