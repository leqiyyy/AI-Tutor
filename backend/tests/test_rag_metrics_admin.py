def _login(client, account: str, password: str, role: str) -> dict:
    response = client.post("/api/v1/auth/login", json={
        "account": account,
        "password": password,
        "role": role,
    })
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _resolve_student_class_id(client, student_headers: dict) -> str:
    courses = client.get("/api/v1/courses", headers=student_headers)
    assert courses.status_code == 200
    rows = courses.json().get("data") or []
    if rows and rows[0].get("class_id"):
        return rows[0]["class_id"]

    classes = client.get("/api/v1/classes", headers=student_headers)
    assert classes.status_code == 200
    class_rows = classes.json().get("data") or []
    assert class_rows
    return class_rows[0]["id"]


def test_admin_rag_performance_metrics(client):
    student_headers = _login(client, "student@aitutor.local", "Student123!", "student")
    admin_headers = _login(client, "admin@aitutor.local", "Admin123!", "admin")
    class_id = _resolve_student_class_id(client, student_headers)

    query = client.post(
        "/api/v1/chat/query",
        headers=student_headers,
        json={
            "class_id": class_id,
            "message": "Explain TCP slow start with one short example.",
            "attachments": [],
        },
    )
    assert query.status_code == 200

    perf = client.get("/api/v1/admin/rag-performance", headers=admin_headers)
    assert perf.status_code == 200
    payload = perf.json()["data"]
    assert payload["window_days"] == 7
    assert payload["totals"]["queries"] >= 1
    assert "success_rate" in payload["rates"]
    assert "fallback_rate" in payload["rates"]
    assert "query_mode" in payload["distributions"]
    assert "retrieval_strategy" in payload["distributions"]
    assert "reranker" in payload["distributions"]
    assert "query_rewrite_mode" in payload["distributions"]
    assert "query_variant_bucket" in payload["distributions"]
    assert "llm_backend" in payload["distributions"]
    assert "embedding_backend" in payload["distributions"]
    assert "vlm_backend" in payload["distributions"]
    assert "reranker_backend" in payload["distributions"]

    ablation = client.get("/api/v1/admin/rag-ablation", headers=admin_headers)
    assert ablation.status_code == 200
    ablation_payload = ablation.json()["data"]
    assert "groups" in ablation_payload
    assert "rewrite_enabled" in ablation_payload["groups"]
    assert "rewrite_mode" in ablation_payload["groups"]
    assert "query_variant_bucket" in ablation_payload["groups"]

    personalization = client.get(
        "/api/v1/admin/personalization-routing-metrics",
        headers=admin_headers,
        params={"days": 14, "class_id": class_id, "top_n": 5},
    )
    assert personalization.status_code == 200
    p_payload = personalization.json()["data"]
    assert p_payload["window_days"] == 14
    assert p_payload["filters"]["class_id"] == class_id
    assert p_payload["filters"]["top_n"] == 5
    assert "summary" in p_payload
    assert "slices" in p_payload
    if p_payload["slices"]:
        first_slice = p_payload["slices"][0]
        assert "routing_slice_key" in first_slice
        assert "llm_backend" in first_slice
        assert "embedding_backend" in first_slice
        assert "vlm_backend" in first_slice
        assert "reranker_backend" in first_slice
        assert "avg_activity_score" in first_slice
        assert "avg_task_completion_rate" in first_slice
        assert "learning_events_per_user" in first_slice
