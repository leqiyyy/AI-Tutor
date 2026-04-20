def test_teacher_notifications_and_student_reports(client, teacher_headers, student_headers):
    teacher_course = client.get("/api/v1/courses", headers=teacher_headers).json()["data"][0]
    class_id = teacher_course["class_id"]
    course_id = teacher_course["id"]

    publish = client.post("/api/v1/notifications", headers=teacher_headers, json={
        "class_id": class_id,
        "title": "Homework reminder",
        "content": "Please complete Week 1 homework.",
        "type": "deadline",
        "scope": "students",
    })
    assert publish.status_code == 200
    assert publish.json()["data"]["recipient_count"] >= 1

    notifications = client.get("/api/v1/notifications", headers=student_headers)
    assert notifications.status_code == 200
    assert len(notifications.json()["data"]["items"]) >= 1

    weekly = client.get(f"/api/v1/students/me/reports/weekly?course_id={course_id}", headers=student_headers)
    monthly = client.get(f"/api/v1/students/me/reports/monthly?course_id={course_id}", headers=student_headers)
    exported = client.get(f"/api/v1/students/me/export?format=csv&course_id={course_id}", headers=student_headers)

    assert weekly.status_code == 200
    assert monthly.status_code == 200
    assert exported.status_code == 200
    assert "summary" in weekly.json()["data"]
    assert "experiment_context" in weekly.json()["data"]
    assert "model_routing" in weekly.json()["data"]["experiment_context"]
    assert "recommendation_context" in weekly.json()["data"]["highlights"]
    assert exported.headers["content-type"].startswith("text/csv")

    mistake = client.post("/api/v1/students/me/mistakes", headers=student_headers, json={
        "chapter": "Transport Layer",
        "question": "What is TCP slow start?",
        "my_answer": "Not sure",
        "correct_answer": "Initial congestion control phase",
        "analysis": "Review congestion window growth",
    })
    assert mistake.status_code == 200
    mistake_id = mistake.json()["data"]["id"]

    mistakes = client.get("/api/v1/students/me/mistakes", headers=student_headers)
    mastered = client.put(f"/api/v1/students/me/mistakes/{mistake_id}/mastered", headers=student_headers)
    practiced = client.post(f"/api/v1/students/me/mistakes/{mistake_id}/practice", headers=student_headers)

    assert mistakes.status_code == 200
    assert mastered.status_code == 200
    assert practiced.status_code == 200
