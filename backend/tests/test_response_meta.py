def test_success_response_contains_request_meta(client):
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert "meta" in payload
    assert payload["meta"]["request_id"] == response.headers.get("X-Request-ID")
    assert payload["meta"]["trace_id"] == response.headers.get("X-Trace-ID")
    assert payload["meta"]["version"]


def test_error_response_contains_request_meta(client):
    response = client.get("/api/v1/courses")
    assert response.status_code == 401
    payload = response.json()
    assert "meta" in payload
    assert payload["meta"]["request_id"] == response.headers.get("X-Request-ID")
    assert payload["meta"]["trace_id"] == response.headers.get("X-Trace-ID")
    assert payload["meta"]["version"]
    assert payload["error"]["key"] == "auth_required"


def test_trace_id_can_be_propagated_from_request_header(client):
    response = client.get("/health", headers={"X-Trace-ID": "trace_from_client"})
    assert response.status_code == 200
    payload = response.json()
    assert response.headers.get("X-Trace-ID") == "trace_from_client"
    assert payload["meta"]["trace_id"] == "trace_from_client"
