from app.services.conversation_context_service import (
    classify_context_intent,
    rewrite_standalone_question,
)
from app.services.learning_graph_service import project_knowledge_entities, project_knowledge_relations
from app.services.learning_path_service import PathConcept, PathRelation, generate_learning_path
from app.services.recommendation_service import RecommendationCandidate, rank_candidates
from app.services.student_profile_service import MasteryEvidence, estimate_mastery_from_evidence


class Obj:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_conversation_followup_rewrite_uses_last_user_anchor():
    history = [
        {"role": "user", "content": "TCP 慢启动的两个关键阶段是什么？"},
        {"role": "ai", "content": "第一是指数增长，第二是拥塞避免。"},
    ]

    rewritten = rewrite_standalone_question(
        history=history,
        summary="",
        question="那第二点再解释一下",
        intent=classify_context_intent(history, "那第二点再解释一下"),
    )

    assert "TCP 慢启动" in rewritten
    assert "第二点" in rewritten


def test_recommendation_ranker_prefers_mastery_gap_and_relevance():
    ranked = rank_candidates([
        RecommendationCandidate(
            target_id="m1",
            target_type="material",
            title="General notes",
            signals={"freshness": 1.0},
        ),
        RecommendationCandidate(
            target_id="m2",
            target_type="material",
            title="Weak concept review",
            signals={"knowledge_gap_score": 1.0, "content_relevance": 0.8},
        ),
    ])

    assert ranked[0]["target_id"] == "m2"
    assert ranked[0]["algorithm"]["name"] == "explainable_weighted_rules_v2"


def test_mastery_estimation_aggregates_positive_and_negative_evidence():
    rows = estimate_mastery_from_evidence([
        MasteryEvidence(concept_name="TCP", signal_type="task_score", value=1.0),
        MasteryEvidence(concept_name="TCP", signal_type="low_confidence", value=1.0),
        MasteryEvidence(concept_name="CIDR", signal_type="dislike", value=1.0),
    ])

    assert rows["TCP"]["evidence_count"] == 2
    assert rows["TCP"]["mastery_score"] > rows["CIDR"]["mastery_score"]


def test_learning_path_respects_prerequisite_order():
    path = generate_learning_path(
        concepts=[
            PathConcept(id="advanced", name="拥塞避免", mastery_score=0.2, difficulty=0.8),
            PathConcept(id="base", name="TCP 基础", mastery_score=0.4, difficulty=0.3),
        ],
        relations=[
            PathRelation(source_id="base", target_id="advanced", relation_type="prerequisite"),
        ],
    )

    names = [step["concept_name"] for step in path["steps"]]
    assert names.index("TCP 基础") < names.index("拥塞避免")


def test_learning_graph_projection_normalizes_relation_types():
    concepts = project_knowledge_entities([
        Obj(id="e1", class_id="c1", name="TCP", entity_type="course_concept", confidence=0.9),
    ])
    relations = project_knowledge_relations([
        Obj(id="r1", class_id="c1", source_id="e1", target_id="e2", relation_type="requires", weight=1.0, confidence=0.8),
    ])

    assert concepts[0].importance == 0.8
    assert relations[0].relation_type == "prerequisite"

