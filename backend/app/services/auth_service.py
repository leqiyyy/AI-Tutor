import random
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthException, BadRequestException
from app.core.logging import get_logger
from app.core.security import create_token, hash_password, verify_password
from app.models.notification import VerifyCode
from app.models.user import User
from app.services import audit_service

log = get_logger(__name__)


def send_verify_code(db: Session, email: str, purpose: str = "register") -> str:
    code = "".join(random.choices(string.digits, k=6))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.query(VerifyCode).filter(
        VerifyCode.email == email,
        VerifyCode.purpose == purpose,
        VerifyCode.is_used == False,
    ).update({"is_used": True})
    vc = VerifyCode(email=email, code=code, purpose=purpose, expires_at=expires_at)
    db.add(vc)
    db.commit()
    if settings.EMAIL_DEV_MODE:
        log.info("verify_code_dev", email=email, code=code, purpose=purpose)
    else:
        log.warning("email_sending_not_configured", email=email)
    return code


def _check_verify_code(db: Session, email: str, code: str, purpose: str) -> None:
    vc = db.query(VerifyCode).filter(
        VerifyCode.email == email,
        VerifyCode.code == code,
        VerifyCode.purpose == purpose,
        VerifyCode.is_used == False,
    ).order_by(VerifyCode.created_at.desc()).first()
    if not vc:
        raise BadRequestException("Invalid verification code")
    if datetime.now(timezone.utc) > vc.expires_at.replace(tzinfo=timezone.utc):
        raise BadRequestException("Verification code expired")
    vc.is_used = True
    db.commit()


def register_user(db: Session, data: dict) -> User:
    role = data["role"]
    email = data["email"]
    if db.query(User).filter(User.email == email).first():
        raise BadRequestException("Email already registered")
    _check_verify_code(db, email, data["verify_code"], "register")
    user = User(
        email=email,
        hashed_password=hash_password(data["password"]),
        real_name=data["real_name"],
        role=role,
        phone=data.get("phone"),
        school=data.get("school"),
    )
    if role == "student":
        user.student_id = data.get("student_id")
        user.college = data.get("college")
        user.major = data.get("major")
        user.grade = data.get("grade")
        user.class_no = data.get("class_no")
    elif role == "teacher":
        user.teacher_id = data.get("teacher_id")
        user.college = data.get("college")
        user.department = data.get("department")
        user.title = data.get("title")
    db.add(user)
    db.commit()
    db.refresh(user)
    audit_service.record_event(
        event_type="auth.user_registered",
        actor=user,
        target_type="user",
        target_id=user.id,
        summary=f"{user.real_name or user.email} 注册为{_role_label(user.role)}",
        extra_data={"email": user.email, "role": user.role},
    )
    return user


def login_user(db: Session, account: str, password: str, role: Optional[str] = None) -> dict:
    user = db.query(User).filter(
        User.is_active == True,
        or_(
            User.email == account,
            User.student_id == account,
            User.teacher_id == account,
        ),
    ).first()
    if not user or not verify_password(password, user.hashed_password):
        raise AuthException("Invalid account or password")
    if role and user.role != role:
        raise AuthException(f"Account role mismatch: expected {role}")
    token = create_token({"sub": user.id, "role": user.role})
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "user_id": user.id,
        "real_name": user.real_name,
    }


def _role_label(role: str) -> str:
    return {"student": "学生", "teacher": "教师", "admin": "管理员"}.get(role, role)
