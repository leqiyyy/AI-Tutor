def test_flashcards_and_analytics_flow(client, teacher_headers, student_headers):
    flashcards = client.get("/api/v1/flashcards", headers=student_headers)
    assert flashcards.status_code == 200
    items = flashcards.json()["data"]
    assert len(items) >= 1

    flashcard_id = items[0]["id"]
    review = client.post(
        f"/api/v1/flashcards/{flashcard_id}/review",
        headers=student_headers,
        json={"response": "good"},
    )
    assert review.status_code == 200
    assert review.json()["data"]["review_count"] >= 1

    profile = client.get("/api/v1/students/me/profile", headers=student_headers)
    assert profile.status_code == 200
    assert "activity_score" in profile.json()["data"]

    course_id = client.get("/api/v1/courses", headers=teacher_headers).json()["data"][0]["id"]
    analytics = client.get(f"/api/v1/courses/{course_id}/analytics", headers=teacher_headers)
    assert analytics.status_code == 200
    data = analytics.json()["data"]
    assert "question_count" in data
    assert "task_completion_rate" in data
