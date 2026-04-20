import asyncio

from app.integrations.reranker.mock_reranker import MockReranker


def test_mock_reranker_scores_and_sorts_candidates():
    reranker = MockReranker()
    candidates = [
        {
            "chunk_id": "a",
            "snippet": "TCP slow start rapidly grows congestion window.",
            "raw_text": "TCP slow start rapidly grows congestion window.",
            "retrieval_score": 0.42,
        },
        {
            "chunk_id": "b",
            "snippet": "Queue fairness under burst traffic.",
            "raw_text": "Queue fairness under burst traffic.",
            "retrieval_score": 0.55,
        },
    ]
    result = asyncio.run(
        reranker.rerank(
            query="Explain TCP slow start with queue example",
            candidates=candidates,
            context={
                "review_matches": [{"final_answer": "teacher answer"}],
                "image_contexts": ["diagram of congestion window"],
            },
        )
    )
    assert len(result) == 2
    assert result[0]["rerank_score"] >= result[1]["rerank_score"]
    assert result[0]["reranker_provider"] == "mock"
    assert "rerank_components" in result[0]
