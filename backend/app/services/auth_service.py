import random
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthException, BadRequestException
from app.core.logging import get_logger
from app.core.security import create_token, hash_password, verify_password
from app.models.notification import VerifyCode
from app.models.user import User
from app.services import audit_service, email_service

log = get_logger(__name__)


def send_verify_code(db: Session, email: str, purpose: str = "register") -> str:
    email = _normalize_email(email)
    _validate_verify_code_purpose(purpose)
    existing_user = db.query(User).filter(func.lower(User.email) == email.lower()).first()
    if purpose == "register" and existing_user:
        raise BadRequestException("邮箱已注册")
    if purpose == "reset_password" and not existing_user:
        log.info("reset_password_code_requested_for_unknown_email", email=email)
        return ""

    _enforce_verify_code_rate_limit(db, email, purpose)
    code = "".join(random.choices(string.digits, k=6))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.VERIFY_CODE_EXPIRE_MINUTES)
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
    email_service.send_verify_code_email(
        to_email=email,
        code=code,
        purpose=purpose,
        expires_minutes=settings.VERIFY_CODE_EXPIRE_MINUTES,
    )
    return code


def _check_verify_code(db: Session, email: str, code: str, purpose: str) -> None:
    email = _normalize_email(email)
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
    email = _normalize_email(data["email"])
    _validate_password_strength(data["password"])
    if db.query(User).filter(func.lower(User.email) == email.lower()).first():
        raise BadRequestException("邮箱已注册")
    if role == "student" and db.query(User).filter(User.student_id == data.get("student_id")).first():
        raise BadRequestException("学号已注册")
    if role == "teacher" and db.query(User).filter(User.teacher_id == data.get("teacher_id")).first():
        raise BadRequestException("工号已注册")
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
    account = account.strip()
    now = datetime.now(timezone.utc)
    user = db.query(User).filter(
        User.is_active == True,
        or_(
            func.lower(User.email) == account.lower(),
            User.student_id == account,
            User.teacher_id == account,
        ),
    ).first()
    if user and _is_locked(user, now):
        raise AuthException("登录失败次数过多，请稍后再试")
    if not user or not verify_password(password, user.hashed_password):
        if user:
            _record_failed_login(db, user, now)
            audit_service.record_event(
                event_type="auth.login_failed",
                status="failed",
                actor=user,
                target_type="user",
                target_id=user.id,
                summary="账号密码登录失败",
                extra_data={"account": account},
            )
        raise AuthException("Invalid account or password")
    if role and user.role != role:
        raise AuthException(f"Account role mismatch: expected {role}")
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    db.add(user)
    db.commit()
    audit_service.record_event(
        event_type="auth.user_login",
        actor=user,
        target_type="user",
        target_id=user.id,
        summary=f"{user.real_name or user.email} 登录系统",
        extra_data={"role": user.role},
    )
    token = create_token({"sub": user.id, "role": user.role})
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "user_id": user.id,
        "real_name": user.real_name,
    }


def reset_password(db: Session, email: str, verify_code: str, password: str, confirm_password: str) -> None:
    email = _normalize_email(email)
    if password != confirm_password:
        raise BadRequestException("两次输入的新密码不一致")
    _validate_password_strength(password)
    user = db.query(User).filter(func.lower(User.email) == email.lower(), User.is_active == True).first()
    if not user:
        raise BadRequestException("Invalid verification code")
    _check_verify_code(db, email, verify_code, "reset_password")
    user.hashed_password = hash_password(password)
    user.failed_login_count = 0
    user.locked_until = None
    db.add(user)
    db.commit()
    audit_service.record_event(
        event_type="auth.password_reset",
        actor=user,
        target_type="user",
        target_id=user.id,
        summary=f"{user.real_name or user.email} 重置密码",
        extra_data={"email": user.email},
    )


def change_password(
    db: Session,
    user: User,
    old_password: str,
    new_password: str,
    confirm_password: str,
) -> None:
    if not verify_password(old_password, user.hashed_password):
        raise AuthException("旧密码不正确")
    if new_password != confirm_password:
        raise BadRequestException("两次输入的新密码不一致")
    _validate_password_strength(new_password)
    if verify_password(new_password, user.hashed_password):
        raise BadRequestException("新密码不能与旧密码相同")
    user.hashed_password = hash_password(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    db.add(user)
    db.commit()
    audit_service.record_event(
        event_type="auth.password_changed",
        actor=user,
        target_type="user",
        target_id=user.id,
        summary=f"{user.real_name or user.email} 修改密码",
        extra_data={"role": user.role},
    )


def _validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise BadRequestException("密码不少于8位")
    if not any(ch.isalpha() for ch in password) or not any(ch.isdigit() for ch in password):
        raise BadRequestException("密码需包含字母和数字")


def _record_failed_login(db: Session, user: User, now: datetime) -> None:
    next_count = int(user.failed_login_count or 0) + 1
    user.failed_login_count = next_count
    if next_count >= settings.AUTH_LOGIN_FAILURE_LIMIT:
        user.locked_until = now + timedelta(seconds=settings.AUTH_LOGIN_LOCK_SECONDS)
    db.add(user)
    db.commit()


def _is_locked(user: User, now: datetime) -> bool:
    if not user.locked_until:
        return False
    locked_until = _ensure_aware(user.locked_until)
    return locked_until > now


def _enforce_verify_code_rate_limit(db: Session, email: str, purpose: str) -> None:
    now = datetime.now(timezone.utc)
    latest = db.query(VerifyCode).filter(
        VerifyCode.email == email,
        VerifyCode.purpose == purpose,
    ).order_by(VerifyCode.created_at.desc()).first()
    if latest and (_ensure_aware(latest.created_at) + timedelta(seconds=settings.VERIFY_CODE_COOLDOWN_SECONDS)) > now:
        raise BadRequestException("验证码发送过于频繁，请稍后再试")
    daily_count = db.query(VerifyCode).filter(
        VerifyCode.email == email,
        VerifyCode.purpose == purpose,
        VerifyCode.created_at >= now - timedelta(days=1),
    ).count()
    if daily_count >= settings.VERIFY_CODE_DAILY_LIMIT:
        raise BadRequestException("今日验证码发送次数已达上限，请明天再试")


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _validate_verify_code_purpose(purpose: str) -> None:
    if purpose not in {"register", "reset_password"}:
        raise BadRequestException("不支持的验证码用途")


def _role_label(role: str) -> str:
    return {"student": "学生", "teacher": "教师", "admin": "管理员"}.get(role, role)
