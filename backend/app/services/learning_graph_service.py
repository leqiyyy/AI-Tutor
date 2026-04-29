"""Teaching-graph projection helpers.

The projection consumes the RAG knowledge graph but keeps learning-path data in
separate tables/services so retrieval graph semantics remain untouched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


TEACHING_RELATION_ALIASES = {
    "prerequisite": "prerequisite",
    "requires": "prerequisite",
    "precedes": "prerequisite",
    "part_of": "part_of",
    "contains": "part_of",
    "related": "related_to",
    "related_to": "related_to",
    "example": "example_of",
    "example_of": "example_of",
}


@dataclass(frozen=True)
class ProjectedConcept:
    source_entity_id: str
    class_id: str
    concept_name: str
    concept_type: str | None = None
    difficulty: float = 0.5
    importance: float = 0.5
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectedRelation:
    source_entity_id: str
    target_entity_id: str
    class_id: str
    relation_type: str
    weight: float = 1.0
    confidence: float = 0.5
    source_relation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def project_knowledge_entities(entities: list[Any]) -> list[ProjectedConcept]:
    projected = []
    for entity in entities:
        name = str(getattr(entity, "name", "") or "").strip()
        if not name:
            continue
        projected.append(
            ProjectedConcept(
                source_entity_id=str(getattr(entity, "id", "")),
                class_id=str(getattr(entity, "class_id", "")),
                concept_name=name,
                concept_type=getattr(entity, "entity_type", None),
                confidence=_clamp01(getattr(entity, "confidence", 0.5)),
                difficulty=_infer_difficulty(entity),
                importance=_infer_importance(entity),
                metadata={
                    "description": getattr(entity, "description", None),
                    "source_material_id": getattr(entity, "source_material_id", None),
                    "provenance": getattr(entity, "provenance", None),
                },
            )
        )
    return projected


def project_knowledge_relations(relations: list[Any]) -> list[ProjectedRelation]:
    projected = []
    for relation in relations:
        raw_type = str(getattr(relation, "relation_type", "") or "related_to").strip().lower()
        teaching_type = TEACHING_RELATION_ALIASES.get(raw_type, "related_to")
        projected.append(
            ProjectedRelation(
                source_entity_id=str(getattr(relation, "source_id", "")),
                target_entity_id=str(getattr(relation, "target_id", "")),
                class_id=str(getattr(relation, "class_id", "")),
                relation_type=teaching_type,
                weight=float(getattr(relation, "weight", 1.0) or 1.0),
                confidence=_clamp01(getattr(relation, "confidence", 0.5)),
                source_relation_id=str(getattr(relation, "id", "") or "") or None,
                metadata={
                    "source_span": getattr(relation, "source_span", None),
                    "provenance": getattr(relation, "provenance", None),
                    "raw_relation_type": raw_type,
                },
            )
        )
    return projected


def rebuild_learning_graph_projection(
    db: "Session",
    *,
    class_id: str,
) -> dict[str, int]:
    """Rebuild teaching graph projection for one class from current KG rows."""

    from app.models.knowledge import KnowledgeEntity, KnowledgeRelation

    entities = (
        db.query(KnowledgeEntity)
        .filter(KnowledgeEntity.class_id == class_id)
        .all()
    )
    relations = (
        db.query(KnowledgeRelation)
        .filter(KnowledgeRelation.class_id == class_id)
        .all()
    )
    projected_concepts = project_knowledge_entities(entities)
    concept_map = _upsert_projected_concepts(db, projected_concepts)
    relation_count = _replace_projected_relations(
        db,
        class_id=class_id,
        projected_relations=project_knowledge_relations(relations),
        concept_id_by_source_entity_id=concept_map,
    )
    db.flush()
    return {
        "source_entity_count": len(entities),
        "source_relation_count": len(relations),
        "concept_count": len(concept_map),
        "relation_count": relation_count,
    }


def _upsert_projected_concepts(
    db: "Session",
    projected_concepts: list[ProjectedConcept],
) -> dict[str, str]:
    from app.models.personalization import LearningConcept

    concept_id_by_source: dict[str, str] = {}
    for concept in projected_concepts:
        row = (
            db.query(LearningConcept)
            .filter(
                LearningConcept.class_id == concept.class_id,
                LearningConcept.source_entity_id == concept.source_entity_id,
            )
            .first()
        )
        if not row:
            row = LearningConcept(
                class_id=concept.class_id,
                source_entity_id=concept.source_entity_id,
                concept_name=concept.concept_name,
            )
            db.add(row)
            db.flush()

        row.concept_name = concept.concept_name
        row.concept_type = concept.concept_type
        row.difficulty = concept.difficulty
        row.importance = concept.importance
        row.confidence = concept.confidence
        row.extra_data = concept.metadata
        concept_id_by_source[concept.source_entity_id] = row.id
    return concept_id_by_source


def _replace_projected_relations(
    db: "Session",
    *,
    class_id: str,
    projected_relations: list[ProjectedRelation],
    concept_id_by_source_entity_id: dict[str, str],
) -> int:
    from app.models.personalization import LearningConceptRelation

    db.query(LearningConceptRelation).filter(
        LearningConceptRelation.class_id == class_id
    ).delete(synchronize_session=False)

    count = 0
    for relation in projected_relations:
        source_concept_id = concept_id_by_source_entity_id.get(relation.source_entity_id)
        target_concept_id = concept_id_by_source_entity_id.get(relation.target_entity_id)
        if not source_concept_id or not target_concept_id:
            continue
        db.add(
            LearningConceptRelation(
                class_id=class_id,
                source_concept_id=source_concept_id,
                target_concept_id=target_concept_id,
                relation_type=relation.relation_type,
                weight=relation.weight,
                confidence=relation.confidence,
                source_relation_id=relation.source_relation_id,
                extra_data=relation.metadata,
            )
        )
        count += 1
    return count


def _infer_difficulty(entity: Any) -> float:
    entity_type = str(getattr(entity, "entity_type", "") or "").lower()
    if entity_type in {"formula", "theorem", "algorithm"}:
        return 0.75
    if entity_type in {"example", "tool"}:
        return 0.35
    return 0.5


def _infer_importance(entity: Any) -> float:
    entity_type = str(getattr(entity, "entity_type", "") or "").lower()
    if entity_type in {"course_concept", "learning_objective", "assessment_point"}:
        return 0.8
    if entity_type in {"example", "tool"}:
        return 0.45
    return 0.6


def _clamp01(value: float | int | None) -> float:
    try:
        numeric = float(value if value is not None else 0.5)
    except (TypeError, ValueError):
        numeric = 0.5
    return max(0.0, min(1.0, numeric))
