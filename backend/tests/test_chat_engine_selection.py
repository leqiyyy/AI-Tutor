from app.ai.base import RAGResult
from app.services import admin_service, chat_service


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


def test_chat_query_uses_persisted_rag_engine(monkeypatch, client):
    student_headers = _login(client, "student@aitutor.local", "Student123!", "student")
    class_id = _resolve_student_class_id(client, student_headers)
    captured = {}

    class DummyRag:
        async def query(self, question, class_id, history=None, attachments=None, role="student"):
            _ = (question, class_id, history, attachments, role)
            return RAGResult(
                answer="dummy",
                sources=[],
                confidence=0.8,
                suggestions=[],
                meta={"engine": "simple", "used_fallback": False},
            )

    def fake_get_rag_engine(requested_engine=None):
        captured["requested_engine"] = requested_engine
        return DummyRag()

    monkeypatch.setattr(chat_service, "get_rag_engine", fake_get_rag_engine)
    monkeypatch.setattr(
        admin_service,
        "get_model_config",
        lambda db: {"rag_engine": "raganything"},
    )

    response = client.post(
        "/api/v1/chat/query",
        headers=student_headers,
        json={
            "class_id": class_id,
            "message": "test routing selection",
            "attachments": [],
        },
    )
    assert response.status_code == 200
    assert captured.get("requested_engine") == "raganything"
