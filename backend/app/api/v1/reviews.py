from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_student, get_current_teacher
from app.core.response import ok
from app.db.base import get_db
from app.integrations.rag.quality import build_evidence_quality, build_review_context
from app.models.chat import ChatMessage, ChatSession, ReviewItem
from app.models.course import Class
from app.models.user import User
from app.schemas.chat import ResolveReviewRequest
from app.services import chat_service

router = APIRouter(prefix="/reviews", tags=["reviews"])


class ManualEscalationRequest(BaseModel):
    course_id: Optional[str] = None
    class_id: Optional[str] = None
    question_content: str
    ai_answer: str
    reason: Optional[str] = None


@router.get("/pending", response_model=None)
def pending_reviews(
    course_id: Optional[str] = Query(None),
    class_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    teacher_class_ids = [cls.id for cls in db.query(Class).filter(Class.teacher_id == current_user.id, Class.is_active == True).all()]
    query = db.query(ReviewItem).filter(ReviewItem.class_id.in_(teacher_class_ids), ReviewItem.status == "pending")
    if class_id:
        query = query.filter(ReviewItem.class_id == class_id)
    if course_id:
        course_class_ids = [cls.id for cls in db.query(Class).filter(Class.course_id == course_id).all()]
        query = query.filter(ReviewItem.class_id.in_(course_class_ids))

    items = query.order_by(ReviewItem.created_at.desc()).all()
    data = []
    for item in items:
        student = db.query(User).filter(User.id == item.student_id).first()
        message = item.message
        sources = (message.sources if message else []) or []
        confidence = message.confidence if message else 0.0
        data.append({
            "id": item.id,
            "message_id": item.message_id,
            "class_id": item.class_id,
            "student_id": item.student_id,
            "student_name": student.real_name if student else "",
            "trigger": item.trigger,
            "question_content": item.question_content,
            "ai_answer": item.ai_answer,
            "teacher_answer": item.teacher_answer,
            "status": item.status,
            "quality": build_evidence_quality(sources, confidence),
            "review_context": build_review_context(
                sources,
                confidence,
                trigger=item.trigger,
                feedback=message.feedback if message else None,
            ),
            "created_at": item.created_at,
        })
    return ok(data=data)


@router.post("/{review_id}/submit", response_model=None)
async def submit_review(
    review_id: str,
    body: ResolveReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    result = await chat_service.resolve_review(
        db,
        review_id,
        current_user.id,
        body.teacher_answer,
        body.add_to_kb,
    )
    return ok(data=result, message="Review submitted")


@router.post("/escalate", response_model=None)
def escalate_review(
    body: ManualEscalationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    if not body.class_id:
        if not body.course_id:
            from app.core.exceptions import BadRequestException

            raise BadRequestException("course_id or class_id is required")
        classes = db.query(Class).filter(Class.course_id == body.course_id, Class.is_active == True).all()
        class_ids = [cls.id for cls in classes]
        memberships = db.query(__import__("app.models.course", fromlist=["ClassMember"]).ClassMember).filter(
            __import__("app.models.course", fromlist=["ClassMember"]).ClassMember.user_id == current_user.id,
            __import__("app.models.course", fromlist=["ClassMember"]).ClassMember.class_id.in_(class_ids),
        ).all()
        if not memberships:
            from app.core.exceptions import ForbiddenException

            raise ForbiddenException("You do not have access to the requested course")
        class_id = memberships[0].class_id
    else:
        class_id = body.class_id

    session = ChatSession(class_id=class_id, user_id=current_user.id, title=body.question_content[:50])
    db.add(session)
    db.flush()
    message = ChatMessage(
        session_id=session.id,
        role="ai",
        content=body.ai_answer,
        needs_review=True,
    )
    db.add(message)
    db.flush()

    review = ReviewItem(
        message_id=message.id,
        class_id=class_id,
        student_id=current_user.id,
        trigger="manual",
        question_content=body.question_content,
        ai_answer=body.ai_answer + (f"\n\nStudent note: {body.reason}" if body.reason else ""),
        status="pending",
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return ok(data={"review_id": review.id, "status": review.status}, message="Manual review requested")
