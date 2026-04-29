import asyncio
import importlib.util
import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.database import SessionLocal
from app.models.course import Material
from app.models.knowledge import FileParseTask
from app.services import kb_service


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("raganything") is None,
    reason="Strict RAG-Anything indexing tests require the raganything package to be installed.",
)


def _admin_headers(client) -> dict:
    login = client.post("/api/v1/auth/login", json={
        "account": "admin@aitutor.local",
        "password": "Admin123!",
        "role": "admin",
    })
    assert login.status_code == 200
    token = login.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_temp_class(client, teacher_headers, course_id: str) -> str:
    marker = uuid.uuid4().hex[:8]
    payload = {
        "course_id": course_id,
        "name": f"Queue Test Class {marker}",
        "semester": "2026 Spring",
        "announcement": "for kb queue integration tests",
    }
    response = client.post("/api/v1/classes", headers=teacher_headers, json=payload)
    assert response.status_code == 200
    return response.json()["data"]["id"]


def _mark_task_failed(
    parse_task_id: str,
    *,
    seconds_ago: int,
    attempt_count: int = 1,
    max_attempts: int = 5,
) -> None:
    failed_at = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    with SessionLocal() as db:
        task = db.query(FileParseTask).filter(FileParseTask.id == parse_task_id).first()
        assert task is not None
        material = db.query(Material).filter(Material.id == task.material_id).first()

        task.status = "failed"
        task.error_message = "simulated_queue_failure"
        extra = dict(task.extra_data or {})
        ingest = dict(extra.get("ingest", {}))
        ingest.update({
            "attempt_count": attempt_count,
            "max_attempts": max_attempts,
            "retry_available": True,
            "last_error_category": "upstream",
            "history": [
                {
                    "type": "queue_submitted",
                    "at": (failed_at - timedelta(seconds=2)).isoformat(),
                },
                {
                    "type": "attempt_start",
                    "attempt": attempt_count,
                    "at": (failed_at - timedelta(seconds=1)).isoformat(),
                },
                {
                    "type": "attempt_done",
                    "attempt": attempt_count,
                    "status": "failed",
                    "at": failed_at.isoformat(),
                },
            ],
        })
        extra["ingest"] = ingest
        task.extra_data = extra
        db.add(task)

        if material:
            material.kb_status = "failed"
            material.kb_error = "simulated_queue_failure"
            db.add(material)
        db.commit()


def _admin_kb_failure_alerts(client, admin_headers: dict, parse_task_id: str) -> list[dict]:
    response = client.get("/api/v1/notifications", headers=admin_headers)
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    return [
        item
        for item in items
        if (item.get("meta") or {}).get("alert_kind") == "kb_index_failure_limit"
        and (item.get("meta") or {}).get("task_id") == parse_task_id
    ]


def test_kb_upload_idempotent_and_task_retry(client, teacher_headers):
    course_id = client.get("/api/v1/courses", headers=teacher_headers).json()["data"][0]["id"]
    marker = uuid.uuid4().hex
    filename = f"congestion_notes_{marker[:8]}.txt"
    file_bytes = f"Congestion avoidance grows cwnd linearly after slow start. {marker}".encode("utf-8")

    upload1 = client.post(
        f"/api/v1/courses/{course_id}/files/upload",
        headers=teacher_headers,
        files={"file": (filename, io.BytesIO(file_bytes), "text/plain")},
        data={"title": "Congestion Notes"},
    )
    assert upload1.status_code == 200
    payload1 = upload1.json()["data"]
    assert payload1["deduplicated"] is False
    assert payload1["parse_task_id"]
    file_id = payload1["id"]
    parse_task_id = payload1["parse_task_id"]

    upload2 = client.post(
        f"/api/v1/courses/{course_id}/files/upload",
        headers=teacher_headers,
        files={"file": (filename, io.BytesIO(file_bytes), "text/plain")},
        data={"title": "Congestion Notes Duplicate"},
    )
    assert upload2.status_code == 200
    payload2 = upload2.json()["data"]
    assert payload2["deduplicated"] is True
    assert payload2["id"] == file_id
    assert payload2["parse_task_id"] == parse_task_id

    task_list = client.get(
        f"/api/v1/courses/{course_id}/kb/tasks",
        headers=teacher_headers,
    )
    assert task_list.status_code == 200
    items = task_list.json()["data"]["items"]
    assert any(item["id"] == parse_task_id for item in items)

    retry = client.post(
        f"/api/v1/courses/{course_id}/files/{file_id}/kb/retry?force=true",
        headers=teacher_headers,
    )
    assert retry.status_code == 200
    retry_task = retry.json()["data"]["task"]
    assert retry_task["id"] == parse_task_id
    assert retry_task["attempt_count"] >= 2


def test_admin_index_tasks_endpoint(client, teacher_headers):
    admin_headers = _admin_headers(client)
    course_id = client.get("/api/v1/courses", headers=teacher_headers).json()["data"][0]["id"]

    response = client.get(
        f"/api/v1/admin/index-tasks?course_id={course_id}",
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "items" in data
    assert "total" in data


def test_kb_async_enqueue_and_async_retry(client, teacher_headers):
    course_id = client.get("/api/v1/courses", headers=teacher_headers).json()["data"][0]["id"]
    marker = uuid.uuid4().hex
    content = f"Queue-based indexing test content {marker}.".encode()
    filename = f"async_queue_notes_{marker[:8]}.txt"

    upload = client.post(
        f"/api/v1/courses/{course_id}/files/upload?async_index=true",
        headers=teacher_headers,
        files={"file": (filename, io.BytesIO(content), "text/plain")},
        data={"title": "Async Queue Notes"},
    )
    assert upload.status_code == 200
    upload_data = upload.json()["data"]
    assert upload_data["action"] == "queued"
    assert upload_data["parse_task_id"]
    assert upload_data["queue_task_id"]

    task_detail = client.get(f"/api/v1/tasks/{upload_data['parse_task_id']}", headers=teacher_headers)
    assert task_detail.status_code == 200
    task_payload = task_detail.json()["data"]
    assert task_payload["id"] == upload_data["parse_task_id"]
    assert task_payload.get("queue_task_id")

    retry = client.post(
        f"/api/v1/courses/{course_id}/files/{upload_data['id']}/kb/retry?force=true&async_retry=true",
        headers=teacher_headers,
    )
    assert retry.status_code == 200
    retry_data = retry.json()["data"]
    assert retry_data["action"] == "queued_reindex"
    assert retry_data["queue_task_id"]


def test_admin_can_query_index_queue_status(client, teacher_headers):
    admin_headers = _admin_headers(client)
    course_id = client.get("/api/v1/courses", headers=teacher_headers).json()["data"][0]["id"]
    marker = uuid.uuid4().hex
    content = f"Queue status query content {marker}.".encode()

    upload = client.post(
        f"/api/v1/courses/{course_id}/files/upload?async_index=true",
        headers=teacher_headers,
        files={"file": (f"queue_status_{marker[:8]}.txt", io.BytesIO(content), "text/plain")},
        data={"title": "Queue Status Notes"},
    )
    assert upload.status_code == 200
    queue_task_id = upload.json()["data"]["queue_task_id"]
    assert queue_task_id

    queue_status = client.get(
        f"/api/v1/admin/index-queue/{queue_task_id}",
        headers=admin_headers,
    )
    assert queue_status.status_code == 200
    payload = queue_status.json()["data"]
    assert payload["queue_task_id"] == queue_task_id
    assert "queue_status" in payload


def test_admin_batch_retry_failed_tasks_with_cooldown(client, teacher_headers):
    admin_headers = _admin_headers(client)
    course_id = client.get("/api/v1/courses", headers=teacher_headers).json()["data"][0]["id"]
    class_id = _create_temp_class(client, teacher_headers, course_id)

    marker = uuid.uuid4().hex
    upload_hot = client.post(
        f"/api/v1/courses/{course_id}/files/upload?async_index=true",
        headers=teacher_headers,
        files={"file": (f"cooldown_hot_{marker[:6]}.txt", io.BytesIO(b"hot"), "text/plain")},
        data={"title": "Hot Cooldown", "class_id": class_id},
    )
    assert upload_hot.status_code == 200
    hot_task_id = upload_hot.json()["data"]["parse_task_id"]

    upload_ready = client.post(
        f"/api/v1/courses/{course_id}/files/upload?async_index=true",
        headers=teacher_headers,
        files={"file": (f"cooldown_ready_{marker[:6]}.txt", io.BytesIO(b"ready"), "text/plain")},
        data={"title": "Ready Cooldown", "class_id": class_id},
    )
    assert upload_ready.status_code == 200
    ready_task_id = upload_ready.json()["data"]["parse_task_id"]

    _mark_task_failed(hot_task_id, seconds_ago=1)
    _mark_task_failed(ready_task_id, seconds_ago=90)

    retry_response = client.post(
        f"/api/v1/admin/index-tasks/retry-failed?course_id={course_id}&class_id={class_id}&limit=10",
        headers=admin_headers,
    )
    assert retry_response.status_code == 200
    payload = retry_response.json()["data"]
    assert payload["queued_count"] >= 1
    assert any(item["task_id"] == ready_task_id for item in payload["queued"])
    assert any(
        item["task_id"] == hot_task_id and item["reason"] == "cooldown_active"
        for item in payload["skipped"]
    )


def test_admin_index_queue_metrics_endpoint(client, teacher_headers):
    admin_headers = _admin_headers(client)
    course_id = client.get("/api/v1/courses", headers=teacher_headers).json()["data"][0]["id"]
    class_id = _create_temp_class(client, teacher_headers, course_id)
    marker = uuid.uuid4().hex

    upload = client.post(
        f"/api/v1/courses/{course_id}/files/upload?async_index=true",
        headers=teacher_headers,
        files={"file": (f"queue_metrics_{marker[:6]}.txt", io.BytesIO(b"metrics"), "text/plain")},
        data={"title": "Metrics Queue", "class_id": class_id},
    )
    assert upload.status_code == 200
    parse_task_id = upload.json()["data"]["parse_task_id"]
    _mark_task_failed(parse_task_id, seconds_ago=120, attempt_count=2, max_attempts=5)

    metrics = client.get(
        f"/api/v1/admin/index-queue-metrics?course_id={course_id}&class_id={class_id}",
        headers=admin_headers,
    )
    assert metrics.status_code == 200
    payload = metrics.json()["data"]
    assert payload["filters"]["class_id"] == class_id
    assert "totals" in payload
    assert "queue" in payload
    assert "retry" in payload
    assert "latency_ms" in payload
    assert payload["retry"]["tasks_with_retry"] >= 1
    assert payload["latency_ms"]["execution"]["samples"] >= 1


def test_process_parse_task_auto_retry_schedules_queue(client, teacher_headers):
    course_id = client.get("/api/v1/courses", headers=teacher_headers).json()["data"][0]["id"]
    class_id = _create_temp_class(client, teacher_headers, course_id)
    marker = uuid.uuid4().hex

    upload = client.post(
        f"/api/v1/courses/{course_id}/files/upload?async_index=true",
        headers=teacher_headers,
        files={"file": (f"auto_retry_{marker[:6]}.txt", io.BytesIO(b"auto retry"), "text/plain")},
        data={"title": "Auto Retry Queue", "class_id": class_id},
    )
    assert upload.status_code == 200
    parse_task_id = upload.json()["data"]["parse_task_id"]

    with SessionLocal() as db:
        task = db.query(FileParseTask).filter(FileParseTask.id == parse_task_id).first()
        assert task is not None
        material = db.query(Material).filter(Material.id == task.material_id).first()
        assert material is not None
        material.file_path = "E:/not_exists/definitely_missing_file.txt"
        db.add(material)
        db.commit()

    result = asyncio.run(kb_service.process_parse_task_by_id(parse_task_id, force=False))
    assert result["parse_task_id"] == parse_task_id
    assert result["auto_retry"] is not None
    assert result["auto_retry"]["scheduled"] is True
    assert result["status"] == "pending"

    with SessionLocal() as db:
        task = db.query(FileParseTask).filter(FileParseTask.id == parse_task_id).first()
        assert task is not None
        ingest = (task.extra_data or {}).get("ingest", {})
        assert int(ingest.get("auto_retry_round", 0) or 0) >= 1
        assert ingest.get("next_retry_after")


def test_kb_failure_limit_emits_admin_alert_without_duplicates(client, teacher_headers):
    admin_headers = _admin_headers(client)
    course_id = client.get("/api/v1/courses", headers=teacher_headers).json()["data"][0]["id"]
    class_id = _create_temp_class(client, teacher_headers, course_id)
    marker = uuid.uuid4().hex

    upload = client.post(
        f"/api/v1/courses/{course_id}/files/upload?async_index=true",
        headers=teacher_headers,
        files={"file": (f"failure_alert_{marker[:8]}.txt", io.BytesIO(b"alert test"), "text/plain")},
        data={"title": "Failure Alert File", "class_id": class_id},
    )
    assert upload.status_code == 200
    file_id = upload.json()["data"]["id"]
    parse_task_id = upload.json()["data"]["parse_task_id"]

    with SessionLocal() as db:
        task = db.query(FileParseTask).filter(FileParseTask.id == parse_task_id).first()
        assert task is not None
        material = db.query(Material).filter(Material.id == task.material_id).first()
        assert material is not None
        material.file_path = "E:/not_exists/index_failure_limit_alert.txt"
        db.add(material)
        db.commit()

    retry_sync = client.post(
        f"/api/v1/courses/{course_id}/files/{file_id}/kb/retry?force=true",
        headers=teacher_headers,
    )
    assert retry_sync.status_code == 200
    assert retry_sync.json()["data"]["action"] == "failed"

    alerts_first = _admin_kb_failure_alerts(client, admin_headers, parse_task_id)
    assert len(alerts_first) >= 1
    first_meta = alerts_first[0]["meta"]
    assert first_meta["reason"] == "max_attempts_reached"
    assert first_meta["task_id"] == parse_task_id
    assert first_meta["class_id"] == class_id

    batch_retry = client.post(
        f"/api/v1/admin/index-tasks/retry-failed?course_id={course_id}&class_id={class_id}&limit=10",
        headers=admin_headers,
    )
    assert batch_retry.status_code == 200

    alerts_second = _admin_kb_failure_alerts(client, admin_headers, parse_task_id)
    assert len(alerts_second) == len(alerts_first)

    task_list = client.get(
        f"/api/v1/admin/index-tasks?course_id={course_id}&class_id={class_id}&status=failed",
        headers=admin_headers,
    )
    assert task_list.status_code == 200
    matched = [
        item
        for item in task_list.json()["data"]["items"]
        if item["id"] == parse_task_id
    ]
    assert matched
    assert matched[0]["alert_count"] >= 1
    assert matched[0]["last_alert_reason"] in {"max_attempts_reached", "auto_retry_exhausted"}


def test_material_analysis_content_items_schema_v1(client, teacher_headers):
    course_id = client.get("/api/v1/courses", headers=teacher_headers).json()["data"][0]["id"]
    marker = uuid.uuid4().hex
    content = f"Schema v1 test content {marker}".encode("utf-8")

    upload = client.post(
        f"/api/v1/courses/{course_id}/files/upload",
        headers=teacher_headers,
        files={"file": (f"schema_v1_{marker[:8]}.txt", io.BytesIO(content), "text/plain")},
        data={"title": "Schema V1 Notes"},
    )
    assert upload.status_code == 200
    file_id = upload.json()["data"]["id"]

    analysis = client.get(
        f"/api/v1/courses/{course_id}/files/{file_id}/analysis",
        headers=teacher_headers,
    )
    assert analysis.status_code == 200
    payload = analysis.json()["data"]
    assert payload["content_items_schema"] == "v1"
    assert isinstance(payload["content_items"], list)
    assert payload["content_items"]
    item = payload["content_items"][0]
    assert "item_id" in item
    assert "modality" in item
    assert "text" in item
    assert "source_name" in item
    assert "meta" in item


def test_content_items_multimodal_mapping_v1():
    raw_items = [
        {
            "id": "tbl-1",
            "type": "table",
            "content": "table rows",
            "table_html": "<table><tr><td>1</td></tr></table>",
            "metadata": {
                "source_name": "chapter1.pdf",
                "source_type": "pdf",
                "page_idx": 3,
                "bbox": {"left": 10, "top": 20, "width": 110, "height": 50},
            },
        },
        {
            "id": "eq-1",
            "type": "equation",
            "equation": "E=mc^2",
            "metadata": {
                "source_name": "chapter1.pdf",
                "page_number": 5,
                "bounding_box": [1, 2, 3, 4],
            },
        },
        {
            "id": "img-1",
            "type": "figure",
            "metadata": {
                "source_name": "slides.pptx",
                "page": 7,
                "image_url": "https://example.local/diagram.png",
                "ocr_text": "Throughput vs RTT",
                "layout_type": "diagram",
            },
        },
    ]
    normalized = kb_service._normalize_content_items(raw_items, material_id="m-test")
    assert len(normalized) == 3

    table_item = normalized[0]
    assert table_item["modality"] == "table"
    assert table_item["table_html"]
    assert table_item["page"] == 3
    assert table_item["bbox"] == [10.0, 20.0, 120.0, 70.0]

    formula_item = normalized[1]
    assert formula_item["modality"] == "formula"
    assert formula_item["formula_latex"] == "E=mc^2"
    assert formula_item["bbox"] == [1.0, 2.0, 3.0, 4.0]
    assert formula_item["page"] == 5

    image_item = normalized[2]
    assert image_item["modality"] == "image"
    assert image_item["image_path"] == "https://example.local/diagram.png"
    assert image_item["ocr_text"] == "Throughput vs RTT"
    assert image_item["layout_type"] == "diagram"


def test_graph_provenance_updates_on_incremental_ingest(client, teacher_headers):
    course_id = client.get("/api/v1/courses", headers=teacher_headers).json()["data"][0]["id"]
    marker = uuid.uuid4().hex[:8]
    token = f"qosalpha{marker}"
    payload1 = f"{token} appears in the first file with congestion notes.".encode("utf-8")
    payload2 = f"{token} appears again in the second file with queue notes.".encode("utf-8")

    upload1 = client.post(
        f"/api/v1/courses/{course_id}/files/upload",
        headers=teacher_headers,
        files={"file": (f"graph_inc_1_{marker}.txt", io.BytesIO(payload1), "text/plain")},
        data={"title": "Graph Increment 1"},
    )
    assert upload1.status_code == 200
    file_id_1 = upload1.json()["data"]["id"]

    upload2 = client.post(
        f"/api/v1/courses/{course_id}/files/upload",
        headers=teacher_headers,
        files={"file": (f"graph_inc_2_{marker}.txt", io.BytesIO(payload2), "text/plain")},
        data={"title": "Graph Increment 2"},
    )
    assert upload2.status_code == 200
    file_id_2 = upload2.json()["data"]["id"]

    graph = client.get(
        f"/api/v1/courses/{course_id}/graph",
        headers=teacher_headers,
    )
    assert graph.status_code == 200
    graph_data = graph.json()["data"]

    matched_nodes = [
        node
        for node in graph_data.get("nodes", [])
        if node.get("label") == token
    ]
    assert matched_nodes, f"Expected entity token {token} in graph nodes"
    node = matched_nodes[0]
    provenance = node.get("provenance") or {}
    source_material_ids = provenance.get("source_material_ids") or []
    assert file_id_1 in source_material_ids
    assert file_id_2 in source_material_ids
    assert float(node.get("confidence") or 0.0) > 0.0

    if graph_data.get("edges"):
        edge = graph_data["edges"][0]
        assert "confidence" in edge
        assert "provenance" in edge
