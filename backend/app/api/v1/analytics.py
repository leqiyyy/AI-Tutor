from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_student, get_current_teacher, get_current_user
from app.core.exceptions import ForbiddenException
from app.core.response import ok
from app.db.base import get_db
from app.models.chat import ChatMessage, ChatSession, ReviewItem
from app.models.course import Class, ClassMember, Submission, Task
from app.models.user import User
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/class/{class_id}/overview", response_model=None)
def class_overview(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    student_count = db.query(ClassMember).filter(
        ClassMember.class_id == class_id, ClassMember.role == "student"
    ).count()
    task_count = db.query(Task).filter(Task.class_id == class_id, Task.is_published == True).count()
    total_questions = db.query(ChatMessage).join(
        ChatSession, ChatMessage.session_id == ChatSession.id
    ).filter(
        ChatSession.class_id == class_id, ChatMessage.role == "user"
    ).count()
    pending_reviews = db.query(ReviewItem).filter(
        ReviewItem.class_id == class_id, ReviewItem.status == "pending"
    ).count()
    submission_count = db.query(Submission).join(
        Task, Submission.task_id == Task.id
    ).filter(Task.class_id == class_id).count()
    return ok(data={
        "class_id": class_id,
        "student_count": student_count,
        "task_count": task_count,
        "total_questions": total_questions,
        "pending_reviews": pending_reviews,
        "submission_count": submission_count,
        "avg_progress": 75,
    })


@router.get("/class/{class_id}/questions", response_model=None)
def class_questions(
    class_id: str,
    limit: int = Query(20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    msgs = db.query(ChatMessage).join(
        ChatSession, ChatMessage.session_id == ChatSession.id
    ).filter(
        ChatSession.class_id == class_id,
        ChatMessage.role == "user",
    ).order_by(ChatMessage.created_at.desc()).limit(limit).all()
    data = [{
        "id": m.id,
        "content": m.content,
        "created_at": m.created_at,
        "session_id": m.session_id,
    } for m in msgs]
    return ok(data=data)


@router.get("/student/{student_id}/progress", response_model=None)
def student_progress(
    student_id: str,
    class_id: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "student" and current_user.id != student_id:
        raise ForbiddenException("You cannot view another student's progress")
    q = db.query(ChatSession).filter(ChatSession.user_id == student_id)
    if class_id:
        q = q.filter(ChatSession.class_id == class_id)
    session_count = q.count()
    msg_count = db.query(ChatMessage).join(
        ChatSession, ChatMessage.session_id == ChatSession.id
    ).filter(
        ChatSession.user_id == student_id,
        ChatMessage.role == "user",
    ).count()
    return ok(data={
        "student_id": student_id,
        "class_id": class_id,
        "chat_sessions": session_count,
        "questions_asked": msg_count,
    })


@router.get("/courses/{course_id}", response_model=None)
def course_analytics_legacy(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    return ok(data=analytics_service.compute_course_analytics(db, course_id))


@router.get("/courses/{course_id}/analytics", response_model=None)
def course_analytics(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {"teacher", "admin", "student"}:
        raise ForbiddenException("You do not have access to this course analytics")
    return ok(data=analytics_service.compute_course_analytics(db, course_id))
