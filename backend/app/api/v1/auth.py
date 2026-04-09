from typing import Union

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.response import ok
from app.db.base import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
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


@router.post("/login", response_model=None)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    result = auth_service.login_user(db, body.account, body.password, body.role)
    return ok(data=result)


@router.get("/me", response_model=None)
def auth_me(current_user: User = Depends(get_current_user)):
    return ok(data=UserProfile.model_validate(current_user).model_dump())
