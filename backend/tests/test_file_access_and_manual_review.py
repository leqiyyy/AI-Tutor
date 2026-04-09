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
    search = client.get(f"/api/v1/courses/{course_id}/search?q=CIDR", headers=student_headers)
    download = client.get(f"/api/v1/courses/{course_id}/files/{file_id}/download", headers=student_headers)

    assert preview.status_code == 200
    assert analysis.status_code == 200
    assert search.status_code == 200
    assert download.status_code == 200
    assert analysis.json()["data"]["chunk_count"] >= 1
    assert search.json()["data"]

    escalate = client.post("/api/v1/reviews/escalate", headers=student_headers, json={
        "course_id": course_id,
        "question_content": "Please help me understand CIDR",
        "ai_answer": "Current answer is not enough",
        "reason": "Need teacher explanation",
    })
    assert escalate.status_code == 200
    assert escalate.json()["data"]["status"] == "pending"
