import io
import os
from pathlib import Path

from app.core.config import settings
from app.ai.base import LLMMessage
from app.services.chat_service import (
    _build_chat_completion_messages,
    _build_direct_attachment_context,
    _build_responses_input_items,
    chat_attachment_scope_id,
    prepare_chat_attachments,
)


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


def test_quick_mode_responses_payload_sends_image_directly():
    messages = [
        LLMMessage(role="system", content="system"),
        LLMMessage(role="user", content="请解读图片"),
    ]
    attachments = [{"file_type": "image", "mime_type": "image/png", "image_base64": "abcd"}]

    input_items = _build_responses_input_items(messages=messages, attachments=attachments)

    user_content = input_items[-1]["content"]
    assert {"type": "input_image", "image_url": "data:image/png;base64,abcd"} in user_content


def test_quick_mode_chat_completion_payload_sends_image_directly():
    messages = [
        LLMMessage(role="system", content="system"),
        LLMMessage(role="user", content="请解读图片"),
    ]
    attachments = [{"file_type": "image", "data_url": "data:image/jpeg;base64,xyz"}]

    chat_messages = _build_chat_completion_messages(messages=messages, attachments=attachments)

    user_content = chat_messages[-1]["content"]
    assert {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,xyz"}} in user_content


def test_quick_mode_attachment_context_does_not_run_vlm_for_images():
    context = _build_direct_attachment_context([
        {"file_type": "image", "name": "diagram.png", "image_base64": "abcd", "mime_type": "image/png"}
    ])

    assert "原图已作为多模态输入直接发送" in context


def test_prepare_chat_attachments_resolves_storage_key_for_current_user(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    user_id = "student-attachment-user"
    storage_key = "notes.txt"
    scope_dir = settings.LOCAL_STORAGE_ROOT / chat_attachment_scope_id(user_id)
    scope_dir.mkdir(parents=True, exist_ok=True)
    (scope_dir / storage_key).write_text("Temporary TCP notes from chat upload.", encoding="utf-8")

    attachments = prepare_chat_attachments([
        {
            "id": storage_key,
            "storage_key": storage_key,
            "name": "notes.txt",
            "file_type": "txt",
            "mime_type": "text/plain",
        }
    ], user_id=user_id)

    assert attachments[0]["file_path"] == str(scope_dir / storage_key)
    assert "Temporary TCP notes" in attachments[0]["attachment_context"]


def test_prepare_chat_attachments_rejects_unsafe_storage_key(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))

    attachments = prepare_chat_attachments([
        {
            "id": "../notes.txt",
            "storage_key": "../notes.txt",
            "name": "notes.txt",
            "file_type": "txt",
            "mime_type": "text/plain",
        }
    ], user_id="student-attachment-user")

    assert "file_path" not in attachments[0]
    assert "no longer available" in attachments[0]["attachment_context"]


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
