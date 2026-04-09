import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.analytics import LearningRecord, QuestionAnalytics, StudentProfile
from app.models.chat import ChatMessage, ChatSession, ReviewItem
from app.models.course import Class, ClassMember, Course, Submission, Task
from app.models.knowledge import FlashcardRecord
from app.models.user import User


def record_learning(
    db: Session,
    user_id: str,
    class_id: str,
    activity_type: str,
    ref_id: Optional[str] = None,
    extra_data: Optional[dict] = None,
    duration_seconds: Optional[int] = None,
) -> LearningRecord:
    record = LearningRecord(
        user_id=user_id,
        class_id=class_id,
        activity_type=activity_type,
        ref_id=ref_id,
        extra_data=extra_data,
        duration_seconds=duration_seconds,
    )
    db.add(record)
    db.flush()
    return record


def record_question_topics(db: Session, class_id: str, question: str) -> None:
    topics = _extract_terms(question)
    if not topics:
        topics = ["general"]

    for topic in topics[:5]:
        existing = db.query(QuestionAnalytics).filter(
            QuestionAnalytics.class_id == class_id,
            QuestionAnalytics.topic == topic,
        ).first()
        if existing:
            existing.question_count += 1
            existing.last_asked_at = datetime.now(timezone.utc)
            existing.updated_at = datetime.now(timezone.utc)
        else:
            db.add(QuestionAnalytics(
                class_id=class_id,
                topic=topic,
                question_count=1,
            ))


def compute_course_analytics(db: Session, course_id: str) -> dict:
    classes = db.query(Class).filter(Class.course_id == course_id, Class.is_active == True).all()
    class_ids = [cls.id for cls in classes]
    if not class_ids:
        return {
            "course_id": course_id,
            "question_count": 0,
            "high_frequency_keywords": [],
            "disliked_question_count": 0,
            "active_student_count": 0,
            "task_completion_rate": 0.0,
            "hot_topics": [],
        }

    student_count = db.query(ClassMember).filter(
        ClassMember.class_id.in_(class_ids),
        ClassMember.role == "student",
    ).count()

    question_count = db.query(ChatMessage).join(
        ChatSession, ChatSession.id == ChatMessage.session_id
    ).filter(
        ChatSession.class_id.in_(class_ids),
        ChatMessage.role == "user",
    ).count()

    disliked_question_count = db.query(ReviewItem).filter(
        ReviewItem.class_id.in_(class_ids),
        ReviewItem.trigger == "dislike",
    ).count()

    two_weeks_ago = datetime.now(timezone.utc) - timedelta(days=14)
    active_student_count = db.query(func.count(func.distinct(LearningRecord.user_id))).filter(
        LearningRecord.class_id.in_(class_ids),
        LearningRecord.created_at >= two_weeks_ago,
    ).scalar() or 0

    published_tasks = db.query(Task).filter(
        Task.class_id.in_(class_ids),
        Task.is_published == True,
    ).count()
    submission_count = db.query(Submission).join(
        Task, Task.id == Submission.task_id
    ).filter(Task.class_id.in_(class_ids)).count()
    expected_submissions = published_tasks * student_count
    task_completion_rate = round(submission_count / expected_submissions, 3) if expected_submissions else 0.0

    top_topics = db.query(QuestionAnalytics).filter(
        QuestionAnalytics.class_id.in_(class_ids)
    ).order_by(QuestionAnalytics.question_count.desc()).limit(8).all()

    hot_topics = [{"topic": topic.topic, "count": topic.question_count} for topic in top_topics]

    return {
        "course_id": course_id,
        "student_count": student_count,
        "question_count": question_count,
        "high_frequency_keywords": [item["topic"] for item in hot_topics[:5]],
        "disliked_question_count": disliked_question_count,
        "active_student_count": active_student_count,
        "task_completion_rate": task_completion_rate,
        "hot_topics": hot_topics,
        "pending_review_count": db.query(ReviewItem).filter(
            ReviewItem.class_id.in_(class_ids),
            ReviewItem.status == "pending",
        ).count(),
    }


def build_student_profile(db: Session, student: User) -> dict:
    class_memberships = db.query(ClassMember).filter(
        ClassMember.user_id == student.id,
        ClassMember.role == "student",
    ).all()
    class_ids = [membership.class_id for membership in class_memberships]
    classes = db.query(Class).filter(Class.id.in_(class_ids)).all() if class_ids else []
    courses = db.query(Course).filter(Course.id.in_([cls.course_id for cls in classes])).all() if classes else []

    total_questions = db.query(ChatMessage).join(
        ChatSession, ChatSession.id == ChatMessage.session_id
    ).filter(
        ChatSession.user_id == student.id,
        ChatMessage.role == "user",
    ).count()

    dislike_count = db.query(ChatMessage).join(
        ChatSession, ChatSession.id == ChatMessage.session_id
    ).filter(
        ChatSession.user_id == student.id,
        ChatMessage.feedback == "dislike",
    ).count()

    published_tasks = db.query(Task).filter(
        Task.class_id.in_(class_ids),
        Task.is_published == True,
    ).count() if class_ids else 0
    completed_tasks = db.query(Submission).filter(Submission.student_id == student.id).count()
    task_completion_rate = round(completed_tasks / published_tasks, 3) if published_tasks else 0.0

    learning_records = db.query(LearningRecord).filter(
        LearningRecord.user_id == student.id
    ).order_by(LearningRecord.created_at.desc()).all()
    activity_score = min(100.0, round(
        total_questions * 2.5
        + completed_tasks * 4
        + len(learning_records) * 1.2,
        2,
    ))
    last_active_at = learning_records[0].created_at if learning_records else None

    weak_topics = _student_weak_topics(db, class_ids, student.id)
    strong_topics = _student_strong_topics(db, student.id)

    payload = {
        "user_id": student.id,
        "preferred_courses": [course.name for course in courses[:5]],
        "strong_topics": strong_topics,
        "weak_topics": weak_topics,
        "total_questions": total_questions,
        "dislike_count": dislike_count,
        "task_completion_rate": task_completion_rate,
        "activity_score": activity_score,
        "last_active_at": last_active_at,
        "extra_data": {
            "course_count": len(courses),
            "class_count": len(classes),
        },
    }

    profile = db.query(StudentProfile).filter(StudentProfile.user_id == student.id).first()
    if not profile:
        profile = StudentProfile(user_id=student.id)
        db.add(profile)

    for key, value in payload.items():
        setattr(profile, key, value)

    db.commit()
    db.refresh(profile)

    return {
        "user_id": profile.user_id,
        "preferred_courses": profile.preferred_courses or [],
        "strong_topics": profile.strong_topics or [],
        "weak_topics": profile.weak_topics or [],
        "total_questions": profile.total_questions,
        "dislike_count": profile.dislike_count,
        "task_completion_rate": profile.task_completion_rate,
        "activity_score": profile.activity_score,
        "last_active_at": profile.last_active_at,
        "extra_data": profile.extra_data or {},
    }


def build_student_report(
    db: Session,
    student: User,
    period: str,
    course_id: Optional[str] = None,
) -> dict:
    now = datetime.now(timezone.utc)
    if period == "weekly":
        start_at = now - timedelta(days=7)
    else:
        start_at = now - timedelta(days=30)

    profile = build_student_profile(db, student)
    class_ids = _class_ids_for_student(db, student.id, course_id)
    learning_query = db.query(LearningRecord).filter(
        LearningRecord.user_id == student.id,
        LearningRecord.created_at >= start_at,
    )
    if class_ids:
        learning_query = learning_query.filter(LearningRecord.class_id.in_(class_ids))
    records = learning_query.all()

    task_submissions = db.query(Submission).filter(
        Submission.student_id == student.id,
        Submission.submitted_at >= start_at,
    ).count()
    question_count = db.query(ChatMessage).join(
        ChatSession, ChatSession.id == ChatMessage.session_id
    ).filter(
        ChatSession.user_id == student.id,
        ChatMessage.role == "user",
        ChatMessage.created_at >= start_at,
    ).count()
    flashcard_reviews = db.query(FlashcardRecord).filter(
        FlashcardRecord.user_id == student.id,
        FlashcardRecord.reviewed_at >= start_at,
    ).count()

    high_frequency = profile["weak_topics"][:3] + profile["strong_topics"][:2]
    summary = (
        f"In the last {'7' if period == 'weekly' else '30'} days, you asked {question_count} questions, "
        f"submitted {task_submissions} tasks, and reviewed {flashcard_reviews} flashcards."
    )

    return {
        "period": period,
        "course_id": course_id,
        "generated_at": now,
        "summary": summary,
        "metrics": {
            "question_count": question_count,
            "task_submissions": task_submissions,
            "flashcard_reviews": flashcard_reviews,
            "learning_events": len(records),
            "activity_score": profile["activity_score"],
            "task_completion_rate": profile["task_completion_rate"],
        },
        "highlights": {
            "strong_topics": profile["strong_topics"],
            "weak_topics": profile["weak_topics"],
            "recommended_focus": high_frequency,
        },
    }


def export_student_report_csv(
    db: Session,
    student: User,
    course_id: Optional[str] = None,
) -> str:
    weekly = build_student_report(db, student, "weekly", course_id)
    monthly = build_student_report(db, student, "monthly", course_id)
    rows = [
        ["period", "question_count", "task_submissions", "flashcard_reviews", "learning_events", "activity_score", "task_completion_rate"],
        [
            "weekly",
            weekly["metrics"]["question_count"],
            weekly["metrics"]["task_submissions"],
            weekly["metrics"]["flashcard_reviews"],
            weekly["metrics"]["learning_events"],
            weekly["metrics"]["activity_score"],
            weekly["metrics"]["task_completion_rate"],
        ],
        [
            "monthly",
            monthly["metrics"]["question_count"],
            monthly["metrics"]["task_submissions"],
            monthly["metrics"]["flashcard_reviews"],
            monthly["metrics"]["learning_events"],
            monthly["metrics"]["activity_score"],
            monthly["metrics"]["task_completion_rate"],
        ],
    ]
    return "\n".join(",".join(map(str, row)) for row in rows)


def _student_weak_topics(db: Session, class_ids: list[str], student_id: str) -> list[str]:
    topics = []
    review_items = db.query(ReviewItem).filter(ReviewItem.class_id.in_(class_ids), ReviewItem.student_id == student_id).all() if class_ids else []
    for item in review_items:
        topics.extend(_extract_terms(item.question_content))
    counts = Counter(topics)
    return [topic for topic, _ in counts.most_common(5)]


def _student_strong_topics(db: Session, student_id: str) -> list[str]:
    records = db.query(FlashcardRecord).filter(
        FlashcardRecord.user_id == student_id,
        FlashcardRecord.rating >= 4,
    ).all()
    topic_counts = Counter()
    for record in records:
        tags = ((record.extra_data or {}).get("tags") or [])
        topic_counts.update(tags)
    return [topic for topic, _ in topic_counts.most_common(5)]


def _extract_terms(text: str) -> list[str]:
    latin = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    cjk = re.findall(r"[\u4e00-\u9fff]{2,8}", text)
    return [*latin, *cjk]


def _class_ids_for_student(db: Session, student_id: str, course_id: Optional[str] = None) -> list[str]:
    query = db.query(ClassMember).filter(
        ClassMember.user_id == student_id,
        ClassMember.role == "student",
    )
    memberships = query.all()
    class_ids = [membership.class_id for membership in memberships]
    if not course_id:
        return class_ids
    classes = db.query(Class).filter(Class.id.in_(class_ids), Class.course_id == course_id).all() if class_ids else []
    return [cls.id for cls in classes]
