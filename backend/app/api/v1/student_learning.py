from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_student
from app.core.response import ok
from app.db.base import get_db
from app.models.user import User
from app.services import student_learning_service


router = APIRouter(prefix="/student/courses/{course_id}/learning", tags=["student-learning"])


class LearningEventRequest(BaseModel):
    activity_type: str
    ref_id: Optional[str] = None
    duration_seconds: Optional[int] = None
    extra_data: Optional[dict[str, Any]] = None


class LearningMistakeRequest(BaseModel):
    question: str
    chapter: Optional[str] = None
    myAnswer: Optional[str] = None
    correctAnswer: Optional[str] = None
    analysis: Optional[str] = None


class FlashcardDeckRequest(BaseModel):
    name: str
    cards: list[dict[str, str]]


class FlashcardReviewRequest(BaseModel):
    deckId: str | int
    cardIndex: int = 0
    difficulty: str = "good"


@router.get("/overview", response_model=None)
def learning_overview(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    return ok(data=student_learning_service.build_learning_overview(db, current_user, course_id))


@router.get("/report", response_model=None)
def learning_report(
    course_id: str,
    period: str = Query("weekly", pattern="^(weekly|monthly)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    return ok(data=student_learning_service.build_learning_report(db, current_user, course_id, period))


@router.post("/events", response_model=None)
def record_learning_event(
    course_id: str,
    body: LearningEventRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    data = student_learning_service.record_learning_event(
        db,
        current_user,
        course_id,
        activity_type=body.activity_type,
        ref_id=body.ref_id,
        duration_seconds=body.duration_seconds,
        extra_data=body.extra_data,
    )
    return ok(data=data)


@router.get("/export")
def export_learning_report(
    course_id: str,
    period: str = Query("weekly", pattern="^(weekly|monthly)$"),
    format: str = Query("csv"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    if format != "csv":
        return ok(data=student_learning_service.build_learning_report(db, current_user, course_id, period))
    csv_content = student_learning_service.export_learning_report_csv(db, current_user, course_id, period)
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=learning_{period}_report.csv"},
    )


@router.post("/export")
def export_learning_report_post(
    course_id: str,
    body: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    period = str(body.get("period") or "weekly")
    if period not in {"weekly", "monthly"}:
        period = "weekly"
    fmt = str(body.get("format") or "csv")
    if fmt != "csv":
        return ok(data=student_learning_service.build_learning_report(db, current_user, course_id, period))
    csv_content = student_learning_service.export_learning_report_csv(db, current_user, course_id, period)
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=learning_{period}_report.csv"},
    )


@router.get("/mistakes", response_model=None)
def learning_mistakes(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    return ok(data=student_learning_service.list_learning_mistakes(db, current_user, course_id))


@router.post("/mistakes", response_model=None)
def create_learning_mistake(
    course_id: str,
    body: LearningMistakeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    return ok(data=student_learning_service.create_learning_mistake(db, current_user, course_id, body.model_dump()))


@router.post("/mistakes/{mistake_id}/mastered", response_model=None)
def mark_learning_mistake_mastered(
    course_id: str,
    mistake_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    return ok(data=student_learning_service.mark_learning_mistake_mastered(db, current_user, mistake_id))


@router.get("/flashcards", response_model=None)
def learning_flashcards(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    return ok(data=student_learning_service.list_learning_flashcard_decks(db, current_user, course_id))


@router.post("/flashcards/decks", response_model=None)
def create_learning_flashcard_deck(
    course_id: str,
    body: FlashcardDeckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    return ok(data=student_learning_service.create_learning_flashcard_deck(db, current_user, course_id, body.model_dump()))


@router.post("/flashcards/reviews", response_model=None)
def review_learning_flashcard(
    course_id: str,
    body: FlashcardReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    return ok(data=student_learning_service.review_learning_flashcard(db, current_user, course_id, body.model_dump()))
