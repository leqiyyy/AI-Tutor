from io import StringIO
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_student
from app.core.response import ok
from app.db.base import get_db
from app.models.user import User
from pydantic import BaseModel

from app.services import analytics_service, mistake_service

router = APIRouter(prefix="/students", tags=["students"])


class MistakeCreateRequest(BaseModel):
    class_id: Optional[str] = None
    chapter: Optional[str] = None
    question: str
    my_answer: Optional[str] = None
    correct_answer: Optional[str] = None
    analysis: Optional[str] = None


@router.get("/me/profile", response_model=None)
def my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    return ok(data=analytics_service.build_student_profile(db, current_user))


@router.get("/me/reports/weekly", response_model=None)
def weekly_report(
    course_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    return ok(data=analytics_service.build_student_report(db, current_user, "weekly", course_id))


@router.get("/me/reports/monthly", response_model=None)
def monthly_report(
    course_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    return ok(data=analytics_service.build_student_report(db, current_user, "monthly", course_id))


@router.get("/me/export")
def export_reports(
    format: str = Query("csv"),
    course_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    if format != "csv":
        return ok(data=analytics_service.build_student_report(db, current_user, "monthly", course_id))

    csv_content = analytics_service.export_student_report_csv(db, current_user, course_id)
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=student_report.csv"},
    )


@router.get("/me/mistakes", response_model=None)
def list_mistakes(
    class_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    return ok(data=mistake_service.list_mistakes(db, current_user, class_id))


@router.post("/me/mistakes", response_model=None)
def create_mistake(
    body: MistakeCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    mistake = mistake_service.create_mistake(
        db,
        current_user,
        question=body.question,
        chapter=body.chapter,
        my_answer=body.my_answer,
        correct_answer=body.correct_answer,
        analysis=body.analysis,
        class_id=body.class_id,
    )
    return ok(data={"id": mistake.id, "question": mistake.question}, message="Mistake added")


@router.put("/me/mistakes/{mistake_id}/mastered", response_model=None)
def mark_mastered(
    mistake_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    mistake = mistake_service.mark_mastered(db, current_user, mistake_id, mastered=True)
    return ok(data={"id": mistake.id, "mastered": bool(mistake.mastered)})


@router.post("/me/mistakes/{mistake_id}/practice", response_model=None)
def practice_mistake(
    mistake_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    mistake = mistake_service.practice_mistake(db, current_user, mistake_id)
    return ok(data={"id": mistake.id, "wrong_count": mistake.wrong_count})
