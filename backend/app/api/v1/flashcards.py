from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.response import ok
from app.db.base import get_db
from app.models.user import User
from app.services import flashcard_service

router = APIRouter(prefix="/flashcards", tags=["flashcards"])


class FlashcardReviewRequest(BaseModel):
    rating: Optional[int] = None
    response: Optional[str] = None


@router.get("", response_model=None)
def list_flashcards(
    course_id: Optional[str] = Query(None),
    class_id: Optional[str] = Query(None),
    due_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ok(data=flashcard_service.list_flashcards(db, current_user, course_id, class_id, due_only))


@router.post("/{flashcard_id}/review", response_model=None)
def review_flashcard(
    flashcard_id: str,
    body: FlashcardReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = flashcard_service.review_flashcard(
        db,
        flashcard_id,
        current_user,
        rating=body.rating,
        response=body.response,
    )
    return ok(data=result, message="Flashcard reviewed")
