import io


def test_kb_chat_review_flow(client, teacher_headers, student_headers):
    courses = client.get("/api/v1/courses", headers=teacher_headers).json()["data"]
    course_id = courses[0]["id"]

    upload = client.post(
        f"/api/v1/courses/{course_id}/files/upload",
        headers=teacher_headers,
        files={"file": ("tcp_notes.txt", io.BytesIO(b"TCP slow start increases cwnd quickly."), "text/plain")},
        data={"title": "TCP Notes"},
    )
    assert upload.status_code == 200
    parse_task_id = upload.json()["data"]["parse_task_id"]

    kb_status = client.get(f"/api/v1/courses/{course_id}/kb/status", headers=teacher_headers)
    graph = client.get(f"/api/v1/courses/{course_id}/graph", headers=teacher_headers)
    parse_task = client.get(f"/api/v1/tasks/{parse_task_id}", headers=teacher_headers)

    assert kb_status.status_code == 200
    assert graph.status_code == 200
    assert parse_task.status_code == 200
    assert parse_task.json()["data"]["kind"] == "file_parse"

    query = client.post(
        "/api/v1/chat/query",
        headers=student_headers,
        json={"course_id": course_id, "message": "What is slow start in TCP?"},
    )
    assert query.status_code == 200
    query_data = query.json()["data"]
    assert query_data["sources"]

    low_conf = client.post(
        "/api/v1/chat/query",
        headers=student_headers,
        json={"course_id": course_id, "message": "??"},
    )
    assert low_conf.status_code == 200
    assert low_conf.json()["data"]["needs_review"] is True

    pending = client.get(f"/api/v1/reviews/pending?course_id={course_id}", headers=teacher_headers)
    assert pending.status_code == 200
    assert len(pending.json()["data"]) >= 1
