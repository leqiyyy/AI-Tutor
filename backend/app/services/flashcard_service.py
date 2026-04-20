from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.analytics import LearningRecord
from app.models.course import Class, ClassMember
from app.models.knowledge import Flashcard, FlashcardRecord
from app.models.user import User
from app.services import analytics_service

RESPONSE_TO_RATING = {
    "again": 1,
    "hard": 2,
    "good": 4,
    "easy": 5,
}
MAX_INTERVAL_DAYS = 36500


def list_flashcards(
    db: Session,
    user: User,
    course_id: Optional[str] = None,
    class_id: Optional[str] = None,
    due_only: bool = False,
) -> list[dict]:
    query = db.query(Flashcard).filter(Flashcard.user_id == user.id, Flashcard.is_active == True)

    if class_id:
        query = query.filter(Flashcard.class_id == class_id)
    elif course_id:
        class_ids = [cls.id for cls in db.query(Class).filter(Class.course_id == course_id).all()]
        query = query.filter(Flashcard.class_id.in_(class_ids))

    if due_only:
        now = datetime.now(timezone.utc)
        query = query.filter((Flashcard.next_review_at == None) | (Flashcard.next_review_at <= now))

    items = query.order_by(Flashcard.next_review_at.asc().nullsfirst(), Flashcard.created_at.desc()).all()
    return [{
        "id": item.id,
        "class_id": item.class_id,
        "question": item.question,
        "answer": item.answer,
        "tags": item.tags or [],
        "ease_factor": item.ease_factor,
        "interval_days": item.interval_days,
        "next_review_at": item.next_review_at,
        "review_count": item.review_count,
        "created_at": item.created_at,
    } for item in items]


def review_flashcard(
    db: Session,
    flashcard_id: str,
    user: User,
    rating: Optional[int] = None,
    response: Optional[str] = None,
) -> dict:
    flashcard = db.query(Flashcard).filter(Flashcard.id == flashcard_id, Flashcard.user_id == user.id).first()
    if not flashcard:
        raise NotFoundException("Flashcard not found")

    if response and rating is None:
        rating = RESPONSE_TO_RATING.get(response, 3)
    rating = rating or 3

    interval_before = flashcard.interval_days
    if rating <= 2:
        flashcard.interval_days = 1
        flashcard.ease_factor = max(1.3, flashcard.ease_factor - 0.2)
    elif rating == 3:
        flashcard.interval_days = max(2, flashcard.interval_days + 1)
    elif rating == 4:
        flashcard.interval_days = max(3, int(round(flashcard.interval_days * flashcard.ease_factor)))
        flashcard.ease_factor = min(3.0, flashcard.ease_factor + 0.05)
    else:
        flashcard.interval_days = max(4, int(round(flashcard.interval_days * (flashcard.ease_factor + 0.3))))
        flashcard.ease_factor = min(3.2, flashcard.ease_factor + 0.1)

    flashcard.interval_days = min(MAX_INTERVAL_DAYS, max(1, int(flashcard.interval_days)))
    flashcard.review_count += 1
    flashcard.next_review_at = datetime.now(timezone.utc) + timedelta(days=flashcard.interval_days)

    record = FlashcardRecord(
        flashcard_id=flashcard.id,
        user_id=user.id,
        rating=rating,
        response=response,
        interval_before=interval_before,
        interval_after=flashcard.interval_days,
        next_review_at=flashcard.next_review_at,
        extra_data={"tags": flashcard.tags or []},
    )
    db.add(record)
    analytics_service.record_learning(
        db,
        user_id=user.id,
        class_id=flashcard.class_id,
        activity_type="flashcard_review",
        ref_id=flashcard.id,
        extra_data={"rating": rating, "response": response},
    )
    db.commit()
    db.refresh(flashcard)

    return {
        "flashcard_id": flashcard.id,
        "rating": rating,
        "response": response,
        "interval_days": flashcard.interval_days,
        "next_review_at": flashcard.next_review_at,
        "review_count": flashcard.review_count,
    }
