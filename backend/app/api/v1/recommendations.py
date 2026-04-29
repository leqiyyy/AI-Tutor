from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_student, require_role
from app.core.exceptions import BadRequestException
from app.core.response import ok
from app.db.base import get_db
from app.models.user import User
from app.services import (
    analytics_service,
    learning_graph_service,
    learning_path_service,
    recommendation_service,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


class RecommendationFeedbackRequest(BaseModel):
    recommendation_type: str
    target_id: str
    feedback: str
    course_id: Optional[str] = None
    class_id: Optional[str] = None
    extra_data: Optional[dict[str, Any]] = None


class RecommendationEventRequest(BaseModel):
    recommendation_type: str
    target_id: str
    event_type: str
    class_id: Optional[str] = None
    score: Optional[float] = None
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


@router.get("/materials-v2", response_model=None)
def material_recommendations_v2(
    class_id: str = Query(...),
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    data = recommendation_service.rank_learning_resources_for_student(
        db,
        user_id=current_user.id,
        class_id=class_id,
        limit=limit,
    )
    return ok(data={
        "items": data,
        "context": {
            "class_id": class_id,
            "algorithm": "explainable_weighted_rules_v2",
        },
    })


@router.get("/learning-path-v2", response_model=None)
def learning_path_recommendations_v2(
    class_id: str = Query(...),
    max_steps: int = Query(7, ge=1, le=20),
    persist: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    data = learning_path_service.generate_learning_path_for_student(
        db,
        user_id=current_user.id,
        class_id=class_id,
        max_steps=max_steps,
        persist=persist,
    )
    if persist:
        db.commit()
    return ok(data=data)


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


@router.post("/events", response_model=None)
def recommendation_event(
    body: RecommendationEventRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    event = recommendation_service.record_recommendation_event(
        db,
        user_id=current_user.id,
        class_id=body.class_id,
        recommendation_type=body.recommendation_type,
        target_id=body.target_id,
        event_type=body.event_type,
        score=body.score,
        extra_data=body.extra_data,
    )
    db.commit()
    return ok(data={
        "id": event.id,
        "recommendation_type": event.recommendation_type,
        "target_id": event.target_id,
        "event_type": event.event_type,
        "class_id": event.class_id,
        "created_at": event.created_at,
    }, message="Recommendation event recorded")


@router.post("/learning-graph/rebuild", response_model=None)
def rebuild_learning_graph(
    class_id: str = Query(...),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("teacher", "admin")),
):
    data = learning_graph_service.rebuild_learning_graph_projection(db, class_id=class_id)
    db.commit()
    return ok(data=data, message="Learning graph projection rebuilt")
