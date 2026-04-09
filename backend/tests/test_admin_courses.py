def test_admin_course_list(client):
    login = client.post("/api/v1/auth/login", json={
        "account": "admin@aitutor.local",
        "password": "Admin123!",
        "role": "admin",
    })
    headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    courses = client.get("/api/v1/admin/courses", headers=headers)
    assert courses.status_code == 200
    assert "items" in courses.json()["data"]
