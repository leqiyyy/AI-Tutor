def test_auth_and_courses_flow(client, teacher_headers, student_headers):
    teacher_me = client.get("/api/v1/auth/me", headers=teacher_headers)
    student_me = client.get("/api/v1/auth/me", headers=student_headers)

    assert teacher_me.status_code == 200
    assert student_me.status_code == 200
    assert teacher_me.json()["data"]["role"] == "teacher"
    assert student_me.json()["data"]["role"] == "student"

    teacher_courses = client.get("/api/v1/courses", headers=teacher_headers)
    student_courses = client.get("/api/v1/courses", headers=student_headers)

    assert teacher_courses.status_code == 200
    assert student_courses.status_code == 200
    assert len(teacher_courses.json()["data"]) >= 1
    assert len(student_courses.json()["data"]) >= 1

    course_id = teacher_courses.json()["data"][0]["id"]
    class_id = teacher_courses.json()["data"][0]["class_id"]

    course_detail = client.get(f"/api/v1/courses/{course_id}", headers=teacher_headers)
    class_detail = client.get(f"/api/v1/classes/{class_id}", headers=teacher_headers)

    assert course_detail.status_code == 200
    assert class_detail.status_code == 200
    assert course_detail.json()["data"]["id"] == course_id
    assert class_detail.json()["data"]["id"] == class_id
