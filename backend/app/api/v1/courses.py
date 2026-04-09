from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_teacher, get_current_user
from app.core.response import ok
from app.db.base import get_db
from app.models.user import User
from app.schemas.course import CreateCourseRequest
from app.services import analytics_service, course_service, kb_service

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", response_model=None)
def list_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ok(data=course_service.list_courses_for_user(db, current_user))


@router.get("/{course_id}", response_model=None)
def get_course(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ok(data=course_service.get_course_detail_for_user(db, course_id, current_user))


@router.get("/{course_id}/analytics", response_model=None)
def get_course_analytics(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kb_service.ensure_course_access(db, course_id, current_user)
    return ok(data=analytics_service.compute_course_analytics(db, course_id))


@router.post("", response_model=None)
def create_course(
    body: CreateCourseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    course = course_service.create_course(db, current_user.id, body.model_dump())
    return ok(
        data={
            "id": course.id,
            "name": course.name,
            "code": course.code,
            "created_at": course.created_at,
        },
        message="Course created",
    )
