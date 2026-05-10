from typing import Union

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.error_codes import ErrorCode
from app.core.openapi_examples import responses_with_success
from app.core.response import ok
from app.db.base import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    ResetPasswordRequest,
    SendVerifyCodeRequest,
    StudentRegisterRequest,
    TeacherRegisterRequest,
)
from app.schemas.user import UserProfile
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/send-verify-code")
def send_verify_code(body: SendVerifyCodeRequest, db: Session = Depends(get_db)):
    auth_service.send_verify_code(db, body.email, body.purpose)
    return ok(message="Verification code sent")


@router.post("/register")
def register(
    body: Union[StudentRegisterRequest, TeacherRegisterRequest],
    db: Session = Depends(get_db),
):
    user = auth_service.register_user(db, body.model_dump())
    return ok(data={"user_id": user.id, "role": user.role}, message="Registration successful")


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    auth_service.reset_password(
        db,
        body.email,
        body.verify_code,
        body.password,
        body.confirm_password,
    )
    return ok(data={"status": "updated"}, message="Password reset successful")


@router.post(
    "/login",
    response_model=None,
    responses=responses_with_success(
        example_data={
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.demo",
            "token_type": "bearer",
            "role": "student",
            "user_id": "4ca8cecf-4f95-4cb8-9d13-a2c4fd905ca3",
            "real_name": "Alice",
        },
        include_errors=(
            ErrorCode.BAD_REQUEST.value,
            ErrorCode.UNAUTHORIZED.value,
            ErrorCode.VALIDATION_ERROR.value,
            ErrorCode.INTERNAL_ERROR.value,
        ),
    ),
)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    result = auth_service.login_user(db, body.account, body.password, body.role)
    return ok(data=result)


@router.get(
    "/me",
    response_model=None,
    responses=responses_with_success(
        example_data={
            "id": "4ca8cecf-4f95-4cb8-9d13-a2c4fd905ca3",
            "email": "student@example.com",
            "real_name": "Alice",
            "role": "student",
            "school": "Demo University",
            "college": "Computer Science",
            "major": "Software Engineering",
            "grade": "2023",
            "class_no": "SE-1",
            "student_id": "S2023001",
            "teacher_id": None,
            "phone": "13800000000",
        },
        include_errors=(
            ErrorCode.UNAUTHORIZED.value,
            ErrorCode.INTERNAL_ERROR.value,
        ),
    ),
)
def auth_me(current_user: User = Depends(get_current_user)):
    return ok(data=UserProfile.model_validate(current_user).model_dump())
