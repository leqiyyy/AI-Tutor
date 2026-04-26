import base64
import importlib.util
import io
import json
import uuid
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("raganything") is None,
    reason="Strict multimodal RAG-Anything regression tests require the raganything package to be installed.",
)


def _fixture_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "multimodal"


def _load_fixture_manifest() -> list[dict]:
    manifest_path = _fixture_dir() / "fixture_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return payload.get("fixtures", [])


def _fixture_bytes(entry: dict) -> bytes:
    if entry.get("content_file"):
        return (_fixture_dir() / entry["content_file"]).read_bytes()
    encoding = (entry.get("encoding") or "").lower()
    if encoding == "base64":
        return base64.b64decode(entry.get("content_base64", ""))
    if encoding == "utf-8":
        return str(entry.get("content", "")).encode("utf-8")
    raise ValueError(f"Unsupported fixture encoding for {entry.get('id')}")


def _create_temp_class(client, teacher_headers, course_id: str) -> str:
    marker = uuid.uuid4().hex[:8]
    payload = {
        "course_id": course_id,
        "name": f"MM Regression {marker}",
        "semester": "2026 Spring",
        "announcement": "multimodal regression sandbox",
    }
    response = client.post("/api/v1/classes", headers=teacher_headers, json=payload)
    assert response.status_code == 200
    return response.json()["data"]["id"]


def test_multimodal_regression_fixtures_upload_analysis_graph(client, teacher_headers):
    course_id = client.get("/api/v1/courses", headers=teacher_headers).json()["data"][0]["id"]
    class_id = _create_temp_class(client, teacher_headers, course_id)
    fixtures = _load_fixture_manifest()
    assert fixtures, "fixture_manifest.json should not be empty"

    uploaded_material_ids: list[str] = []
    observed_modalities: set[str] = set()

    for entry in fixtures:
        file_bytes = _fixture_bytes(entry)
        upload = client.post(
            f"/api/v1/courses/{course_id}/files/upload",
            headers=teacher_headers,
            files={"file": (entry["file_name"], io.BytesIO(file_bytes), entry["mime_type"])},
            data={"title": f"Fixture {entry['id']}", "class_id": class_id},
        )
        assert upload.status_code == 200
        upload_data = upload.json()["data"]
        assert upload_data["action"] in {"indexed", "reindexed", "already_indexed"}
        material_id = upload_data["id"]
        uploaded_material_ids.append(material_id)

        analysis = client.get(
            f"/api/v1/courses/{course_id}/files/{material_id}/analysis",
            headers=teacher_headers,
        )
        assert analysis.status_code == 200
        analysis_data = analysis.json()["data"]
        assert analysis_data["content_items_schema"] == "v1"
        assert "raganything_quality" in analysis_data

        item_modalities = {
            str(item.get("modality", "")).lower()
            for item in analysis_data.get("content_items", [])
        }
        observed_modalities.update(item_modalities)

        expected_modalities = {
            str(modality).lower()
            for modality in entry.get("expected_modalities", [])
        }
        assert expected_modalities.issubset(item_modalities), (
            f"Fixture {entry['id']} missing expected modalities. "
            f"expected={expected_modalities}, actual={item_modalities}"
        )

    assert {"text", "table", "formula", "image"}.issubset(observed_modalities)

    graph = client.get(f"/api/v1/courses/{course_id}/graph", headers=teacher_headers)
    assert graph.status_code == 200
    graph_data = graph.json()["data"]
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    assert nodes
    assert "summary" in graph_data
    assert "legend" in graph_data
    assert "materials" in graph_data
    assert graph_data["summary"]["source_material_count"] >= 1

    assert any(
        set((node.get("provenance") or {}).get("source_material_ids") or []).intersection(uploaded_material_ids)
        for node in nodes
    )

    node = nodes[0]
    assert "confidence" in node
    assert "source_span" in node
    assert "provenance" in node
    if edges:
        edge = edges[0]
        assert "confidence" in edge
        assert "source_span" in edge
        assert "provenance" in edge
