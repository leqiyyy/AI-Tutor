from app.integrations.rag.quality import build_evidence_quality, build_review_context


def test_build_review_context_marks_strong_evidence_as_direct_answer():
    sources = [
        {"name": "tcp.md", "score": 0.92},
        {"name": "congestion.md", "score": 0.88},
    ]

    quality = build_evidence_quality(sources, 0.87)
    review = build_review_context(sources, 0.87)

    assert quality["grounding_level"] == "strong"
    assert review["needs_teacher_review"] is False
    assert review["review_priority"] == "none"
    assert review["review_reasons"] == []
    assert review["recommended_action"] == "direct_answer"


def test_build_review_context_marks_ungrounded_answer_for_teacher_review():
    review = build_review_context([], 0.91)

    assert review["needs_teacher_review"] is True
    assert review["review_priority"] == "high"
    assert "no_supporting_sources" in review["review_reasons"]
    assert "weak_grounding" in review["review_reasons"]
    assert review["recommended_action"] == "teacher_review"


def test_build_review_context_adds_negative_feedback_reason():
    sources = [{"name": "tcp.md", "score": 0.61}]

    review = build_review_context(sources, 0.74, trigger="dislike", feedback="dislike")

    assert review["needs_teacher_review"] is True
    assert review["review_priority"] == "high"
    assert "negative_user_feedback" in review["review_reasons"]
