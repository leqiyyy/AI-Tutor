from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_student
from app.core.exceptions import BadRequestException
from app.core.response import ok
from app.db.base import get_db
from app.models.user import User
from app.services import analytics_service

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


class RecommendationFeedbackRequest(BaseModel):
    recommendation_type: str
    target_id: str
    feedback: str
    course_id: Optional[str] = None
    class_id: Optional[str] = None
    extra_data: Optional[dict[str, Any]] = None


@router.get("/materials", response_model=None)
def material_recommendations(
    course_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    return ok(data=analytics_service.get_material_recommendations(db, current_user, course_id))


@router.get("/learning-path", response_model=None)
def learning_path_recommendations(
    course_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    return ok(data=analytics_service.build_learning_path_recommendation(db, current_user, course_id))


@router.post("/feedback", response_model=None)
def recommendation_feedback(
    body: RecommendationFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    try:
        data = analytics_service.record_recommendation_feedback(
            db,
            current_user,
            recommendation_type=body.recommendation_type,
            target_id=body.target_id,
            feedback=body.feedback,
            course_id=body.course_id,
            class_id=body.class_id,
            extra_data=body.extra_data,
        )
    except ValueError as exc:
        raise BadRequestException(str(exc)) from exc
    return ok(data=data, message="Recommendation feedback recorded")
