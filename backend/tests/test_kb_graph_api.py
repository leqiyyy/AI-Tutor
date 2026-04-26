import importlib.util
import io

import pytest


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("raganything") is None,
    reason="Strict RAG-Anything graph API tests require the raganything package to be installed.",
)


def test_course_graph_api_exposes_summary_and_filters(client, teacher_headers):
    course_id = client.get("/api/v1/courses", headers=teacher_headers).json()["data"][0]["id"]

    upload = client.post(
        f"/api/v1/courses/{course_id}/files/upload",
        headers=teacher_headers,
        files={"file": ("graph_filter_notes.txt", io.BytesIO(b"Congestion control improves throughput stability."), "text/plain")},
        data={"title": "Graph Filter Notes"},
    )
    assert upload.status_code == 200

    graph = client.get(f"/api/v1/courses/{course_id}/graph", headers=teacher_headers)
    filtered = client.get(
        f"/api/v1/courses/{course_id}/graph?entity_type=concept&min_confidence=0.5&limit=20",
        headers=teacher_headers,
    )

    assert graph.status_code == 200
    assert filtered.status_code == 200

    graph_data = graph.json()["data"]
    filtered_data = filtered.json()["data"]

    assert "nodes" in graph_data
    assert "edges" in graph_data
    assert "stats" in graph_data
    assert "summary" in graph_data
    assert "legend" in graph_data
    assert "materials" in graph_data
    assert "filters" in graph_data

    assert filtered_data["filters"]["entity_type"] == "concept"
    assert filtered_data["filters"]["min_confidence"] == 0.5
    assert filtered_data["filters"]["limit"] == 20
