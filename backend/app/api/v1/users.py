from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserProfile, UpdateProfileRequest
from app.core.response import ok
from app.core.exceptions import BadRequestException

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=None)
def get_me(current_user: User = Depends(get_current_user)):
    return ok(data=UserProfile.model_validate(current_user).model_dump())


@router.put("/me", response_model=None)
def update_me(
    body: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    for field, value in body.model_dump(exclude_none=True).items():
        if hasattr(current_user, field):
            setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return ok(data=UserProfile.model_validate(current_user).model_dump())


@router.get("/me/learning-stats", response_model=None)
def get_learning_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.chat import ChatMessage, ChatSession
    from app.models.course import Submission, ClassMember
    session_count = db.query(ChatSession).filter(ChatSession.user_id == current_user.id).count()
    msg_count = db.query(ChatMessage).join(
        ChatSession, ChatMessage.session_id == ChatSession.id
    ).filter(ChatSession.user_id == current_user.id, ChatMessage.role == "user").count()
    class_count = db.query(ClassMember).filter(
        ClassMember.user_id == current_user.id,
        ClassMember.role == "student",
    ).count()
    submission_count = db.query(Submission).filter(Submission.student_id == current_user.id).count()
    return ok(data={
        "chat_sessions": session_count,
        "questions_asked": msg_count,
        "courses_joined": class_count,
        "submissions": submission_count,
    })
