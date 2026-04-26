import io
import os
from pathlib import Path

from app.core.config import settings
from app.services.chat_service import prepare_chat_attachments


def test_prepare_chat_attachments_builds_context_and_image_payload(tmp_path: Path):
    image_path = tmp_path / "diagram.png"
    image_path.write_bytes(b"fake-image-bytes")
    text_path = tmp_path / "notes.txt"
    text_path.write_text("TCP slow start increases cwnd every RTT.", encoding="utf-8")

    attachments = prepare_chat_attachments([
        {
            "id": "img-1",
            "name": "diagram.png",
            "file_type": "image",
            "mime_type": "image/png",
            "file_path": str(image_path),
        },
        {
            "id": "doc-1",
            "name": "notes.txt",
            "file_type": "txt",
            "mime_type": "text/plain",
            "file_path": str(text_path),
        },
    ])

    assert attachments[0]["image_base64"]
    assert attachments[0]["data_url"].startswith("data:image/png;base64,")
    assert "Attachment: diagram.png" in attachments[0]["attachment_context"]
    assert "TCP slow start" in attachments[1]["attachment_context"]


def test_chat_attachment_upload_endpoint(client, student_headers):
    response = client.post(
        "/api/v1/chat/attachments/upload",
        headers=student_headers,
        files={"file": ("notes.txt", io.BytesIO(b"Temporary attachment content"), "text/plain")},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "notes.txt"
    assert data["file_type"] == "txt"
    assert data["temporary"] is True
    assert data["file_path"]
    assert data["expires_at"]


def test_chat_attachment_cleanup_endpoint(client, student_headers, monkeypatch):
    upload = client.post(
        "/api/v1/chat/attachments/upload",
        headers=student_headers,
        files={"file": ("old.txt", io.BytesIO(b"old temporary attachment"), "text/plain")},
    )
    assert upload.status_code == 200
    data = upload.json()["data"]
    old_timestamp = 1
    os.utime(data["file_path"], (old_timestamp, old_timestamp))
    monkeypatch.setattr(settings, "CHAT_ATTACHMENT_TTL_HOURS", 1)

    cleanup = client.post("/api/v1/chat/attachments/cleanup", headers=student_headers)

    assert cleanup.status_code == 200
    cleanup_data = cleanup.json()["data"]
    assert cleanup_data["deleted_count"] >= 1
    assert not Path(data["file_path"]).exists()


def test_chat_attachment_can_be_promoted_to_kb(client, teacher_headers):
    courses = client.get("/api/v1/courses", headers=teacher_headers).json()["data"]
    course_id = courses[0]["id"]
    upload = client.post(
        "/api/v1/chat/attachments/upload",
        headers=teacher_headers,
        data={"course_id": course_id},
        files={"file": ("promote.txt", io.BytesIO(b"Temporary attachment promoted to KB."), "text/plain")},
    )
    assert upload.status_code == 200
    attachment = upload.json()["data"]

    promote = client.post(
        "/api/v1/chat/attachments/promote",
        headers=teacher_headers,
        json={
            "course_id": course_id,
            "storage_key": attachment["storage_key"],
            "name": attachment["name"],
            "mime_type": attachment["mime_type"],
            "file_type": attachment["file_type"],
            "size": attachment["size"],
            "title": "Promoted Attachment",
        },
    )

    assert promote.status_code == 200
    data = promote.json()["data"]
    assert data["promoted_from_chat_attachment"] is True
    assert data["kb_status"] in {"indexed", "pending", "processing"}
