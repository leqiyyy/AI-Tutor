"""Learning-path generation that uses a teaching graph projection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.models.personalization import LearningPath


PREREQUISITE_RELATIONS = {"prerequisite", "requires", "before"}


@dataclass(frozen=True)
class PathConcept:
    id: str
    name: str
    mastery_score: float = 0.5
    importance: float = 0.5
    difficulty: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PathRelation:
    source_id: str
    target_id: str
    relation_type: str
    weight: float = 1.0


def generate_learning_path(
    *,
    concepts: list[PathConcept],
    relations: list[PathRelation],
    resources_by_concept: dict[str, list[dict[str, Any]]] | None = None,
    max_steps: int = 7,
) -> dict[str, Any]:
    resources_by_concept = resources_by_concept or {}
    ordered = order_concepts_for_learning(concepts=concepts, relations=relations)
    selected = ordered[: max(1, int(max_steps))]
    steps = []
    for index, concept in enumerate(selected, start=1):
        resources = resources_by_concept.get(concept.id, [])[:3]
        steps.append({
            "step": index,
            "concept_id": concept.id,
            "concept_name": concept.name,
            "goal": f"Strengthen understanding of {concept.name}",
            "recommended_resources": resources,
            "estimated_minutes": estimate_minutes(concept),
            "reason": build_step_reason(concept, resources),
            "evidence_signals": {
                "mastery_gap": round(1.0 - concept.mastery_score, 4),
                "importance": round(concept.importance, 4),
                "difficulty": round(concept.difficulty, 4),
                "resource_count": len(resources),
            },
        })
    return {
        "strategy": "topological_rules_v1",
        "steps": steps,
        "summary": {
            "candidate_count": len(concepts),
            "selected_count": len(steps),
            "prerequisite_relation_count": sum(
                1 for relation in relations if relation.relation_type in PREREQUISITE_RELATIONS
            ),
        },
    }


def generate_learning_path_for_student(
    db: "Session",
    *,
    user_id: str,
    class_id: str,
    max_steps: int = 7,
    persist: bool = False,
) -> dict[str, Any]:
    """Generate a path from persisted teaching graph and mastery snapshots."""

    from app.models.personalization import (
        LearningConcept,
        LearningConceptRelation,
        StudentConceptMastery,
    )

    concepts = db.query(LearningConcept).filter(LearningConcept.class_id == class_id).all()
    mastery_by_concept_id = {
        row.concept_id: row
        for row in db.query(StudentConceptMastery)
        .filter(
            StudentConceptMastery.user_id == user_id,
            StudentConceptMastery.class_id == class_id,
        )
        .all()
        if row.concept_id
    }
    path_concepts = []
    for concept in concepts:
        mastery = mastery_by_concept_id.get(concept.id)
        path_concepts.append(
            PathConcept(
                id=concept.id,
                name=concept.concept_name,
                mastery_score=float(mastery.mastery_score) if mastery else 0.5,
                importance=float(concept.importance or 0.5),
                difficulty=float(concept.difficulty or 0.5),
                metadata={
                    "concept_type": concept.concept_type,
                    "source_entity_id": concept.source_entity_id,
                },
            )
        )

    relations = [
        PathRelation(
            source_id=row.source_concept_id,
            target_id=row.target_concept_id,
            relation_type=row.relation_type,
            weight=float(row.weight or 1.0),
        )
        for row in db.query(LearningConceptRelation)
        .filter(LearningConceptRelation.class_id == class_id)
        .all()
    ]
    resources = _resources_by_concept(db, class_id=class_id)
    payload = generate_learning_path(
        concepts=path_concepts,
        relations=relations,
        resources_by_concept=resources,
        max_steps=max_steps,
    )
    if persist:
        path = persist_learning_path(
            db,
            user_id=user_id,
            class_id=class_id,
            path_payload=payload,
        )
        payload["path_id"] = path.id
    return payload


def persist_learning_path(
    db: "Session",
    *,
    user_id: str,
    class_id: str,
    path_payload: dict[str, Any],
) -> LearningPath:
    from app.models.personalization import LearningPath, LearningPathStep

    path = LearningPath(
        user_id=user_id,
        class_id=class_id,
        title="Personalized learning path",
        strategy=path_payload.get("strategy") or "topological_rules_v1",
        extra_data={"summary": path_payload.get("summary") or {}},
    )
    db.add(path)
    db.flush()
    for step in path_payload.get("steps") or []:
        db.add(
            LearningPathStep(
                path_id=path.id,
                step_order=int(step.get("step") or 0),
                concept_id=step.get("concept_id"),
                concept_name=step.get("concept_name") or "",
                goal=step.get("goal"),
                recommended_resources=step.get("recommended_resources") or [],
                estimated_minutes=step.get("estimated_minutes"),
                reason=step.get("reason"),
                extra_data={"evidence_signals": step.get("evidence_signals") or {}},
            )
        )
    db.flush()
    return path


def order_concepts_for_learning(
    *,
    concepts: list[PathConcept],
    relations: list[PathRelation],
) -> list[PathConcept]:
    concept_map = {concept.id: concept for concept in concepts}
    incoming = {concept.id: 0 for concept in concepts}
    outgoing: dict[str, list[str]] = {concept.id: [] for concept in concepts}
    for relation in relations:
        if relation.relation_type not in PREREQUISITE_RELATIONS:
            continue
        if relation.source_id not in concept_map or relation.target_id not in concept_map:
            continue
        outgoing[relation.source_id].append(relation.target_id)
        incoming[relation.target_id] += 1

    ready = sorted(
        [concept_id for concept_id, count in incoming.items() if count == 0],
        key=lambda concept_id: _learning_priority(concept_map[concept_id]),
    )
    ordered_ids: list[str] = []
    while ready:
        concept_id = ready.pop(0)
        ordered_ids.append(concept_id)
        for target_id in outgoing.get(concept_id, []):
            incoming[target_id] -= 1
            if incoming[target_id] == 0:
                ready.append(target_id)
        ready.sort(key=lambda item: _learning_priority(concept_map[item]))

    remaining = [concept.id for concept in concepts if concept.id not in set(ordered_ids)]
    remaining.sort(key=lambda concept_id: _learning_priority(concept_map[concept_id]))
    ordered_ids.extend(remaining)
    return [concept_map[concept_id] for concept_id in ordered_ids]


def _resources_by_concept(
    db: "Session",
    *,
    class_id: str,
) -> dict[str, list[dict[str, Any]]]:
    from app.models.personalization import LearningResourceLink

    rows = (
        db.query(LearningResourceLink)
        .filter(LearningResourceLink.class_id == class_id)
        .order_by(LearningResourceLink.relevance.desc())
        .all()
    )
    result: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        result.setdefault(row.concept_id, []).append({
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "title": row.title,
            "relevance": row.relevance,
            "difficulty": row.difficulty,
        })
    return result


def estimate_minutes(concept: PathConcept) -> int:
    return int(20 + concept.difficulty * 40)


def build_step_reason(concept: PathConcept, resources: list[dict[str, Any]]) -> str:
    parts = []
    if concept.mastery_score < 0.4:
        parts.append("low mastery")
    elif concept.mastery_score < 0.7:
        parts.append("needs reinforcement")
    if concept.importance >= 0.7:
        parts.append("high importance")
    if resources:
        parts.append("has matched learning resources")
    return "; ".join(parts) if parts else "balanced review step"


def _learning_priority(concept: PathConcept) -> tuple[float, float, float]:
    return (
        round(concept.mastery_score, 4),
        -round(concept.importance, 4),
        round(concept.difficulty, 4),
    )
