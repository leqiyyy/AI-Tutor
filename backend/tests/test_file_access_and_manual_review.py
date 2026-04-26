import io


def test_file_access_and_manual_review(client, teacher_headers, student_headers):
    course = client.get("/api/v1/courses", headers=teacher_headers).json()["data"][0]
    course_id = course["id"]

    upload = client.post(
        f"/api/v1/courses/{course_id}/files/upload",
        headers=teacher_headers,
        files={"file": ("subnet_notes.txt", io.BytesIO(b"CIDR /24 equals 255.255.255.0"), "text/plain")},
        data={"title": "Subnet Notes"},
    )
    assert upload.status_code == 200
    file_id = upload.json()["data"]["id"]

    preview = client.get(f"/api/v1/courses/{course_id}/files/{file_id}/preview", headers=student_headers)
    analysis = client.get(f"/api/v1/courses/{course_id}/files/{file_id}/analysis", headers=student_headers)
    transcript = client.get(f"/api/v1/courses/{course_id}/files/{file_id}/transcript", headers=student_headers)
    search = client.get(f"/api/v1/courses/{course_id}/search?q=CIDR", headers=student_headers)
    download = client.get(f"/api/v1/courses/{course_id}/files/{file_id}/download", headers=student_headers)

    assert preview.status_code == 200
    assert analysis.status_code == 200
    assert transcript.status_code == 200
    assert search.status_code == 200
    assert download.status_code == 200
    assert analysis.json()["data"]["chunk_count"] >= 1
    assert transcript.json()["data"]["transcript_available"] is True
    assert "CIDR" in transcript.json()["data"]["segments"][0]["text"]
    assert search.json()["data"]

    escalate = client.post("/api/v1/reviews/escalate", headers=student_headers, json={
        "course_id": course_id,
        "question_content": "Please help me understand CIDR",
        "ai_answer": "Current answer is not enough",
        "reason": "Need teacher explanation",
    })
    assert escalate.status_code == 200
    assert escalate.json()["data"]["status"] == "pending"

    pending = client.get(f"/api/v1/reviews/pending?course_id={course_id}", headers=teacher_headers)
    assert pending.status_code == 200
    review_item = next(
        item for item in pending.json()["data"]
        if item["question_content"] == "Please help me understand CIDR"
    )
    assert review_item["review_context"]["review_priority"] == "high"
    assert review_item["quality"]["grounding_level"] == "ungrounded"


def test_multimodal_result_endpoints_for_image_material(client, teacher_headers, student_headers):
    course = client.get("/api/v1/courses", headers=teacher_headers).json()["data"][0]
    course_id = course["id"]

    upload = client.post(
        f"/api/v1/courses/{course_id}/files/upload",
        headers=teacher_headers,
        files={"file": ("diagram.png", io.BytesIO(b"fake-image"), "image/png")},
        data={"title": "Diagram"},
    )
    assert upload.status_code == 200
    file_id = upload.json()["data"]["id"]

    keyframes = client.get(f"/api/v1/courses/{course_id}/files/{file_id}/keyframes", headers=student_headers)
    ocr = client.get(f"/api/v1/courses/{course_id}/files/{file_id}/ocr", headers=student_headers)

    assert keyframes.status_code == 200
    assert ocr.status_code == 200
    assert "frames" in keyframes.json()["data"]
    assert "blocks" in ocr.json()["data"]
