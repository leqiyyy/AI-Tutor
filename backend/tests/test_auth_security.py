from uuid import uuid4

from app.core.database import SessionLocal
from app.models.notification import VerifyCode
from app.models.user import User
from app.services import email_service


def _latest_code(email: str, purpose: str) -> str:
    db = SessionLocal()
    try:
        row = db.query(VerifyCode).filter(
            VerifyCode.email == email,
            VerifyCode.purpose == purpose,
        ).order_by(VerifyCode.created_at.desc()).first()
        assert row is not None
        return row.code
    finally:
        db.close()


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}@example.com"


def test_register_with_email_code_and_duplicate_student_id(client, monkeypatch):
    monkeypatch.setattr(email_service, "send_verify_code_email", lambda **_: None)
    email = _unique_email("student")
    student_id = f"S{uuid4().hex[:8]}"

    send_response = client.post("/api/v1/auth/send-verify-code", json={
        "email": email,
        "purpose": "register",
    })
    assert send_response.status_code == 200

    code = _latest_code(email, "register")
    register_response = client.post("/api/v1/auth/register", json={
        "role": "student",
        "realName": "测试学生",
        "studentId": student_id,
        "email": email,
        "phone": "13900000001",
        "school": "测试大学",
        "college": "计算机学院",
        "major": "软件工程",
        "grade": "2026级",
        "classNo": "1班",
        "password": "Student123!",
        "confirmPassword": "Student123!",
        "verifyCode": code,
    })
    assert register_response.status_code == 200

    login_response = client.post("/api/v1/auth/login", json={
        "account": email,
        "password": "Student123!",
        "role": "student",
    })
    assert login_response.status_code == 200
    assert login_response.json()["data"]["access_token"]

    other_email = _unique_email("student")
    client.post("/api/v1/auth/send-verify-code", json={
        "email": other_email,
        "purpose": "register",
    })
    duplicate_response = client.post("/api/v1/auth/register", json={
        "role": "student",
        "realName": "重复学号",
        "studentId": student_id,
        "email": other_email,
        "password": "Student123!",
        "confirmPassword": "Student123!",
        "verifyCode": _latest_code(other_email, "register"),
    })
    assert duplicate_response.status_code == 400


def test_reset_password_and_change_password(client, monkeypatch):
    monkeypatch.setattr(email_service, "send_verify_code_email", lambda **_: None)
    email = _unique_email("reset")
    teacher_id = f"T{uuid4().hex[:8]}"

    client.post("/api/v1/auth/send-verify-code", json={"email": email, "purpose": "register"})
    register_response = client.post("/api/v1/auth/register", json={
        "role": "teacher",
        "realName": "测试教师",
        "teacherId": teacher_id,
        "email": email,
        "phone": "13900000002",
        "school": "测试大学",
        "college": "计算机学院",
        "department": "网络工程系",
        "title": "讲师",
        "password": "Teacher123!",
        "confirmPassword": "Teacher123!",
        "verifyCode": _latest_code(email, "register"),
    })
    assert register_response.status_code == 200

    reset_code_response = client.post("/api/v1/auth/send-verify-code", json={
        "email": email,
        "purpose": "reset_password",
    })
    assert reset_code_response.status_code == 200
    reset_response = client.post("/api/v1/auth/reset-password", json={
        "email": email,
        "verifyCode": _latest_code(email, "reset_password"),
        "password": "Teacher456!",
        "confirmPassword": "Teacher456!",
    })
    assert reset_response.status_code == 200

    login_response = client.post("/api/v1/auth/login", json={
        "account": email,
        "password": "Teacher456!",
        "role": "teacher",
    })
    assert login_response.status_code == 200
    token = login_response.json()["data"]["access_token"]

    change_response = client.post(
        "/api/v1/settings/password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "oldPassword": "Teacher456!",
            "newPassword": "Teacher789!",
            "confirmPassword": "Teacher789!",
        },
    )
    assert change_response.status_code == 200

    relogin_response = client.post("/api/v1/auth/login", json={
        "account": email,
        "password": "Teacher789!",
        "role": "teacher",
    })
    assert relogin_response.status_code == 200


def test_login_failure_locks_account(client, monkeypatch):
    monkeypatch.setattr(email_service, "send_verify_code_email", lambda **_: None)
    email = _unique_email("lock")
    client.post("/api/v1/auth/send-verify-code", json={"email": email, "purpose": "register"})
    client.post("/api/v1/auth/register", json={
        "role": "student",
        "realName": "锁定测试",
        "studentId": f"S{uuid4().hex[:8]}",
        "email": email,
        "password": "Student123!",
        "confirmPassword": "Student123!",
        "verifyCode": _latest_code(email, "register"),
    })

    for _ in range(5):
        response = client.post("/api/v1/auth/login", json={
            "account": email,
            "password": "Wrong123!",
            "role": "student",
        })
        assert response.status_code == 401

    locked_response = client.post("/api/v1/auth/login", json={
        "account": email,
        "password": "Student123!",
        "role": "student",
    })
    assert locked_response.status_code == 401

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        assert user.locked_until is not None
    finally:
        db.close()
