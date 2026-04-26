import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.analytics import LearningRecord, QuestionAnalytics, RAGQueryEvent, StudentProfile
from app.models.chat import ChatMessage, ChatSession, ReviewItem, ReviewSyncRecord
from app.models.course import Class, ClassMember, Course, Material, Submission, Task
from app.models.knowledge import FlashcardRecord, KBSpace
from app.models.user import User
from app.services import model_routing_service


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


def get_personalization_routing_metrics(
    db: Session,
    *,
    days: int = 30,
    class_id: Optional[str] = None,
    top_n: int = 12,
) -> dict:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=days)
    query = db.query(RAGQueryEvent).filter(RAGQueryEvent.created_at >= window_start)
    if class_id:
        query = query.filter(RAGQueryEvent.class_id == class_id)
    rows = query.order_by(RAGQueryEvent.created_at.desc()).all()

    by_slice = defaultdict(lambda: {"events": [], "user_ids": set()})
    for row in rows:
        slice_key = _routing_slice_key_from_extra(row.extra_data or {})
        bucket = by_slice[slice_key]
        bucket["events"].append(row)
        if row.user_id:
            bucket["user_ids"].add(row.user_id)

    all_user_ids = {
        user_id
        for group in by_slice.values()
        for user_id in group["user_ids"]
        if user_id
    }

    profiles_by_user: dict[str, StudentProfile] = {}
    if all_user_ids:
        profiles = db.query(StudentProfile).filter(StudentProfile.user_id.in_(list(all_user_ids))).all()
        profiles_by_user = {profile.user_id: profile for profile in profiles}

    learning_events_by_user: dict[str, int] = {}
    if all_user_ids:
        learning_query = db.query(
            LearningRecord.user_id,
            func.count(LearningRecord.id),
        ).filter(
            LearningRecord.user_id.in_(list(all_user_ids)),
            LearningRecord.created_at >= window_start,
        )
        if class_id:
            learning_query = learning_query.filter(LearningRecord.class_id == class_id)
        for user_id, count in learning_query.group_by(LearningRecord.user_id).all():
            learning_events_by_user[user_id] = int(count or 0)

    slices: list[dict] = []
    for slice_key, group in by_slice.items():
        events = group["events"]
        user_ids = group["user_ids"]
        query_count = len(events)
        if query_count <= 0:
            continue

        success_count = sum(1 for row in events if row.success)
        fallback_count = sum(1 for row in events if row.used_fallback)
        avg_confidence = _avg([float(row.confidence) for row in events if row.confidence is not None])
        avg_source_count = _avg([float(row.source_count) for row in events if row.source_count is not None])
        avg_latency = _avg([float(row.latency_ms) for row in events if row.latency_ms is not None])

        profiles = [profiles_by_user[user_id] for user_id in user_ids if user_id in profiles_by_user]
        avg_activity_score = _avg([float(profile.activity_score or 0.0) for profile in profiles])
        avg_task_completion_rate = _avg([float(profile.task_completion_rate or 0.0) for profile in profiles])
        avg_dislike_count = _avg([float(profile.dislike_count or 0) for profile in profiles])

        learning_events_total = sum(learning_events_by_user.get(user_id, 0) for user_id in user_ids)
        learning_events_per_user = round(
            learning_events_total / max(1, len(user_ids)),
            4,
        ) if user_ids else 0.0

        llm_backend, embedding_backend, vlm_backend, reranker_backend = _routing_slice_parts(slice_key)
        slices.append({
            "routing_slice_key": slice_key,
            "llm_backend": llm_backend,
            "embedding_backend": embedding_backend,
            "vlm_backend": vlm_backend,
            "reranker_backend": reranker_backend,
            "queries": query_count,
            "users": len(user_ids),
            "success_rate": _ratio(success_count, query_count),
            "fallback_rate": _ratio(fallback_count, query_count),
            "avg_confidence": avg_confidence,
            "avg_source_count": avg_source_count,
            "avg_latency_ms": avg_latency,
            "avg_activity_score": avg_activity_score,
            "avg_task_completion_rate": avg_task_completion_rate,
            "avg_dislike_count": avg_dislike_count,
            "learning_events_per_user": learning_events_per_user,
        })

    slices.sort(key=lambda item: item["queries"], reverse=True)
    limited = slices[: max(1, int(top_n))] if slices else []
    best_confidence_slice = max(limited, key=lambda item: item["avg_confidence"])["routing_slice_key"] if limited else None
    best_fallback_slice = min(limited, key=lambda item: item["fallback_rate"])["routing_slice_key"] if limited else None

    return {
        "window_days": days,
        "window_start": window_start,
        "window_end": now,
        "filters": {
            "class_id": class_id,
            "top_n": top_n,
        },
        "summary": {
            "total_queries": len(rows),
            "total_slices": len(slices),
            "total_users": len(all_user_ids),
            "best_confidence_slice": best_confidence_slice,
            "lowest_fallback_slice": best_fallback_slice,
        },
        "slices": limited,
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

    recommended_focus = _build_recommended_focus(profile["weak_topics"], profile["strong_topics"])
    recommended_materials = _recommend_materials(
        db,
        student_id=student.id,
        class_ids=class_ids,
        weak_topics=profile["weak_topics"],
    )
    teacher_verified_faq = _recommend_teacher_verified_faq(
        db,
        class_ids=class_ids,
        weak_topics=profile["weak_topics"],
    )
    routing_snapshot = model_routing_service.build_runtime_model_routing_snapshot()
    routing_flat = model_routing_service.flatten_routing_snapshot(routing_snapshot)
    routing_slice_key = "|".join([
        str(routing_flat.get("llm_backend") or "unknown"),
        str(routing_flat.get("embedding_backend") or "unknown"),
        str(routing_flat.get("vlm_backend") or "unknown"),
        str(routing_flat.get("reranker_backend") or "unknown"),
    ])
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
            "recommended_focus": recommended_focus,
            "recommended_materials": recommended_materials,
            "teacher_verified_faq": teacher_verified_faq,
            "recommendation_context": {
                "routing_slice_key": routing_slice_key,
                "llm_backend": routing_flat.get("llm_backend"),
                "embedding_backend": routing_flat.get("embedding_backend"),
                "vlm_backend": routing_flat.get("vlm_backend"),
                "reranker_backend": routing_flat.get("reranker_backend"),
                "recommended_material_count": len(recommended_materials),
                "teacher_verified_faq_count": len(teacher_verified_faq),
                "recommendation_strategy": "weighted_weak_topics+popularity+feedback+review_faq",
            },
        },
        "experiment_context": {
            "routing_slice_key": routing_slice_key,
            "model_routing": routing_snapshot,
        },
    }


def get_material_recommendations(
    db: Session,
    student: User,
    course_id: Optional[str] = None,
) -> dict:
    profile = build_student_profile(db, student)
    class_ids = _class_ids_for_student(db, student.id, course_id)
    routing_snapshot = model_routing_service.build_runtime_model_routing_snapshot()
    routing_flat = model_routing_service.flatten_routing_snapshot(routing_snapshot)
    materials = _recommend_materials(db, student_id=student.id, class_ids=class_ids, weak_topics=profile["weak_topics"])
    faq = _recommend_teacher_verified_faq(db, class_ids=class_ids, weak_topics=profile["weak_topics"])
    return {
        "items": materials,
        "teacher_verified_faq": faq,
        "focus_topics": _build_recommended_focus(profile["weak_topics"], profile["strong_topics"]),
        "context": {
            "course_id": course_id,
            "class_ids": class_ids,
            "weak_topics": profile["weak_topics"],
            "strong_topics": profile["strong_topics"],
            "routing": routing_flat,
            "strategy": "weighted_weak_topics+popularity+feedback+review_faq",
            "algorithm": {
                "name": "explainable_weighted_rules",
                "signals": [
                    "student_weak_topic_match",
                    "class_question_popularity",
                    "rag_indexed_status",
                    "material_recency",
                    "student_recommendation_feedback",
                ],
            },
        },
    }


def build_learning_path_recommendation(
    db: Session,
    student: User,
    course_id: Optional[str] = None,
) -> dict:
    recommendation = get_material_recommendations(db, student, course_id)
    focus_topics = recommendation["focus_topics"] or ["general"]
    material_map = recommendation["items"]
    faq_items = recommendation["teacher_verified_faq"]
    steps = []
    for index, topic in enumerate(focus_topics[:5], start=1):
        related_materials = [
            item for item in material_map
            if topic in (item.get("matched_topics") or [])
        ][:2]
        related_faq = [
            item for item in faq_items
            if topic in (item.get("matched_topics") or item.get("topics") or [])
        ][:2]
        steps.append({
            "step": index,
            "topic": topic,
            "goal": f"Strengthen understanding of {topic}",
            "materials": related_materials,
            "teacher_verified_faq": related_faq,
            "practice_hint": (
                f"Review teacher-verified explanation and then revisit course material for {topic}."
                if related_faq or related_materials
                else f"Ask a focused follow-up question about {topic}."
            ),
        })
    return {
        "course_id": course_id,
        "focus_topics": focus_topics,
        "steps": steps,
        "context": recommendation["context"],
    }


def record_recommendation_feedback(
    db: Session,
    student: User,
    *,
    recommendation_type: str,
    target_id: str,
    feedback: str,
    course_id: Optional[str] = None,
    class_id: Optional[str] = None,
    extra_data: Optional[dict[str, Any]] = None,
) -> dict:
    resolved_class_id = class_id
    if not resolved_class_id:
        class_ids = _class_ids_for_student(db, student.id, course_id)
        resolved_class_id = class_ids[0] if class_ids else None
    if not resolved_class_id:
        raise ValueError("No class context available for recommendation feedback")

    payload = {
        "recommendation_type": recommendation_type,
        "target_id": target_id,
        "feedback": feedback,
        "course_id": course_id,
        **(extra_data or {}),
    }
    record = record_learning(
        db,
        user_id=student.id,
        class_id=resolved_class_id,
        activity_type="recommendation_feedback",
        ref_id=target_id,
        extra_data=payload,
    )
    db.commit()
    return {
        "id": record.id,
        "recommendation_type": recommendation_type,
        "target_id": target_id,
        "feedback": feedback,
        "recorded_at": record.created_at,
        "class_id": resolved_class_id,
        "course_id": course_id,
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


def extract_terms_for_recommendation(text: str) -> list[str]:
    return _extract_terms(text)


def _extract_terms(text: str) -> list[str]:
    latin = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    cjk = re.findall(r"[\u4e00-\u9fff]{2,8}", text)
    return [*latin, *cjk]


def _build_recommended_focus(weak_topics: list[str], strong_topics: list[str]) -> list[str]:
    focus = []
    for topic in [*(weak_topics or [])[:3], *(strong_topics or [])[:2]]:
        if topic and topic not in focus:
            focus.append(topic)
    return focus


def _recommend_materials(
    db: Session,
    *,
    student_id: str,
    class_ids: list[str],
    weak_topics: list[str],
) -> list[dict]:
    if not class_ids:
        return []
    materials = db.query(Material).filter(
        Material.class_id.in_(class_ids),
        Material.is_active == True,
    ).order_by(Material.created_at.desc()).limit(20).all()

    weak_topic_set = set(weak_topics or [])
    feedback_scores = _recommendation_feedback_scores(db, student_id=student_id)
    topic_popularity = _class_topic_popularity(db, class_ids=class_ids)
    now = datetime.now(timezone.utc)
    ranked = []
    for material in materials:
        haystack = " ".join(filter(None, [
            material.title,
            material.file_name,
            material.description,
        ])).lower()
        matched_topics = [topic for topic in weak_topic_set if topic.lower() in haystack]
        popularity_score = min(
            3.0,
            sum(topic_popularity.get(topic.lower(), 0) for topic in matched_topics) / 5.0,
        )
        recency_score = max(0.0, 1.5 - (_days_since(material.created_at, now) / 30.0))
        feedback_score = feedback_scores.get(material.id, 0.0)
        score = len(matched_topics) * 4.0 + popularity_score + recency_score + feedback_score
        if material.kb_status == "indexed":
            score += 1.5
        evidence_signals = {
            "weak_topic_match": round(len(matched_topics) * 4.0, 3),
            "class_question_popularity": round(popularity_score, 3),
            "rag_indexed_status": 1.5 if material.kb_status == "indexed" else 0.0,
            "material_recency": round(recency_score, 3),
            "student_feedback": round(feedback_score, 3),
        }
        ranked.append({
            "material_id": material.id,
            "title": material.title,
            "file_name": material.file_name,
            "file_type": material.file_type,
            "kb_status": material.kb_status,
            "matched_topics": matched_topics,
            "reason": (
                f"Matches weak topics: {', '.join(matched_topics)}"
                if matched_topics
                else "Recent indexed course material with no direct weak-topic match"
            ),
            "score": round(score, 3),
            "evidence_signals": evidence_signals,
            "created_at": material.created_at,
        })

    ranked.sort(key=lambda item: (item["score"], item["created_at"]), reverse=True)
    return [
        {
            "material_id": item["material_id"],
            "title": item["title"],
            "file_name": item["file_name"],
            "file_type": item["file_type"],
            "kb_status": item["kb_status"],
            "matched_topics": item["matched_topics"],
            "reason": item["reason"],
            "score": item["score"],
            "evidence_signals": item["evidence_signals"],
        }
        for item in ranked[:5]
    ]


def _recommendation_feedback_scores(db: Session, *, student_id: str) -> dict[str, float]:
    weights = {
        "helpful": 2.0,
        "useful": 2.0,
        "like": 1.5,
        "saved": 1.5,
        "neutral": 0.0,
        "dismissed": -1.0,
        "not_helpful": -2.0,
        "dislike": -2.0,
    }
    records = db.query(LearningRecord).filter(
        LearningRecord.user_id == student_id,
        LearningRecord.activity_type == "recommendation_feedback",
    ).all()
    scores: dict[str, float] = defaultdict(float)
    for record in records:
        extra = record.extra_data or {}
        target_id = str(extra.get("target_id") or record.ref_id or "").strip()
        feedback = str(extra.get("feedback") or "").strip().lower()
        if target_id:
            scores[target_id] += weights.get(feedback, 0.0)
    return dict(scores)


def _class_topic_popularity(db: Session, *, class_ids: list[str]) -> dict[str, int]:
    if not class_ids:
        return {}
    rows = db.query(QuestionAnalytics).filter(QuestionAnalytics.class_id.in_(class_ids)).all()
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        topic = str(row.topic or "").strip().lower()
        if topic:
            counts[topic] += int(row.question_count or 0)
    return dict(counts)


def _days_since(value: datetime | None, now: datetime) -> float:
    if not value:
        return 365.0
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return max(0.0, (now - value).total_seconds() / 86400.0)


def _recommend_teacher_verified_faq(db: Session, *, class_ids: list[str], weak_topics: list[str]) -> list[dict]:
    if not class_ids:
        return []
    kb_spaces = db.query(KBSpace).filter(KBSpace.class_id.in_(class_ids)).all()
    weak_topic_set = set(weak_topics or [])
    faq_items = []
    for kb_space in kb_spaces:
        extra = kb_space.extra_data or {}
        for faq in extra.get("review_faq") or []:
            if not isinstance(faq, dict):
                continue
            topics = faq.get("topics") or []
            matched_topics = [topic for topic in topics if topic in weak_topic_set]
            score = len(matched_topics) * 2 + (1 if faq.get("sync_status") == "synced" else 0)
            faq_items.append({
                "question": faq.get("question"),
                "answer": faq.get("answer"),
                "topics": topics,
                "matched_topics": matched_topics,
                "sync_status": faq.get("sync_status"),
                "reviewed_at": faq.get("reviewed_at"),
                "reason": (
                    f"Teacher-verified answer for weak topics: {', '.join(matched_topics)}"
                    if matched_topics
                    else "Recent teacher-verified answer"
                ),
                "score": score,
            })
    sync_records = db.query(ReviewSyncRecord).filter(
        ReviewSyncRecord.class_id.in_(class_ids),
        ReviewSyncRecord.sync_status.in_(["synced", "pending"]),
    ).order_by(ReviewSyncRecord.created_at.desc()).all()
    for record in sync_records:
        topics = _extract_terms(record.question_content)[:6]
        matched_topics = [topic for topic in topics if topic in weak_topic_set]
        score = len(matched_topics) * 2 + (1 if record.sync_status == "synced" else 0)
        faq_items.append({
            "question": record.question_content,
            "answer": record.final_answer,
            "topics": topics,
            "matched_topics": matched_topics,
            "sync_status": record.sync_status,
            "reviewed_at": (record.synced_at or record.created_at).isoformat() if (record.synced_at or record.created_at) else None,
            "reason": (
                f"Teacher-verified answer for weak topics: {', '.join(matched_topics)}"
                if matched_topics
                else "Recent teacher-verified answer"
            ),
            "score": score,
        })
    faq_items.sort(key=lambda item: (item["score"], item.get("reviewed_at") or ""), reverse=True)
    deduped = []
    seen_questions = set()
    for item in faq_items:
        question = item.get("question")
        if question in seen_questions:
            continue
        seen_questions.add(question)
        deduped.append(item)
        if len(deduped) >= 5:
            break
    return deduped


def _routing_slice_key_from_extra(extra_data: dict) -> str:
    llm_backend = (extra_data.get("llm_backend") or "unknown").strip() if isinstance(extra_data, dict) else "unknown"
    embedding_backend = (extra_data.get("embedding_backend") or "unknown").strip() if isinstance(extra_data, dict) else "unknown"
    vlm_backend = (extra_data.get("vlm_backend") or "unknown").strip() if isinstance(extra_data, dict) else "unknown"
    reranker_backend = (extra_data.get("reranker_backend") or "unknown").strip() if isinstance(extra_data, dict) else "unknown"
    return "|".join([llm_backend, embedding_backend, vlm_backend, reranker_backend])


def _routing_slice_parts(slice_key: str) -> tuple[str, str, str, str]:
    values = (slice_key or "").split("|")
    if len(values) != 4:
        return ("unknown", "unknown", "unknown", "unknown")
    return values[0], values[1], values[2], values[3]


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(part / total, 4)


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
