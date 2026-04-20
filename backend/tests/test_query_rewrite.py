from types import SimpleNamespace

from app.integrations.rag.query_rewrite import build_query_rewrite_bundle
from app.integrations.rag.simple_engine import SimpleRAGEngine


def test_query_rewrite_disabled_keeps_original_query():
    bundle = build_query_rewrite_bundle(
        question="How does TCP slow start work?",
        enabled=False,
        mode="simple",
        max_variants=3,
    )
    assert bundle["enabled"] is False
    assert bundle["mode"] == "disabled"
    assert bundle["queries"] == ["How does TCP slow start work?"]
    assert bundle["variant_count"] == 1


def test_query_rewrite_simple_generates_multiple_variants():
    bundle = build_query_rewrite_bundle(
        question="Please explain how TCP slow start works in congestion control.",
        enabled=True,
        mode="simple",
        max_variants=3,
    )
    assert bundle["enabled"] is True
    assert bundle["mode"] == "simple"
    assert bundle["variant_count"] >= 2
    assert len(bundle["queries"]) <= 3
    assert len(set(bundle["queries"])) == len(bundle["queries"])


def test_simple_engine_collects_candidates_with_query_variants(monkeypatch):
    engine = SimpleRAGEngine()
    monkeypatch.setattr(engine, "_normalized_retrieval_strategy", lambda: "lexical")

    task = SimpleNamespace(
        chunks=[
            {
                "source_name": "network_notes.pdf",
                "source_type": "pdf",
                "page": 2,
                "chunk_id": "chunk-1",
                "text": "TCP slow start grows congestion window before threshold.",
            }
        ]
    )
    bundle = engine._collect_retrieval_candidates(
        class_id="class-demo",
        question="Explain TCP slow start.",
        tasks=[task],
        review_matches=[],
        image_contexts=[],
        query_variants=[
            "Explain TCP slow start.",
            "tcp congestion window threshold",
        ],
    )

    assert bundle["candidate_count"] == 1
    assert bundle["query_variant_count"] == 2
    assert bundle["candidates"][0]["matched_query_count"] >= 1
