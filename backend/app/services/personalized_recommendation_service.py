"""Personalized recommendation orchestration for student learning surfaces."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.analytics import LearningRecord, StudentProfile, StudyMistake
from app.models.chat import ChatMessage, ChatSession, ReviewItem
from app.models.course import Class, ClassMember, Material, Task
from app.models.knowledge import Flashcard
from app.models.personalization import LearningConcept, LearningResourceLink, RecommendationEvent, StudentConceptMastery
from app.models.user import User
from app.services import analytics_service, learning_path_service
from app.services.student_learning_service import resolve_learning_class


SURFACE_LABELS = {
    "dashboard": "今日建议",
    "ai_panel": "相关学习推荐",
    "my_learning": "个性化复习推荐",
    "after_answer": "下一步学习",
    "report": "报告建议",
}

SURFACE_TYPE_ORDER = {
    "dashboard": ["path", "material", "task", "flashcard", "mistake", "concept", "faq", "followup"],
    "ai_panel": ["material", "faq", "concept", "followup", "path", "flashcard", "mistake", "task"],
    "my_learning": ["concept", "path", "mistake", "flashcard", "material", "faq", "task", "followup"],
    "after_answer": ["followup", "material", "faq", "concept", "flashcard", "mistake", "path", "task"],
    "report": ["path", "concept", "material", "mistake", "flashcard", "task", "faq", "followup"],
}


@dataclass
class PersonalizedCandidate:
    target_id: str
    target_type: str
    title: str
    description: str = ""
    reason: str = ""
    score: float = 0.5
    action_type: str = "view"
    action_label: str = "查看"
    evidence: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def get_personalized_recommendations(
    db: Session,
    student: User,
    *,
    course_id: str | None = None,
    class_id: str | None = None,
    surface: str = "dashboard",
    limit: int = 6,
    context_query: str | None = None,
) -> dict[str, Any]:
    """Return mixed, explainable recommendations for a student-facing surface."""

    cls = _resolve_recommendation_class(db, student, course_id=course_id, class_id=class_id)
    normalized_surface = surface if surface in SURFACE_LABELS else "dashboard"
    requested_limit = max(1, min(int(limit or 6), 20))

    profile = db.query(StudentProfile).filter(StudentProfile.user_id == student.id).first()
    weak_terms = _build_weak_terms(db, student_id=student.id, class_id=cls.id, profile=profile, context_query=context_query)
    recent_terms = _recent_question_terms(db, student_id=student.id, class_id=cls.id)
    all_terms = _dedupe_terms([*weak_terms, *recent_terms])
    event_state = _recommendation_event_state(db, user_id=student.id, class_id=cls.id)

    candidates: list[PersonalizedCandidate] = []
    candidates.extend(_resource_link_candidates(db, student_id=student.id, class_id=cls.id, terms=all_terms))
    candidates.extend(_material_candidates(db, class_id=cls.id, terms=all_terms))
    candidates.extend(_concept_candidates(db, student_id=student.id, class_id=cls.id, terms=all_terms))
    candidates.extend(_mistake_candidates(db, student_id=student.id, class_id=cls.id, terms=all_terms))
    candidates.extend(_flashcard_candidates(db, student_id=student.id, class_id=cls.id, terms=all_terms))
    candidates.extend(_task_candidates(db, class_id=cls.id, terms=all_terms))
    candidates.extend(_teacher_faq_candidates(db, class_id=cls.id, terms=all_terms))
    candidates.extend(_learning_path_candidates(db, student_id=student.id, class_id=cls.id))
    candidates.extend(_followup_candidates(terms=all_terms, context_query=context_query))

    ranked = _rank_and_shape(
        candidates,
        surface=normalized_surface,
        event_state=event_state,
        limit=requested_limit,
    )
    return {
        "items": ranked,
        "context": {
            "surface": normalized_surface,
            "surfaceLabel": SURFACE_LABELS[normalized_surface],
            "courseId": cls.course_id,
            "classId": cls.id,
            "className": cls.name,
            "weakTerms": weak_terms[:8],
            "recentTerms": recent_terms[:8],
            "algorithm": "personalized_mixed_rules_v1",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        },
    }


def _resolve_recommendation_class(
    db: Session,
    student: User,
    *,
    course_id: str | None,
    class_id: str | None,
) -> Class:
    if class_id:
        return resolve_learning_class(db, student, class_id)
    if course_id:
        return resolve_learning_class(db, student, course_id)
    membership = (
        db.query(ClassMember)
        .join(Class, Class.id == ClassMember.class_id)
        .filter(
            ClassMember.user_id == student.id,
            Class.is_active == True,
        )
        .order_by(Class.created_at.desc())
        .first()
    )
    if membership:
        return membership.cls
    return resolve_learning_class(db, student, "")


def _build_weak_terms(
    db: Session,
    *,
    student_id: str,
    class_id: str,
    profile: StudentProfile | None,
    context_query: str | None,
) -> list[str]:
    terms: list[str] = []
    if profile and isinstance(profile.weak_topics, list):
        terms.extend(str(item) for item in profile.weak_topics if str(item).strip())
    if context_query:
        terms.extend(analytics_service.extract_terms_for_recommendation(context_query))

    mastery_rows = (
        db.query(StudentConceptMastery)
        .filter(
            StudentConceptMastery.user_id == student_id,
            StudentConceptMastery.class_id == class_id,
        )
        .order_by(StudentConceptMastery.mastery_score.asc(), StudentConceptMastery.evidence_count.desc())
        .limit(10)
        .all()
    )
    for row in mastery_rows:
        if float(row.mastery_score or 0.0) < 0.72:
            terms.append(row.concept_name)

    mistakes = (
        db.query(StudyMistake)
        .filter(
            StudyMistake.user_id == student_id,
            StudyMistake.class_id == class_id,
            StudyMistake.mastered == 0,
        )
        .order_by(StudyMistake.updated_at.desc())
        .limit(8)
        .all()
    )
    for item in mistakes:
        terms.extend(analytics_service.extract_terms_for_recommendation(" ".join([
            item.chapter or "",
            item.question or "",
            item.analysis or "",
        ])))
    return _dedupe_terms(terms)


def _recent_question_terms(db: Session, *, student_id: str, class_id: str) -> list[str]:
    since = datetime.now(timezone.utc) - timedelta(days=30)
    rows = (
        db.query(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .filter(
            ChatSession.user_id == student_id,
            ChatSession.class_id == class_id,
            ChatSession.is_active == True,
            ChatMessage.role == "user",
            ChatMessage.created_at >= since,
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(30)
        .all()
    )
    terms: list[str] = []
    for row in rows:
        terms.extend(analytics_service.extract_terms_for_recommendation(row.content or ""))
    return _dedupe_terms(terms)


def _resource_link_candidates(
    db: Session,
    *,
    student_id: str,
    class_id: str,
    terms: list[str],
) -> list[PersonalizedCandidate]:
    mastery_by_concept = {
        row.concept_id: row
        for row in db.query(StudentConceptMastery)
        .filter(StudentConceptMastery.user_id == student_id, StudentConceptMastery.class_id == class_id)
        .all()
        if row.concept_id
    }
    rows = (
        db.query(LearningResourceLink)
        .filter(LearningResourceLink.class_id == class_id)
        .order_by(LearningResourceLink.relevance.desc(), LearningResourceLink.created_at.desc())
        .limit(80)
        .all()
    )
    candidates: list[PersonalizedCandidate] = []
    for row in rows:
        mastery = mastery_by_concept.get(row.concept_id)
        gap = 1.0 - float(mastery.mastery_score) if mastery else 0.45
        score = 0.35 + _clamp01(row.relevance) * 0.35 + _clamp01(gap) * 0.2 + _text_match(row.title or "", terms) * 0.1
        candidates.append(PersonalizedCandidate(
            target_id=row.resource_id,
            target_type=_normalize_target_type(row.resource_type),
            title=row.title or "课程资源",
            description=_description_for_resource_type(row.resource_type),
            reason=_join_reason([
                "关联到你的薄弱知识点" if gap >= 0.35 else "",
                "与课程知识图谱资源链接匹配",
            ]),
            score=score,
            action_type=_action_for_type(row.resource_type),
            action_label=_action_label_for_type(row.resource_type),
            evidence={
                "conceptId": row.concept_id,
                "masteryScore": round(float(mastery.mastery_score), 3) if mastery else None,
                "relevance": round(float(row.relevance or 0.0), 3),
            },
            metadata=row.extra_data or {},
        ))
    return candidates


def _material_candidates(db: Session, *, class_id: str, terms: list[str]) -> list[PersonalizedCandidate]:
    rows = (
        db.query(Material)
        .filter(Material.class_id == class_id, Material.is_active == True)
        .order_by(Material.updated_at.desc())
        .limit(50)
        .all()
    )
    candidates: list[PersonalizedCandidate] = []
    for row in rows:
        match = _text_match(" ".join([row.title or "", row.description or "", row.file_name or ""]), terms)
        indexed_bonus = 0.12 if row.kb_status == "indexed" else 0.0
        recent_bonus = _recency_score(row.updated_at or row.created_at)
        score = 0.35 + match * 0.32 + indexed_bonus + recent_bonus * 0.16
        candidates.append(PersonalizedCandidate(
            target_id=row.id,
            target_type="material",
            title=row.title or row.file_name or "课程资料",
            description=_compact_text(row.description or f"{row.file_type or '资料'} · {row.kb_status or '待索引'}", 96),
            reason=_join_reason([
                "与你最近关注的关键词匹配" if match >= 0.2 else "",
                "已进入课程知识库" if row.kb_status == "indexed" else "课程资料可用于补充学习",
            ]),
            score=score,
            action_type="open_material",
            action_label="查看资料",
            evidence={
                "kbStatus": row.kb_status,
                "fileType": row.file_type,
                "matchScore": round(match, 3),
            },
        ))
    return candidates


def _concept_candidates(db: Session, *, student_id: str, class_id: str, terms: list[str]) -> list[PersonalizedCandidate]:
    mastery_rows = {
        row.concept_id: row
        for row in db.query(StudentConceptMastery)
        .filter(StudentConceptMastery.user_id == student_id, StudentConceptMastery.class_id == class_id)
        .all()
        if row.concept_id
    }
    rows = (
        db.query(LearningConcept)
        .filter(LearningConcept.class_id == class_id)
        .order_by(LearningConcept.importance.desc(), LearningConcept.difficulty.asc())
        .limit(80)
        .all()
    )
    candidates: list[PersonalizedCandidate] = []
    for row in rows:
        mastery = mastery_rows.get(row.id)
        mastery_score = float(mastery.mastery_score) if mastery else 0.5
        gap = 1.0 - mastery_score
        match = _text_match(row.concept_name or "", terms)
        score = 0.22 + gap * 0.35 + float(row.importance or 0.5) * 0.2 + match * 0.2
        if gap < 0.2 and match <= 0:
            continue
        candidates.append(PersonalizedCandidate(
            target_id=row.id,
            target_type="concept",
            title=row.concept_name,
            description=_join_reason([
                f"掌握度约 {int(mastery_score * 100)}%" if mastery else "暂无充分掌握度证据",
                f"难度 {int(float(row.difficulty or 0.5) * 100)}%",
            ]),
            reason=_join_reason([
                "该知识点掌握度偏低" if gap >= 0.35 else "",
                "与你最近的提问主题相关" if match > 0 else "",
                "在课程知识图谱中较重要" if float(row.importance or 0.0) >= 0.65 else "",
            ]),
            score=score,
            action_type="ask_ai",
            action_label="让 AI 讲解",
            evidence={
                "masteryScore": round(mastery_score, 3),
                "importance": round(float(row.importance or 0.0), 3),
                "difficulty": round(float(row.difficulty or 0.0), 3),
            },
        ))
    return candidates


def _mistake_candidates(db: Session, *, student_id: str, class_id: str, terms: list[str]) -> list[PersonalizedCandidate]:
    rows = (
        db.query(StudyMistake)
        .filter(StudyMistake.user_id == student_id, StudyMistake.class_id == class_id, StudyMistake.mastered == 0)
        .order_by(StudyMistake.wrong_count.desc(), StudyMistake.updated_at.desc())
        .limit(20)
        .all()
    )
    candidates: list[PersonalizedCandidate] = []
    for row in rows:
        text = " ".join([row.chapter or "", row.question or "", row.analysis or ""])
        match = _text_match(text, terms)
        score = 0.48 + min(float(row.wrong_count or 1), 5.0) * 0.06 + match * 0.2
        candidates.append(PersonalizedCandidate(
            target_id=row.id,
            target_type="mistake",
            title=_compact_text(row.question, 48),
            description=_compact_text(row.analysis or row.correct_answer or "这道错题还没有标记掌握。", 96),
            reason=_join_reason([
                "这道错题尚未掌握",
                f"累计出错 {row.wrong_count or 1} 次" if (row.wrong_count or 1) > 1 else "",
            ]),
            score=score,
            action_type="review_mistake",
            action_label="复习错题",
            evidence={"wrongCount": row.wrong_count or 1, "chapter": row.chapter},
        ))
    return candidates


def _flashcard_candidates(db: Session, *, student_id: str, class_id: str, terms: list[str]) -> list[PersonalizedCandidate]:
    now = datetime.now(timezone.utc)
    rows = (
        db.query(Flashcard)
        .filter(
            Flashcard.user_id == student_id,
            Flashcard.class_id == class_id,
            Flashcard.is_active == True,
            or_(Flashcard.next_review_at == None, Flashcard.next_review_at <= now),
        )
        .order_by(Flashcard.next_review_at.asc(), Flashcard.updated_at.desc())
        .limit(20)
        .all()
    )
    candidates: list[PersonalizedCandidate] = []
    for row in rows:
        tags = row.tags if isinstance(row.tags, list) else []
        match = _text_match(" ".join([row.question or "", " ".join(map(str, tags))]), terms)
        score = 0.44 + match * 0.18 + min(float(row.review_count or 0), 5.0) * 0.025
        candidates.append(PersonalizedCandidate(
            target_id=row.id,
            target_type="flashcard",
            title=_compact_text(row.question, 50),
            description="到期闪卡，适合用 1-2 分钟快速巩固。",
            reason=_join_reason(["这张闪卡已经到复习时间", "主题与你最近学习内容相关" if match > 0 else ""]),
            score=score,
            action_type="review_flashcard",
            action_label="复习闪卡",
            evidence={"tags": tags, "reviewCount": row.review_count or 0},
        ))
    return candidates


def _task_candidates(db: Session, *, class_id: str, terms: list[str]) -> list[PersonalizedCandidate]:
    now = datetime.now(timezone.utc)
    rows = (
        db.query(Task)
        .filter(Task.class_id == class_id, Task.is_published == True)
        .order_by(Task.due_date.asc(), Task.created_at.desc())
        .limit(20)
        .all()
    )
    candidates: list[PersonalizedCandidate] = []
    for row in rows:
        match = _text_match(" ".join([row.title or "", row.description or ""]), terms)
        due_score = 0.0
        if row.due_date:
            due_date = row.due_date
            if due_date.tzinfo is None:
                due_date = due_date.replace(tzinfo=timezone.utc)
            days = max(0.0, (due_date - now).total_seconds() / 86400)
            due_score = 1.0 if days <= 2 else 0.6 if days <= 7 else 0.2
        score = 0.32 + match * 0.2 + due_score * 0.25
        candidates.append(PersonalizedCandidate(
            target_id=row.id,
            target_type="task",
            title=row.title,
            description=_compact_text(row.description or f"{row.task_type or '任务'} · 满分 {row.max_score or 100}", 96),
            reason=_join_reason([
                "任务临近截止" if due_score >= 0.6 else "",
                "任务内容与你的关注主题相关" if match > 0 else "课程任务建议及时完成",
            ]),
            score=score,
            action_type="open_task",
            action_label="查看任务",
            evidence={"dueDate": row.due_date.isoformat() if row.due_date else None, "taskType": row.task_type},
        ))
    return candidates


def _teacher_faq_candidates(db: Session, *, class_id: str, terms: list[str]) -> list[PersonalizedCandidate]:
    rows = (
        db.query(ReviewItem)
        .filter(
            ReviewItem.class_id == class_id,
            ReviewItem.status == "resolved",
            ReviewItem.teacher_answer.isnot(None),
        )
        .order_by(ReviewItem.reviewed_at.desc(), ReviewItem.created_at.desc())
        .limit(40)
        .all()
    )
    candidates: list[PersonalizedCandidate] = []
    for row in rows:
        text = " ".join([row.question_content or "", row.teacher_answer or ""])
        match = _text_match(text, terms)
        if match <= 0 and terms:
            continue
        score = 0.45 + match * 0.35
        candidates.append(PersonalizedCandidate(
            target_id=row.id,
            target_type="faq",
            title=_compact_text(row.question_content, 52),
            description=_compact_text(row.teacher_answer or "", 112),
            reason="教师已经审核修正，适合作为可靠参考。",
            score=score,
            action_type="ask_ai",
            action_label="围绕它追问",
            evidence={"reviewId": row.id, "trigger": row.trigger},
        ))
    return candidates


def _learning_path_candidates(db: Session, *, student_id: str, class_id: str) -> list[PersonalizedCandidate]:
    try:
        payload = learning_path_service.generate_learning_path_for_student(
            db,
            user_id=student_id,
            class_id=class_id,
            max_steps=3,
            persist=False,
        )
    except Exception:
        return []
    candidates: list[PersonalizedCandidate] = []
    for step in payload.get("steps") or []:
        concept_name = str(step.get("concept_name") or "学习路径")
        signals = step.get("evidence_signals") or {}
        score = 0.45 + float(signals.get("mastery_gap") or 0.0) * 0.25 + float(signals.get("importance") or 0.0) * 0.15
        candidates.append(PersonalizedCandidate(
            target_id=str(step.get("concept_id") or _short_hash(concept_name)),
            target_type="path",
            title=f"学习路径：{concept_name}",
            description=_compact_text(step.get("goal") or "按推荐顺序补齐这个知识点。", 96),
            reason=_translate_path_reason(str(step.get("reason") or "")),
            score=score,
            action_type="open_learning_path",
            action_label="查看路径",
            evidence={"step": step.get("step"), "signals": signals, "resources": step.get("recommended_resources") or []},
        ))
    return candidates


def _followup_candidates(*, terms: list[str], context_query: str | None) -> list[PersonalizedCandidate]:
    focus_terms = terms[:4]
    if not focus_terms and context_query:
        focus_terms = analytics_service.extract_terms_for_recommendation(context_query)[:4]
    if not focus_terms:
        return []
    candidates: list[PersonalizedCandidate] = []
    templates = [
        ("概念辨析", "请用对比表解释 {term} 的核心概念和常见误区"),
        ("例题演练", "请围绕 {term} 出一道分步骤练习题并讲解答案"),
        ("知识关联", "请说明 {term} 与课程中哪些知识点存在先修或因果关系"),
    ]
    for index, term in enumerate(focus_terms[:3]):
        title, prompt = templates[index % len(templates)]
        candidates.append(PersonalizedCandidate(
            target_id=_short_hash(f"{title}:{term}"),
            target_type="followup",
            title=f"{title}：{term}",
            description=prompt.format(term=term),
            reason="基于你最近的提问关键词生成，适合作为下一步追问。",
            score=0.52 - index * 0.03,
            action_type="ask_ai",
            action_label="继续追问",
            evidence={"term": term, "prompt": prompt.format(term=term)},
        ))
    return candidates


def _rank_and_shape(
    candidates: list[PersonalizedCandidate],
    *,
    surface: str,
    event_state: dict[str, dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    order = SURFACE_TYPE_ORDER.get(surface) or SURFACE_TYPE_ORDER["dashboard"]
    order_weight = {target_type: (len(order) - index) / len(order) for index, target_type in enumerate(order)}
    deduped: dict[tuple[str, str], PersonalizedCandidate] = {}
    for item in candidates:
        key = _candidate_dedupe_key(item)
        previous = deduped.get(key)
        if previous is None or item.score > previous.score:
            deduped[key] = item

    ranked: list[tuple[float, PersonalizedCandidate]] = []
    for item in deduped.values():
        state = event_state.get(f"{item.target_type}:{item.target_id}", {})
        penalty = 0.0
        if state.get("dismissed"):
            penalty += 0.35
        if state.get("completed"):
            penalty += 0.2
        if state.get("recent_impressions", 0) >= 3:
            penalty += 0.12
        surface_bonus = order_weight.get(item.target_type, 0.35) * 0.12
        ranked.append((_clamp01(item.score + surface_bonus - penalty), item))

    ranked.sort(key=lambda pair: pair[0], reverse=True)
    selected = _diversify(ranked, limit=limit)
    return [_shape_item(item, score=score, surface=surface) for score, item in selected]


def _candidate_dedupe_key(item: PersonalizedCandidate) -> tuple[str, str]:
    title_key = " ".join((item.title or "").lower().split())
    if item.target_type in {"faq", "followup", "concept", "path"} and title_key:
        return (item.target_type, title_key)
    return (item.target_type, item.target_id)


def _diversify(
    ranked: list[tuple[float, PersonalizedCandidate]],
    *,
    limit: int,
) -> list[tuple[float, PersonalizedCandidate]]:
    selected: list[tuple[float, PersonalizedCandidate]] = []
    type_counts: dict[str, int] = {}
    for score, item in ranked:
        if type_counts.get(item.target_type, 0) >= 3:
            continue
        selected.append((score, item))
        type_counts[item.target_type] = type_counts.get(item.target_type, 0) + 1
        if len(selected) >= limit:
            break
    if len(selected) < limit:
        selected_keys = {(item.target_type, item.target_id) for _, item in selected}
        for score, item in ranked:
            if (item.target_type, item.target_id) in selected_keys:
                continue
            selected.append((score, item))
            if len(selected) >= limit:
                break
    return selected


def _shape_item(item: PersonalizedCandidate, *, score: float, surface: str) -> dict[str, Any]:
    relevance = int(round(_clamp01(score) * 100))
    return {
        "id": f"{item.target_type}:{item.target_id}",
        "targetId": item.target_id,
        "type": item.target_type,
        "title": item.title,
        "description": item.description,
        "reason": item.reason or "根据你的学习记录和课程内容推荐。",
        "relevance": relevance,
        "score": round(_clamp01(score), 4),
        "surface": surface,
        "action": {
            "type": item.action_type,
            "label": item.action_label,
            "payload": {
                "targetId": item.target_id,
                "targetType": item.target_type,
                **(item.metadata or {}),
            },
        },
        "evidence": item.evidence,
        "metadata": item.metadata,
    }


def _recommendation_event_state(db: Session, *, user_id: str, class_id: str) -> dict[str, dict[str, Any]]:
    since = datetime.now(timezone.utc) - timedelta(days=14)
    rows = (
        db.query(RecommendationEvent)
        .filter(
            RecommendationEvent.user_id == user_id,
            RecommendationEvent.class_id == class_id,
            RecommendationEvent.created_at >= since,
        )
        .order_by(RecommendationEvent.created_at.desc())
        .limit(300)
        .all()
    )
    state: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = f"{row.recommendation_type}:{row.target_id}"
        item = state.setdefault(key, {"recent_impressions": 0})
        if row.event_type == "impression":
            item["recent_impressions"] += 1
        elif row.event_type == "dismiss":
            item["dismissed"] = True
        elif row.event_type in {"complete", "completed"}:
            item["completed"] = True
        elif row.event_type == "click":
            item["clicked"] = True
    return state


def _dedupe_terms(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for term in terms:
        clean = str(term or "").strip()
        if not clean or len(clean) < 2:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(clean)
    return result[:20]


def _text_match(text: str, terms: list[str]) -> float:
    if not text or not terms:
        return 0.0
    haystack = text.lower()
    hits = 0
    for term in terms[:12]:
        if term.lower() in haystack:
            hits += 1
    return _clamp01(hits / max(3, min(len(terms), 8)))


def _recency_score(value: datetime | None) -> float:
    if not value:
        return 0.2
    now = datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    days = max(0.0, (now - value).total_seconds() / 86400)
    if days <= 3:
        return 1.0
    if days <= 14:
        return 0.7
    if days <= 60:
        return 0.4
    return 0.2


def _normalize_target_type(value: str | None) -> str:
    normalized = (value or "material").lower()
    if normalized in {"pdf", "ppt", "pptx", "doc", "docx", "video", "image", "material"}:
        return "material"
    if normalized in {"review", "review_faq", "qa", "faq"}:
        return "faq"
    if normalized in {"concept", "entity"}:
        return "concept"
    if normalized in {"flashcard", "card"}:
        return "flashcard"
    if normalized in {"task", "homework", "quiz", "exercise"}:
        return "task"
    return normalized


def _action_for_type(value: str | None) -> str:
    target_type = _normalize_target_type(value)
    return {
        "material": "open_material",
        "faq": "ask_ai",
        "concept": "ask_ai",
        "flashcard": "review_flashcard",
        "task": "open_task",
        "mistake": "review_mistake",
        "path": "open_learning_path",
        "followup": "ask_ai",
    }.get(target_type, "view")


def _action_label_for_type(value: str | None) -> str:
    target_type = _normalize_target_type(value)
    return {
        "material": "查看资料",
        "faq": "围绕它追问",
        "concept": "让 AI 讲解",
        "flashcard": "复习闪卡",
        "task": "查看任务",
        "mistake": "复习错题",
        "path": "查看路径",
        "followup": "继续追问",
    }.get(target_type, "查看")


def _description_for_resource_type(value: str | None) -> str:
    target_type = _normalize_target_type(value)
    return {
        "material": "与课程知识点关联的学习资料。",
        "faq": "教师审核过的问答内容。",
        "concept": "知识图谱中的关键概念。",
        "flashcard": "用于快速复习的记忆卡片。",
        "task": "课程任务或练习。",
    }.get(target_type, "推荐学习内容。")


def _translate_path_reason(reason: str) -> str:
    if not reason:
        return "根据知识图谱顺序和掌握度生成。"
    parts = []
    if "low mastery" in reason:
        parts.append("掌握度偏低")
    if "needs reinforcement" in reason:
        parts.append("需要继续巩固")
    if "high importance" in reason:
        parts.append("课程重要知识点")
    if "matched learning resources" in reason:
        parts.append("已有匹配资料")
    return "，".join(parts) if parts else "根据知识图谱顺序和掌握度生成。"


def _compact_text(text: str | None, max_len: int) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= max_len:
        return value
    return value[: max(0, max_len - 1)] + "…"


def _join_reason(parts: list[str]) -> str:
    return "；".join(part for part in parts if part)


def _short_hash(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def _clamp01(value: float | int | None) -> float:
    try:
        numeric = float(value if value is not None else 0.0)
    except (TypeError, ValueError):
        numeric = 0.0
    return max(0.0, min(1.0, numeric))
