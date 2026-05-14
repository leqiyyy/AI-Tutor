from __future__ import annotations

import csv
import io
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.core.timezone import date_app_timezone, isoformat_app_timezone
from app.models.analytics import LearningRecord, StudyMistake
from app.models.chat import ChatMessage, ChatSession, ReviewItem
from app.models.course import Class, ClassMember, Material, Submission, Task
from app.models.knowledge import Flashcard, FlashcardRecord, KnowledgeEntity
from app.models.personalization import LearningConcept, StudentConceptMastery
from app.models.user import User


ACTIVITY_DURATION_FALLBACKS = {
    "ask_question": 120,
    "message_dislike": 30,
    "submit_task": 900,
    "flashcard_review": 60,
    "view_material": 300,
    "material_study_duration": 0,
    "view_knowledge_graph": 180,
    "view_learning_profile": 45,
    "recommendation_feedback": 45,
    "recommendation_click": 120,
    "export_learning_report": 20,
}


def resolve_learning_class(db: Session, student: User, course_or_class_id: str) -> Class:
    membership = db.query(ClassMember).filter(
        ClassMember.user_id == student.id,
        ClassMember.class_id == course_or_class_id,
    ).first()
    if membership:
        cls = db.query(Class).filter(Class.id == membership.class_id, Class.is_active == True).first()
        if cls:
            return cls

    cls = db.query(Class).join(ClassMember, ClassMember.class_id == Class.id).filter(
        Class.course_id == course_or_class_id,
        ClassMember.user_id == student.id,
        Class.is_active == True,
    ).order_by(Class.created_at.desc()).first()
    if cls:
        return cls
    raise NotFoundException("Learning class not found for student")


def build_learning_overview(db: Session, student: User, course_or_class_id: str) -> dict:
    cls = resolve_learning_class(db, student, course_or_class_id)
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=6)
    month_start = now - timedelta(days=30)

    week_records = _learning_records(db, student.id, cls.id, week_start)
    month_records = _learning_records(db, student.id, cls.id, month_start)
    week_hours = _build_week_hours(week_records, week_start, now)
    total_week_hours = sum(item["hours"] for item in week_hours)

    question_count = _question_count(db, student.id, cls.id, month_start)
    published_tasks, completed_tasks, task_rate = _task_stats(db, student.id, cls.id)
    flashcards = _flashcards(db, student.id, cls.id)
    flashcard_reviews = _flashcard_review_count(db, student.id, month_start, cls.id)
    mistakes = _mistakes(db, student.id, cls.id)
    mastered_mistakes = sum(1 for item in mistakes if item.mastered)

    radar_data = _build_radar_data(
        task_rate=task_rate,
        question_count=question_count,
        flashcard_count=len(flashcards),
        flashcard_reviews=flashcard_reviews,
        mistakes=mistakes,
        records=month_records,
        mastery_rows=_concept_mastery_rows(db, student.id, cls.id),
    )

    return {
        "summaryCards": [
            {
                "label": "本周学习时长",
                "value": f"{total_week_hours:.1f}h",
                "sub": f"{len([d for d in week_hours if d['hours'] > 0])} 天活跃",
                "icon": "ri-time-line",
                "color": "teal",
                "progress": _clamp(round(total_week_hours / 14 * 100)),
            },
            {
                "label": "任务完成率",
                "value": f"{round(task_rate * 100)}%",
                "sub": f"{completed_tasks}/{published_tasks}",
                "icon": "ri-task-line",
                "color": "green",
                "progress": _clamp(round(task_rate * 100)),
            },
            {
                "label": "AI 提问",
                "value": f"{question_count}次",
                "sub": "近30天",
                "icon": "ri-question-answer-line",
                "color": "sky",
                "progress": _clamp(question_count * 5),
            },
            {
                "label": "错题修复",
                "value": f"{mastered_mistakes}/{len(mistakes)}",
                "sub": "已掌握/总错题",
                "icon": "ri-error-warning-line",
                "color": "amber",
                "progress": _clamp(round(mastered_mistakes / max(1, len(mistakes)) * 100)),
            },
        ],
        "radarData": radar_data,
        "keywordData": _build_keyword_data(db, student.id, cls.id),
        "weekHours": week_hours,
        "chapterProgress": _build_chapter_progress(db, student.id, cls.id, radar_data),
    }


def build_learning_report(db: Session, student: User, course_or_class_id: str, period: str) -> dict:
    cls = resolve_learning_class(db, student, course_or_class_id)
    days = 7 if period == "weekly" else 30
    now = datetime.now(timezone.utc)
    start_at = now - timedelta(days=days)
    records = _learning_records(db, student.id, cls.id, start_at)
    hours = _records_to_hours(records)
    question_count = _question_count(db, student.id, cls.id, start_at)
    published_tasks, completed_tasks, task_rate = _task_stats(db, student.id, cls.id, start_at)
    flashcard_reviews = _flashcard_review_count(db, student.id, start_at, cls.id)
    mistakes = _mistakes(db, student.id, cls.id)
    weak_topics = _weak_topics_from_evidence(db, student.id, cls.id)
    strong_topics = _strong_topics_from_mastery(db, student.id, cls.id)

    cards = [
        {"label": "学习时长" if period == "weekly" else "总学习时长", "value": f"{hours:.1f}h", "color": "teal"},
        {"label": "任务完成", "value": f"{completed_tasks}/{published_tasks}", "color": "green"},
        {"label": "AI提问", "value": f"{question_count}次", "color": "sky"},
        {"label": "闪卡复习", "value": f"{flashcard_reviews}张", "color": "violet"},
    ]
    suggestions = _build_suggestions(weak_topics, question_count, task_rate, hours, period)
    highlights = _build_highlights(strong_topics, task_rate, flashcard_reviews, period)
    return {
        "period": period,
        "title": "学习周报" if period == "weekly" else "学习月报",
        "rangeLabel": _range_label(start_at, now, period),
        "generatedAt": now.isoformat(),
        "summary": f"本{'周' if period == 'weekly' else '月'}学习 {hours:.1f} 小时，提出 {question_count} 个问题，完成 {completed_tasks}/{published_tasks} 项任务。",
        "cards": cards,
        "metrics": {
            "studyHours": round(hours, 2),
            "questionCount": question_count,
            "taskCompleted": completed_tasks,
            "taskPublished": published_tasks,
            "taskCompletionRate": round(task_rate, 3),
            "flashcardReviews": flashcard_reviews,
            "mistakeCount": len(mistakes),
            "masteredMistakeCount": sum(1 for item in mistakes if item.mastered),
            "learningEvents": len(records),
        },
        "weakTopics": weak_topics,
        "strongTopics": strong_topics,
        "suggestions": suggestions,
        "highlights": highlights,
    }


def export_learning_report_csv(db: Session, student: User, course_or_class_id: str, period: str) -> str:
    report = build_learning_report(db, student, course_or_class_id, period)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "metric", "value"])
    writer.writerow(["summary", "period", report["period"]])
    writer.writerow(["summary", "range", report["rangeLabel"]])
    writer.writerow(["summary", "summary", report["summary"]])
    for key, value in report["metrics"].items():
        writer.writerow(["metrics", key, value])
    for topic in report["weakTopics"]:
        writer.writerow(["weak_topics", "topic", topic])
    for topic in report["strongTopics"]:
        writer.writerow(["strong_topics", "topic", topic])
    for suggestion in report["suggestions"]:
        writer.writerow(["suggestions", "item", suggestion])
    return output.getvalue()


def record_learning_event(
    db: Session,
    student: User,
    course_or_class_id: str,
    *,
    activity_type: str,
    ref_id: Optional[str] = None,
    duration_seconds: Optional[int] = None,
    extra_data: Optional[dict[str, Any]] = None,
) -> dict:
    cls = resolve_learning_class(db, student, course_or_class_id)
    record = LearningRecord(
        user_id=student.id,
        class_id=cls.id,
        activity_type=activity_type,
        ref_id=ref_id,
        duration_seconds=max(0, int(duration_seconds or 0)) if duration_seconds is not None else None,
        extra_data=extra_data or {},
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"id": record.id, "created_at": record.created_at, "class_id": cls.id}


def list_learning_mistakes(db: Session, student: User, course_or_class_id: str) -> dict:
    cls = resolve_learning_class(db, student, course_or_class_id)
    return {"mistakes": [_mistake_to_frontend(item) for item in _mistakes(db, student.id, cls.id)]}


def create_learning_mistake(db: Session, student: User, course_or_class_id: str, payload: dict) -> dict:
    cls = resolve_learning_class(db, student, course_or_class_id)
    mistake = StudyMistake(
        user_id=student.id,
        class_id=cls.id,
        chapter=payload.get("chapter"),
        question=payload.get("question") or "",
        my_answer=payload.get("myAnswer") or payload.get("my_answer"),
        correct_answer=payload.get("correctAnswer") or payload.get("correct_answer"),
        analysis=payload.get("analysis"),
        wrong_count=1,
        extra_data={"source": "manual"},
    )
    db.add(mistake)
    db.commit()
    db.refresh(mistake)
    return _mistake_to_frontend(mistake)


def mark_learning_mistake_mastered(db: Session, student: User, mistake_id: str) -> dict:
    mistake = db.query(StudyMistake).filter(StudyMistake.id == mistake_id, StudyMistake.user_id == student.id).first()
    if not mistake:
        raise NotFoundException("Mistake not found")
    mistake.mastered = 1
    mistake.last_practice_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(mistake)
    return _mistake_to_frontend(mistake)


def practice_learning_mistake(db: Session, student: User, course_or_class_id: str, mistake_id: str) -> dict:
    cls = resolve_learning_class(db, student, course_or_class_id)
    mistake = db.query(StudyMistake).filter(
        StudyMistake.id == mistake_id,
        StudyMistake.user_id == student.id,
        StudyMistake.class_id == cls.id,
    ).first()
    if not mistake:
        raise NotFoundException("Mistake not found")
    mistake.last_practice_at = datetime.now(timezone.utc)
    db.add(LearningRecord(
        user_id=student.id,
        class_id=cls.id,
        activity_type="mistake_practice",
        ref_id=mistake.id,
        extra_data={
            "chapter": mistake.chapter,
            "mastered": bool(mistake.mastered),
        },
    ))
    db.commit()
    db.refresh(mistake)
    return {
        "mistakeId": mistake.id,
        "prompt": f"请重新作答这道错题，并特别说明关键步骤：\n\n{mistake.question}",
        "answerHint": mistake.correct_answer or "",
        "analysis": mistake.analysis or "",
        "lastPracticeTime": _date_text(mistake.last_practice_at),
        "mistake": _mistake_to_frontend(mistake),
    }


def generate_similar_mistake_practice(db: Session, student: User, course_or_class_id: str, mistake_id: str) -> dict:
    cls = resolve_learning_class(db, student, course_or_class_id)
    mistake = db.query(StudyMistake).filter(
        StudyMistake.id == mistake_id,
        StudyMistake.user_id == student.id,
        StudyMistake.class_id == cls.id,
    ).first()
    if not mistake:
        raise NotFoundException("Mistake not found")
    mistake.last_practice_at = datetime.now(timezone.utc)
    chapter = mistake.chapter or "当前知识点"
    prompt = (
        f"相似练习（{chapter}）：\n"
        f"请围绕原错题考查的同一知识点，完成一道变式题，并写出关键步骤。\n\n"
        f"原错题：{mistake.question}\n\n"
        f"变式题：请换一个场景或参数，重新判断并说明理由。"
    )
    db.add(LearningRecord(
        user_id=student.id,
        class_id=cls.id,
        activity_type="mistake_similar_practice",
        ref_id=mistake.id,
        extra_data={
            "chapter": chapter,
            "source_question": mistake.question[:300],
        },
    ))
    db.commit()
    db.refresh(mistake)
    return {
        "mistakeId": mistake.id,
        "prompt": prompt,
        "answerHint": mistake.correct_answer or "",
        "analysis": mistake.analysis or "",
        "lastPracticeTime": _date_text(mistake.last_practice_at),
        "mistake": _mistake_to_frontend(mistake),
    }


def list_learning_flashcard_decks(db: Session, student: User, course_or_class_id: str) -> dict:
    cls = resolve_learning_class(db, student, course_or_class_id)
    cards = _flashcards(db, student.id, cls.id)
    if not cards:
        return {"decks": []}
    grouped: dict[str, list[Flashcard]] = {}
    for card in cards:
        deck_name = _flashcard_deck_name(card, cls.name)
        grouped.setdefault(deck_name, []).append(card)

    decks = [
        _flashcard_deck_to_frontend(cls.id, deck_name, deck_cards)
        for deck_name, deck_cards in grouped.items()
    ]
    decks.sort(key=lambda item: (0 if item["dueCount"] else 1, item["name"]))
    return {"decks": decks}


def _flashcard_deck_name(card: Flashcard, class_name: str) -> str:
    tags = card.tags if isinstance(card.tags, list) else []
    for tag in tags:
        text = str(tag or "").strip()
        if text:
            return text
    return f"{class_name} · 我的闪卡"


def _flashcard_deck_to_frontend(class_id: str, deck_name: str, cards: list[Flashcard]) -> dict:
    mastered = sum(1 for card in cards if (card.review_count or 0) > 0 and (card.interval_days or 0) >= 7)
    learning = sum(1 for card in cards if (card.review_count or 0) > 0 and (card.interval_days or 0) < 7)
    new = sum(1 for card in cards if not card.review_count)
    next_review = min([card.next_review_at for card in cards if card.next_review_at] or [None])
    due_count = sum(1 for card in cards if _flashcard_due(card))
    return {
        "id": f"deck:{class_id}:{deck_name}",
        "name": deck_name,
        "cards": len(cards),
        "mastered": mastered,
        "learning": learning,
        "new": new,
        "dueCount": due_count,
        "nextReview": "今天" if due_count else (_date_text(next_review) if next_review else "暂无复习计划"),
        "cardList": [_flashcard_to_frontend(card) for card in cards],
    }


def create_learning_flashcard_deck(db: Session, student: User, course_or_class_id: str, payload: dict) -> dict:
    cls = resolve_learning_class(db, student, course_or_class_id)
    cards_payload = payload.get("cards") or []
    created: list[Flashcard] = []
    for card in cards_payload:
        question = (card or {}).get("front") or (card or {}).get("question")
        answer = (card or {}).get("back") or (card or {}).get("answer")
        if not question or not answer:
            continue
        row = Flashcard(
            class_id=cls.id,
            user_id=student.id,
            question=str(question),
            answer=str(answer),
            tags=[payload.get("name") or "自建卡组"],
        )
        db.add(row)
        created.append(row)
    db.commit()
    if created:
        for card in created:
            db.refresh(card)
        return _flashcard_deck_to_frontend(cls.id, payload.get("name") or "自建卡组", created)
    return {
        "id": f"class:{cls.id}",
        "name": payload.get("name") or "新卡组",
        "cards": 0,
        "mastered": 0,
        "learning": 0,
        "new": 0,
        "dueCount": 0,
        "nextReview": "暂无复习计划",
        "cardList": [],
    }


def review_learning_flashcard(db: Session, student: User, course_or_class_id: str, payload: dict) -> dict:
    cls = resolve_learning_class(db, student, course_or_class_id)
    cards = _flashcards(db, student.id, cls.id)
    card_id = payload.get("cardId") or payload.get("card_id")
    if card_id:
        card = next((item for item in cards if str(item.id) == str(card_id)), None)
    else:
        card_index = int(payload.get("cardIndex") or payload.get("card_index") or 0)
        card = cards[card_index] if 0 <= card_index < len(cards) else None
    if not card:
        raise NotFoundException("Flashcard not found")
    response = payload.get("difficulty") or payload.get("response") or "good"
    rating = {"forget": 1, "hard": 2, "good": 4, "easy": 5}.get(response, 4)
    before = card.interval_days or 1
    if rating <= 2:
        card.interval_days = 1
    elif rating == 4:
        card.interval_days = max(3, int(round(before * (card.ease_factor or 2.5))))
    else:
        card.interval_days = max(4, int(round(before * ((card.ease_factor or 2.5) + 0.3))))
    card.review_count = (card.review_count or 0) + 1
    card.next_review_at = datetime.now(timezone.utc) + timedelta(days=card.interval_days)
    db.add(FlashcardRecord(
        flashcard_id=card.id,
        user_id=student.id,
        rating=rating,
        response=response,
        interval_before=before,
        interval_after=card.interval_days,
        next_review_at=card.next_review_at,
    ))
    db.add(LearningRecord(
        user_id=student.id,
        class_id=cls.id,
        activity_type="flashcard_review",
        ref_id=card.id,
        extra_data={"rating": rating, "response": response},
    ))
    db.commit()
    return {"flashcard_id": card.id, "rating": rating, "next_review_at": card.next_review_at}


def _learning_records(db: Session, user_id: str, class_id: str, start_at: datetime) -> list[LearningRecord]:
    return db.query(LearningRecord).filter(
        LearningRecord.user_id == user_id,
        LearningRecord.class_id == class_id,
        LearningRecord.created_at >= start_at,
    ).all()


def _records_to_hours(records: list[LearningRecord]) -> float:
    seconds = 0
    for record in records:
        seconds += record.duration_seconds if record.duration_seconds is not None else ACTIVITY_DURATION_FALLBACKS.get(record.activity_type, 60)
    return round(seconds / 3600, 2)


def _build_week_hours(records: list[LearningRecord], start_at: datetime, now: datetime) -> list[dict]:
    by_date: defaultdict[str, int] = defaultdict(int)
    for record in records:
        created_at = _aware(record.created_at)
        key = created_at.date().isoformat()
        by_date[key] += record.duration_seconds if record.duration_seconds is not None else ACTIVITY_DURATION_FALLBACKS.get(record.activity_type, 60)
    labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    start_date = start_at.date()
    return [{
        "day": labels[(start_date + timedelta(days=i)).weekday()],
        "date": (start_date + timedelta(days=i)).isoformat(),
        "hours": round(by_date[(start_date + timedelta(days=i)).isoformat()] / 3600, 2),
    } for i in range((now.date() - start_date).days + 1)]


def _question_count(db: Session, user_id: str, class_id: str, start_at: datetime) -> int:
    return db.query(ChatMessage).join(ChatSession, ChatSession.id == ChatMessage.session_id).filter(
        ChatSession.user_id == user_id,
        ChatSession.class_id == class_id,
        ChatSession.is_active == True,
        ChatMessage.role == "user",
        ChatMessage.created_at >= start_at,
    ).count()


def _task_stats(db: Session, user_id: str, class_id: str, start_at: Optional[datetime] = None) -> tuple[int, int, float]:
    task_query = db.query(Task).filter(Task.class_id == class_id, Task.is_published == True)
    if start_at:
        task_query = task_query.filter(Task.created_at >= start_at)
    tasks = task_query.all()
    task_ids = [task.id for task in tasks]
    completed = 0
    if task_ids:
        completed = db.query(Submission).filter(
            Submission.student_id == user_id,
            Submission.task_id.in_(task_ids),
        ).count()
    return len(tasks), completed, completed / max(1, len(tasks))


def _flashcards(db: Session, user_id: str, class_id: str) -> list[Flashcard]:
    return db.query(Flashcard).filter(
        Flashcard.user_id == user_id,
        Flashcard.class_id == class_id,
        Flashcard.is_active == True,
    ).order_by(Flashcard.created_at.asc()).all()


def _flashcard_due(card: Flashcard) -> bool:
    if not card.next_review_at:
        return True
    return _aware(card.next_review_at) <= datetime.now(timezone.utc)


def _flashcard_to_frontend(card: Flashcard) -> dict:
    return {
        "id": card.id,
        "front": card.question,
        "back": card.answer,
        "due": _flashcard_due(card),
        "nextReviewAt": _iso(card.next_review_at) if card.next_review_at else None,
        "reviewCount": card.review_count or 0,
    }


def _flashcard_review_count(db: Session, user_id: str, start_at: datetime, class_id: str) -> int:
    return db.query(FlashcardRecord).join(Flashcard, Flashcard.id == FlashcardRecord.flashcard_id).filter(
        FlashcardRecord.user_id == user_id,
        Flashcard.class_id == class_id,
        FlashcardRecord.reviewed_at >= start_at,
    ).count()


def _mistakes(db: Session, user_id: str, class_id: str) -> list[StudyMistake]:
    return db.query(StudyMistake).filter(
        StudyMistake.user_id == user_id,
        StudyMistake.class_id == class_id,
    ).order_by(StudyMistake.updated_at.desc()).all()


def _concept_mastery_rows(db: Session, user_id: str, class_id: str) -> list[StudentConceptMastery]:
    return db.query(StudentConceptMastery).filter(
        StudentConceptMastery.user_id == user_id,
        StudentConceptMastery.class_id == class_id,
    ).order_by(StudentConceptMastery.mastery_score.asc()).all()


def _build_radar_data(
    *,
    task_rate: float,
    question_count: int,
    flashcard_count: int,
    flashcard_reviews: int,
    mistakes: list[StudyMistake],
    records: list[LearningRecord],
    mastery_rows: list[StudentConceptMastery],
) -> list[dict]:
    avg_mastery = sum(row.mastery_score for row in mastery_rows) / len(mastery_rows) if mastery_rows else 0.68
    mistake_mastery = sum(1 for item in mistakes if item.mastered) / max(1, len(mistakes))
    return [
        {"label": "概念理解", "score": _clamp(round(avg_mastery * 100)), "fullScore": 100},
        {"label": "作业表现", "score": _clamp(round(task_rate * 100)), "fullScore": 100},
        {"label": "错题修复", "score": _clamp(round((0.55 + mistake_mastery * 0.45) * 100)) if mistakes else 72, "fullScore": 100},
        {"label": "闪卡记忆", "score": _clamp(round(min(1, flashcard_reviews / max(6, flashcard_count)) * 100)) if flashcard_count else 60, "fullScore": 100},
        {"label": "学习稳定", "score": _clamp(round(len({r.created_at.date() for r in records}) / 14 * 100)), "fullScore": 100},
        {"label": "AI探究", "score": _clamp(question_count * 8), "fullScore": 100},
    ]


def _build_keyword_data(db: Session, user_id: str, class_id: str) -> list[dict]:
    texts = [
        row.content or "" for row in db.query(ChatMessage).join(ChatSession, ChatSession.id == ChatMessage.session_id).filter(
            ChatSession.user_id == user_id,
            ChatSession.class_id == class_id,
            ChatSession.is_active == True,
            ChatMessage.role == "user",
        ).order_by(ChatMessage.created_at.desc()).limit(120).all()
    ]
    texts.extend(
        item.question_content or ""
        for item in db.query(ReviewItem)
        .join(ChatMessage, ChatMessage.id == ReviewItem.message_id)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .filter(
            ReviewItem.student_id == user_id,
            ReviewItem.class_id == class_id,
            ChatSession.is_active == True,
        )
        .limit(80)
        .all()
    )
    counts: Counter[str] = Counter()
    course_terms = _course_keyword_terms(db, class_id)
    for text in texts:
        for token in _extract_question_keywords(text, course_terms):
            counts[token] += 1
    return [{"word": word, "count": count} for word, count in counts.most_common(36)]


def _build_chapter_progress(db: Session, user_id: str, class_id: str, radar_data: list[dict]) -> list[dict]:
    chapter_scores: dict[str, list[float]] = defaultdict(list)
    for row in _concept_mastery_rows(db, user_id, class_id):
        concept = db.query(LearningConcept).filter(LearningConcept.id == row.concept_id).first() if row.concept_id else None
        chapter_scores[(concept.chapter if concept and concept.chapter else "核心知识")].append(row.mastery_score * 100)
    for mistake in _mistakes(db, user_id, class_id):
        if mistake.chapter:
            chapter_scores[mistake.chapter].append(85 if mistake.mastered else 55)
    if not chapter_scores:
        materials = db.query(Material).filter(Material.class_id == class_id, Material.is_active == True).order_by(Material.created_at.asc()).limit(6).all()
        base = sum(item["score"] for item in radar_data) / max(1, len(radar_data))
        for material in materials:
            chapter_scores[material.title[:24]].append(base)
    if not chapter_scores:
        chapter_scores["课程基础"].append(sum(item["score"] for item in radar_data) / max(1, len(radar_data)))
    result = []
    for chapter, values in list(chapter_scores.items())[:8]:
        progress = _clamp(round(sum(values) / max(1, len(values))))
        result.append({
            "name": chapter,
            "progress": progress,
            "status": "done" if progress >= 90 else ("active" if progress >= 55 else "todo"),
        })
    return result


def _weak_topics_from_evidence(db: Session, user_id: str, class_id: str) -> list[str]:
    counts: Counter[str] = Counter()
    for item in _mistakes(db, user_id, class_id):
        for token in _topic_tokens(" ".join([item.chapter or "", item.question or "", item.analysis or ""])):
            counts[token] += 2 if not item.mastered else 1
    for row in _concept_mastery_rows(db, user_id, class_id)[:6]:
        if row.mastery_score < 0.75:
            counts[row.concept_name] += 3
    return [topic for topic, _ in counts.most_common(5)]


def _strong_topics_from_mastery(db: Session, user_id: str, class_id: str) -> list[str]:
    rows = db.query(StudentConceptMastery).filter(
        StudentConceptMastery.user_id == user_id,
        StudentConceptMastery.class_id == class_id,
    ).order_by(StudentConceptMastery.mastery_score.desc()).limit(5).all()
    return [row.concept_name for row in rows if row.mastery_score >= 0.75]


def _build_suggestions(weak_topics: list[str], question_count: int, task_rate: float, hours: float, period: str) -> list[str]:
    suggestions = []
    if weak_topics:
        suggestions.append(f"优先复习 {weak_topics[0]}，建议结合教师纠正答案和课程资料重新梳理。")
    if question_count < (3 if period == "weekly" else 10):
        suggestions.append("AI 提问次数偏少，可以把不确定的概念拆成小问题逐个追问。")
    if task_rate < 0.8:
        suggestions.append("任务完成率还有提升空间，建议先补齐未完成任务再做拓展练习。")
    if hours < (4 if period == "weekly" else 16):
        suggestions.append("学习时长偏低，建议设置固定学习时段，保持连续活跃。")
    return suggestions or ["本阶段学习状态稳定，建议继续保持并尝试整理阶段性知识框架。"]


def _build_highlights(strong_topics: list[str], task_rate: float, flashcard_reviews: int, period: str) -> list[str]:
    highlights = []
    if strong_topics:
        highlights.append(f"掌握较好的知识点：{'、'.join(strong_topics[:3])}")
    if task_rate >= 0.9:
        highlights.append("任务完成情况良好，学习执行力稳定。")
    if flashcard_reviews >= (10 if period == "weekly" else 30):
        highlights.append("闪卡复习频率较高，有助于长期记忆保持。")
    return highlights or ["已形成基础学习记录，继续积累后画像会更准确。"]


def _topic_tokens(text: str) -> list[str]:
    return _extract_question_keywords(text, [])


QUESTION_STOP_PATTERNS = [
    r"帮我", r"请问", r"请你", r"能不能", r"可以", r"是否", r"为什么", r"怎么样", r"是什么",
    r"有没有", r"有什么", r"有吗", r"会发生什么", r"发生什么", r"会发生", r"吗", r"呢", r"呀", r"请", r"为我", r"给我", r"介绍", r"解释",
    r"分析", r"总结", r"讲讲", r"说说", r"一下", r"这个", r"那个", r"这些", r"那些",
    r"内容", r"里面", r"其中", r"相关", r"问题", r"回答", r"生成", r"帮助", r"学习",
    r"这张图", r"图片", r"图里", r"里有", r"今天", r"天气", r"你好", r"您好",
]
KEYWORD_STOP_WORDS = {
    "什么", "如何", "为什么", "怎么样", "是什么", "有没有", "有什么", "有吗", "你好", "您好", "会",
    "内容", "问题", "回答", "分析", "解释", "介绍", "总结", "帮我", "请问",
}
ENGLISH_STOP_WORDS = {
    "what", "why", "how", "when", "where", "which", "who", "please", "and", "or", "the",
    "for", "with", "about", "tell", "explain", "show", "help", "in", "on", "to", "of", "a", "an",
    "pdf", "doc", "docx", "ppt",
    "image", "picture", "content", "is", "are", "me", "my", "understand", "start", "slow",
    "test", "testing", "selection", "table", "one", "two", "three", "first", "second",
}
CHINESE_KEYWORD_SUFFIXES = (
    "算法", "协议", "机制", "模型", "公式", "定理", "方法", "过程", "原理", "概念",
    "控制", "网络", "数据", "结构", "函数", "系统", "路由", "窗口", "阈值", "报文",
    "传输", "连接", "拥塞", "确认", "超时", "重传", "慢启动", "吞吐量",
)


def _course_keyword_terms(db: Session, class_id: str) -> list[str]:
    terms: set[str] = set()
    concept_rows = db.query(LearningConcept.concept_name).filter(LearningConcept.class_id == class_id).limit(200).all()
    entity_rows = db.query(KnowledgeEntity.name).filter(KnowledgeEntity.class_id == class_id).limit(300).all()
    for row in [*concept_rows, *entity_rows]:
        name = str(row[0] or "").strip()
        if _is_good_keyword(name):
            terms.add(_format_keyword(name))
    return sorted(terms, key=len, reverse=True)


def _extract_question_keywords(text: str, course_terms: list[str]) -> list[str]:
    normalized = _normalize_question_text(text)
    if not normalized:
        return []

    found: list[str] = []
    lowered = normalized.lower()
    matched_terms: list[str] = []
    for term in course_terms:
        if term and term.lower() in lowered:
            found.append(term)
            matched_terms.append(term)

    for token in re.findall(r"[A-Za-z][A-Za-z0-9+#._-]{1,}", normalized):
        token = token.strip("._-").upper() if len(token) <= 6 else token.strip("._-")
        token_lower = token.lower()
        if token_lower in ENGLISH_STOP_WORDS:
            continue
        if any(" " in term and token_lower in term.lower().split() for term in matched_terms):
            continue
        if _is_good_keyword(token):
            found.append(token)

    chinese_chunks = re.split(r"[^A-Za-z0-9+#._\-\u4e00-\u9fff]+", normalized)
    for chunk in chinese_chunks:
        chunk = re.sub(r"[A-Za-z0-9+#._-]+", "", chunk)
        chunk = chunk.strip()
        if not chunk:
            continue
        found.extend(_extract_chinese_keyword_candidates(chunk))

    deduped: list[str] = []
    seen: set[str] = set()
    for item in found:
        item = _clean_keyword(item)
        key = item.lower()
        if key not in seen and _is_good_keyword(item):
            seen.add(key)
            deduped.append(item)
    return deduped[:6]


def _normalize_question_text(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"https?://\S+|[\w.+-]+@[\w.-]+\.\w+", " ", value)
    value = re.sub(r"\b1[3-9]\d{9}\b|\b\d{8,}\b", " ", value)
    for pattern in QUESTION_STOP_PATTERNS:
        value = re.sub(pattern, " ", value, flags=re.I)
    value = re.sub(r"[?？!！,，。；;：:（）()【】\[\]《》<>“”\"'、/\\|]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _extract_chinese_keyword_candidates(chunk: str) -> list[str]:
    candidates: list[str] = []
    if _is_good_keyword(chunk) and len(chunk) <= 8:
        candidates.append(chunk)
    for suffix in CHINESE_KEYWORD_SUFFIXES:
        idx = chunk.find(suffix)
        while idx >= 0:
            start = max(0, idx - 4)
            candidate = chunk[start: idx + len(suffix)]
            if _is_good_keyword(candidate):
                candidates.append(candidate)
            idx = chunk.find(suffix, idx + 1)
    return candidates


def _clean_keyword(keyword: str) -> str:
    value = str(keyword or "").strip()
    for pattern in QUESTION_STOP_PATTERNS:
        value = re.sub(pattern, "", value, flags=re.I)
    value = re.sub(r"^\d*个", "", value)
    return _format_keyword(value.strip())


def _format_keyword(keyword: str) -> str:
    value = str(keyword or "").strip()
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9+#._-]{1,}", value) and len(value) <= 8:
        return value.upper()
    return value


def _is_good_keyword(keyword: str) -> bool:
    value = str(keyword or "").strip()
    if not value or value in KEYWORD_STOP_WORDS:
        return False
    if len(value) < 2 or len(value) > 16:
        return False
    if re.fullmatch(r"[\d\s\W_]+", value):
        return False
    if value.lower() in ENGLISH_STOP_WORDS:
        return False
    if value in {"这张", "图的", "图里", "里面", "内容", "今天", "天气"}:
        return False
    if re.search(r"[\u4e00-\u9fff]", value) and any(part in value for part in {"的", "里", "表格", "阶段的"}):
        return False
    if value.startswith("个") or value.endswith("会"):
        return False
    if any(stop in value for stop in KEYWORD_STOP_WORDS):
        return False
    return True


def _mistake_to_frontend(item: StudyMistake) -> dict:
    extra = item.extra_data if isinstance(item.extra_data, dict) else {}
    return {
        "id": item.id,
        "question": item.question,
        "chapter": item.chapter or "未分类",
        "wrongCount": item.wrong_count or 1,
        "myAnswer": item.my_answer or "",
        "correctAnswer": item.correct_answer or "",
        "analysis": item.analysis or "",
        "addTime": _date_text(item.created_at),
        "lastPracticeTime": _date_text(item.last_practice_at),
        "mastered": bool(item.mastered),
        "source": extra.get("source"),
        "sourceTaskId": extra.get("task_id"),
        "sourceTaskTitle": extra.get("task_title"),
        "sourceTaskType": extra.get("task_type"),
        "sourceSubmissionId": extra.get("submission_id"),
        "sourceQuestionId": extra.get("question_id"),
    }


def _range_label(start_at: datetime, now: datetime, period: str) -> str:
    if period == "weekly":
        return f"{start_at:%Y.%m.%d} - {now:%m.%d}"
    return f"{now:%Y年%m月}"


def _date_text(value: Optional[datetime]) -> str:
    return date_app_timezone(_aware(value)) if value else ""


def _iso(value: Optional[datetime]) -> str:
    return isoformat_app_timezone(_aware(value)) if value else ""


def _aware(value: Optional[datetime]) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _clamp(value: int | float, lower: int = 0, upper: int = 100) -> int:
    return int(max(lower, min(upper, value)))
