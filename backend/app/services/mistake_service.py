from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.models.analytics import StudyMistake
from app.models.course import Class, ClassMember
from app.models.user import User


def _resolve_class_for_student(db: Session, student: User, class_id: Optional[str] = None) -> str:
    if class_id:
        membership = db.query(ClassMember).filter(
            ClassMember.user_id == student.id,
            ClassMember.class_id == class_id,
        ).first()
        if not membership:
            raise NotFoundException("Class not found for student")
        return class_id

    membership = db.query(ClassMember).filter(
        ClassMember.user_id == student.id,
        ClassMember.role == "student",
    ).first()
    if not membership:
        raise NotFoundException("Student has no joined class")
    return membership.class_id


def list_mistakes(db: Session, student: User, class_id: Optional[str] = None) -> list[dict]:
    query = db.query(StudyMistake).filter(StudyMistake.user_id == student.id)
    if class_id:
        query = query.filter(StudyMistake.class_id == class_id)
    items = query.order_by(StudyMistake.updated_at.desc()).all()
    return [{
        "id": item.id,
        "class_id": item.class_id,
        "chapter": item.chapter,
        "question": item.question,
        "my_answer": item.my_answer,
        "correct_answer": item.correct_answer,
        "analysis": item.analysis,
        "wrong_count": item.wrong_count,
        "mastered": bool(item.mastered),
        "last_practice_at": item.last_practice_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    } for item in items]


def create_mistake(
    db: Session,
    student: User,
    question: str,
    chapter: Optional[str] = None,
    my_answer: Optional[str] = None,
    correct_answer: Optional[str] = None,
    analysis: Optional[str] = None,
    class_id: Optional[str] = None,
) -> StudyMistake:
    resolved_class_id = _resolve_class_for_student(db, student, class_id)
    mistake = StudyMistake(
        user_id=student.id,
        class_id=resolved_class_id,
        chapter=chapter,
        question=question,
        my_answer=my_answer,
        correct_answer=correct_answer,
        analysis=analysis,
        wrong_count=1,
    )
    db.add(mistake)
    db.commit()
    db.refresh(mistake)
    return mistake


def mark_mastered(db: Session, student: User, mistake_id: str, mastered: bool = True) -> StudyMistake:
    mistake = db.query(StudyMistake).filter(
        StudyMistake.id == mistake_id,
        StudyMistake.user_id == student.id,
    ).first()
    if not mistake:
        raise NotFoundException("Mistake not found")
    mistake.mastered = 1 if mastered else 0
    mistake.last_practice_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(mistake)
    return mistake


def practice_mistake(db: Session, student: User, mistake_id: str) -> StudyMistake:
    mistake = db.query(StudyMistake).filter(
        StudyMistake.id == mistake_id,
        StudyMistake.user_id == student.id,
    ).first()
    if not mistake:
        raise NotFoundException("Mistake not found")
    mistake.wrong_count += 1
    mistake.last_practice_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(mistake)
    return mistake
