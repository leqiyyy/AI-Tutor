import io


def test_recommendations_endpoints(client, teacher_headers, student_headers):
    teacher_course = client.get("/api/v1/courses", headers=teacher_headers).json()["data"][0]
    course_id = teacher_course["id"]

    upload = client.post(
        f"/api/v1/courses/{course_id}/files/upload",
        headers=teacher_headers,
        files={"file": ("tcp-material.txt", io.BytesIO(b"TCP slow start recommendation material."), "text/plain")},
        data={"title": "TCP Recommendation Material", "description": "Slow start review material"},
    )
    assert upload.status_code == 200

    escalate = client.post(
        "/api/v1/reviews/escalate",
        headers=student_headers,
        json={
            "course_id": course_id,
            "question_content": "What is TCP slow start?",
            "ai_answer": "Unknown.",
            "reason": "Need recommendation signal",
        },
    )
    assert escalate.status_code == 200
    review_id = escalate.json()["data"]["review_id"]

    submit = client.post(
        f"/api/v1/reviews/{review_id}/submit",
        headers=teacher_headers,
        json={
            "teacher_answer": "TCP slow start rapidly grows the congestion window during the initial phase.",
            "add_to_kb": True,
        },
    )
    assert submit.status_code == 200

    materials = client.get(f"/api/v1/recommendations/materials?course_id={course_id}", headers=student_headers)
    learning_path = client.get(f"/api/v1/recommendations/learning-path?course_id={course_id}", headers=student_headers)

    assert materials.status_code == 200
    assert learning_path.status_code == 200
    materials_data = materials.json()["data"]
    path_data = learning_path.json()["data"]
    assert "items" in materials_data
    assert "teacher_verified_faq" in materials_data
    assert materials_data["context"]["algorithm"]["name"] == "explainable_weighted_rules"
    if materials_data["items"]:
        assert "score" in materials_data["items"][0]
        assert "evidence_signals" in materials_data["items"][0]
    assert "steps" in path_data
    assert path_data["steps"]

    feedback = client.post(
        "/api/v1/recommendations/feedback",
        headers=student_headers,
        json={
            "course_id": course_id,
            "recommendation_type": "material",
            "target_id": materials_data["items"][0]["material_id"] if materials_data["items"] else "fallback-id",
            "feedback": "helpful",
            "extra_data": {"reason": "useful for weak topic review"},
        },
    )
    assert feedback.status_code == 200
    feedback_data = feedback.json()["data"]
    assert feedback_data["feedback"] == "helpful"
    assert feedback_data["recommendation_type"] == "material"
