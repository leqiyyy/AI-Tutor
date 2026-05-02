from datetime import datetime, timedelta, timezone
import math
import os
import re
import uuid
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1 import kb as kb_api
from app.core.deps import get_current_admin, get_current_student, get_current_teacher, get_current_user
from app.core.exceptions import ForbiddenException, NotFoundException
from app.core.response import ok
from app.db.base import get_db
from app.models.course import Class, ClassMember, Course, Discussion, Material, Task
from app.models.chat import ChatMessage, ChatSession, ReviewItem
from app.models.knowledge import KnowledgeEntity, KnowledgeRelation
from app.models.notification import Notification
from app.models.personalization import LearningConcept, StudentConceptMastery
from app.models.user import User
from app.schemas.course import CreateClassRequest, JoinClassRequest
from app.services import course_service, kb_service, personalized_recommendation_service

router = APIRouter(tags=["frontend-compat"])

COLORS = ["blue", "green", "purple", "orange", "teal", "pink", "amber"]
GRAPH_ENTITY_LIMIT = 80
GRAPH_ENTITY_FETCH_LIMIT = 300
GRAPH_ROOT_EDGE_LIMIT = 24
GRAPH_ROOT_EDGE_PER_MATERIAL_LIMIT = 10
GRAPH_HIDDEN_ENTITY_KINDS = {
    "material",
    "content_item",
    "candidate_concept_identifier",
}
GRAPH_ARTIFACT_LABELS = {
    "表",
    "表格",
    "表格结构",
    "表的结构",
    "表的组织",
    "表头",
    "行",
    "列",
    "单元格",
    "图片",
    "图像",
    "公式",
    "文件",
    "文档",
    "材料",
    "markdown",
    "markdown table",
    "table",
    "table structure",
    "table organization",
    "row",
    "column",
    "cell",
    "header",
    "image",
    "figure",
    "equation",
    "formula",
    "document",
    "file",
    "material",
}
GRAPH_HIDDEN_RELATION_KINDS = {
    "entity_material_link",
    "candidate_material_link",
    "candidate_material_link_existing",
    "material_content_link",
}
GRAPH_FILE_LABEL_RE = re.compile(
    r"\.(?:txt|pdf|docx?|pptx?|xlsx?|csv|md|png|jpe?g|gif|webp|mp4|mov|avi|zip)$",
    re.IGNORECASE,
)
GRAPH_UUID_RE = re.compile(
    r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$",
    re.IGNORECASE,
)
GRAPH_FILE_HASH_RE = re.compile(
    r"(?:^|[._-])[a-f0-9]{8,}(?:$|[._-])",
    re.IGNORECASE,
)


class TeacherNoticeRequest(BaseModel):
    title: str
    content: str
    importance: str = "normal"
    scope: str = "all"
    attachments: list[str] = Field(default_factory=list)


class TeacherHomeworkRequest(BaseModel):
    title: str
    deadline: Any | None = None
    allowLate: bool = False
    questions: list[dict[str, Any]] = Field(default_factory=list)
    attachments: list[str] = Field(default_factory=list)


class TeacherExamRequest(BaseModel):
    name: str
    startTime: Any | None = None
    endTime: Any | None = None
    duration: int = 90
    totalScore: int = 100
    questions: list[dict[str, Any]] = Field(default_factory=list)
    attachments: list[str] = Field(default_factory=list)


class TeacherTaskStatusRequest(BaseModel):
    status: str | None = None
    is_published: bool | None = None


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return ""


def _date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    return ""


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _size_text(size: int | None) -> str:
    if not size:
        return "0 KB"
    if size < 1024 * 1024:
        return f"{max(1, round(size / 1024))} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def _file_type(value: str | None) -> str:
    mapping = {
        "pdf": "PDF",
        "ppt": "PPT",
        "pptx": "PPT",
        "video": "Video",
        "mp4": "Video",
    }
    return mapping.get((value or "").lower(), "PDF")


def _student_file_type(value: str | None) -> str:
    mapping = {
        "pdf": "pdf",
        "ppt": "ppt",
        "pptx": "ppt",
        "video": "video",
        "mp4": "video",
    }
    return mapping.get((value or "").lower(), "pdf")


def _course_image(seed: str) -> str:
    return f"https://readdy.ai/api/search-image?query=course%20learning%20space%20{seed}&width=400&height=240&orientation=landscape"


def _get_course(db: Session, course_id: str | None) -> Course | None:
    if not course_id:
        return None
    return db.query(Course).filter(Course.id == course_id).first()


def _get_teacher(db: Session, teacher_id: str | None) -> User | None:
    if not teacher_id:
        return None
    return db.query(User).filter(User.id == teacher_id).first()


def _student_count(db: Session, class_id: str) -> int:
    return db.query(ClassMember).filter(
        ClassMember.class_id == class_id,
        ClassMember.role == "student",
    ).count()


def _material_count(db: Session, class_id: str) -> int:
    return db.query(Material).filter(
        Material.class_id == class_id,
        Material.is_active == True,
    ).count()


def _task_count(db: Session, class_id: str, published_only: bool = False) -> int:
    query = db.query(Task).filter(Task.class_id == class_id)
    if published_only:
        query = query.filter(Task.is_published == True)
    return query.count()


def _discussion_count(db: Session, class_id: str) -> int:
    return db.query(Discussion).filter(
        Discussion.class_id == class_id,
        Discussion.is_active == True,
    ).count()


def _notifications_for_user(db: Session, user_id: str, limit: int = 20) -> list[dict]:
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(max(limit * 5, 50))
        .all()
    )
    visible = [
        {
            "id": item.id,
            "type": item.type,
            "title": item.title,
            "content": item.content,
            "time": _date(item.created_at),
            "unread": not bool(item.is_read),
        }
        for item in rows
        if not (item.extra_data or {}).get("deleted_at")
    ]
    return visible[:limit]


def _student_settings_payload(user: User) -> dict[str, Any]:
    return {
        "profile": {
            "name": user.real_name or "",
            "nameEn": "",
            "gender": "male",
            "birthday": "",
            "bio": user.bio or "",
            "email": user.email or "",
            "phone": user.phone or "",
            "wechat": "",
            "qq": "",
            "hometown": "",
        },
        "academic": {
            "studentId": user.student_id or "",
            "school": user.school or "",
            "college": user.college or "",
            "major": user.major or "",
            "grade": user.grade or "",
            "classNumber": user.class_no or "",
            "enrollYear": "",
            "expectedGradYear": "",
            "degree": "",
            "studentType": "undergraduate",
            "dormitory": "",
            "advisor": "",
            "gpa": "",
            "credits": "",
        },
        "notifications": {
            "siteNotify": True,
            "emailNotify": True,
            "wechatNotify": False,
            "deadlineRemind": True,
            "teacherReply": True,
            "aiSuggestion": True,
            "examRemind": True,
            "scoreRelease": True,
        },
        "learning": {
            "preferStyle": "visual",
            "dailyGoal": "2",
            "showLeaderboard": True,
            "weeklyReport": True,
            "aiAutoSuggest": True,
        },
        "privacy": {
            "showGrade": False,
            "showLeaderboard": True,
            "showBio": True,
            "showContact": False,
            "allowAIAnalyze": True,
        },
        "interests": [],
        "avatarUrl": user.avatar_url or "",
    }


def _teacher_settings_payload(user: User) -> dict[str, Any]:
    return {
        "profile": {
            "name": user.real_name or "",
            "nameEn": "",
            "gender": "male",
            "birthday": "",
            "bio": user.bio or "",
            "email": user.email or "",
            "phone": user.phone or "",
            "wechat": "",
            "website": "",
            "school": user.school or "",
            "college": user.college or "",
            "department": user.department or "",
            "title": user.title or "",
            "employeeId": user.teacher_id or "",
            "teacherType": "full",
            "researchArea": "",
            "officeLocation": "",
            "officeHours": "",
            "education": "",
            "graduateSchool": "",
            "degree": "",
            "graduateYear": "",
            "joinYear": "",
            "teachingYears": "",
        },
        "notifications": {
            "siteNotify": True,
            "emailNotify": True,
            "wechatNotify": False,
            "studentQuestion": True,
            "aiDislike": True,
            "deadlineRemind": True,
            "systemUpdate": False,
        },
        "ai": {
            "defaultStyle": "academic",
            "autoReply": True,
            "knowledgeBase": True,
            "responseLanguage": "zh",
            "maxTokens": "2000",
        },
        "achievements": [],
        "avatarUrl": user.avatar_url or "",
    }


def _apply_student_settings(user: User, payload: dict[str, Any]) -> None:
    profile = payload.get("profile") or {}
    academic = payload.get("academic") or {}
    user.real_name = str(profile.get("name") or user.real_name or "").strip() or user.real_name
    user.phone = profile.get("phone") or None
    user.bio = profile.get("bio") or None
    user.school = academic.get("school") or None
    user.student_id = academic.get("studentId") or None
    user.college = academic.get("college") or None
    user.major = academic.get("major") or None
    user.grade = academic.get("grade") or None
    user.class_no = academic.get("classNumber") or None
    user.avatar_url = payload.get("avatarUrl") or user.avatar_url
    user.updated_at = datetime.now(timezone.utc)


def _apply_teacher_settings(user: User, payload: dict[str, Any]) -> None:
    profile = payload.get("profile") or {}
    user.real_name = str(profile.get("name") or user.real_name or "").strip() or user.real_name
    user.phone = profile.get("phone") or None
    user.bio = profile.get("bio") or None
    user.school = profile.get("school") or None
    user.college = profile.get("college") or None
    user.department = profile.get("department") or None
    user.title = profile.get("title") or None
    user.teacher_id = profile.get("employeeId") or None
    user.avatar_url = payload.get("avatarUrl") or user.avatar_url
    user.updated_at = datetime.now(timezone.utc)


def _avatar_data_url(label: str) -> str:
    initial = next(iter((label or "用").strip()), "用")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">'
        '<rect width="200" height="200" rx="100" fill="#14b8a6"/>'
        f'<text x="50%" y="54%" text-anchor="middle" dominant-baseline="middle" '
        f'font-family="Arial, sans-serif" font-size="86" font-weight="700" fill="#fff">{initial}</text>'
        '</svg>'
    )
    return f"data:image/svg+xml;charset=utf-8,{quote(svg)}"


@router.get("/student/settings", response_model=None)
def student_settings(
    current_user: User = Depends(get_current_student),
):
    return ok(data=_student_settings_payload(current_user))


@router.put("/student/settings", response_model=None)
def update_student_settings(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    _apply_student_settings(current_user, payload)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return ok(data=_student_settings_payload(current_user), message="Settings updated")


@router.get("/teacher/settings", response_model=None)
def teacher_settings(
    current_user: User = Depends(get_current_teacher),
):
    return ok(data=_teacher_settings_payload(current_user))


@router.put("/teacher/settings", response_model=None)
def update_teacher_settings(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    _apply_teacher_settings(current_user, payload)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return ok(data=_teacher_settings_payload(current_user), message="Settings updated")


@router.post("/settings/password", response_model=None)
def update_password_placeholder(
    payload: dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    new_password = str(payload.get("newPassword") or "")
    confirm_password = str(payload.get("confirmPassword") or "")
    if not new_password or new_password != confirm_password:
        return ok(data={"status": "ignored", "message": "两次输入的新密码不一致"})
    return ok(data={"status": "updated", "message": "密码校验已通过"})


@router.post("/settings/avatar", response_model=None)
def upload_avatar_placeholder(
    payload: dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    label = current_user.real_name or str(payload.get("fileName") or "头像")
    return ok(data={"url": _avatar_data_url(label)})


@router.get("/settings/devices", response_model=None)
def settings_devices(
    current_user: User = Depends(get_current_user),
):
    return ok(data=[{
        "id": f"device-{current_user.id}",
        "deviceName": "当前浏览器",
        "location": "当前登录位置",
        "lastActiveAt": "刚刚",
        "current": True,
    }])


def _student_home_task_item(task: Task) -> dict:
    deadline = task.due_date
    now = datetime.now(deadline.tzinfo) if deadline and deadline.tzinfo else datetime.now(timezone.utc).replace(tzinfo=None)
    urgent = bool(deadline and deadline <= now.replace(hour=23, minute=59, second=59, microsecond=999999))
    icon = "ri-file-edit-line" if task.task_type == "exam" else "ri-file-list-3-line"
    return {
        "title": task.title,
        "deadline": _iso(deadline) if deadline else "未设置截止时间",
        "urgent": urgent,
        "icon": icon,
    }


def _student_home_update_item(notification: Notification) -> dict:
    color_map = {
        "exam": "bg-purple-50 text-purple-600",
        "deadline": "bg-orange-50 text-orange-600",
        "system": "bg-blue-50 text-blue-600",
    }
    icon_map = {
        "exam": "ri-file-edit-line",
        "deadline": "ri-time-line",
        "system": "ri-notification-3-line",
    }
    return {
        "type": notification.type,
        "title": notification.title,
        "time": _date(notification.created_at),
        "color": color_map.get(notification.type, "bg-gray-50 text-gray-600"),
        "icon": icon_map.get(notification.type, "ri-notification-line"),
    }


def _course_summary(db: Session, cls: Class) -> dict:
    course = _get_course(db, cls.course_id)
    teacher = _get_teacher(db, cls.teacher_id)
    return {
        "id": cls.id,
        "classId": cls.id,
        "courseId": cls.course_id,
        "name": course.name if course else cls.name,
        "teacher": teacher.real_name if teacher else "",
        "code": course.code or cls.invite_code if course else cls.invite_code,
    }


def _assert_class_access(db: Session, cls: Class, user: User) -> None:
    if user.role == "admin":
        return
    if not course_service.check_class_member(db, cls.id, user.id):
        raise ForbiddenException("You are not a member of this class")


def _class_or_404_with_access(db: Session, class_id: str, user: User) -> Class:
    cls = course_service.get_class_or_404(db, class_id)
    _assert_class_access(db, cls, user)
    return cls


def _teacher_class_or_404(db: Session, class_id: str, user: User) -> Class:
    cls = course_service.get_class_or_404(db, class_id)
    if user.role != "admin" and cls.teacher_id != user.id:
        raise ForbiddenException("Only the class teacher can manage this class")
    return cls


def _task_status(task: Task) -> str:
    if not task.is_published:
        return "草稿"
    if task.task_type == "exam":
        start_at = _extract_exam_start_time(task.description)
        if start_at:
            now = datetime.now(start_at.tzinfo) if start_at.tzinfo else datetime.now(timezone.utc).replace(tzinfo=None)
            if start_at > now:
                return "未开始"
    if task.due_date:
        now = datetime.now(task.due_date.tzinfo) if task.due_date.tzinfo else datetime.now(timezone.utc).replace(tzinfo=None)
        if task.due_date < now:
            return "已结束"
    return "进行中"


def _extract_exam_start_time(description: str | None) -> datetime | None:
    if not description:
        return None
    match = re.search(r"开始时间：([^\n]+)", description)
    if not match:
        return None
    return _parse_datetime(match.group(1))


def _publish_class_notifications(
    db: Session,
    class_id: str,
    notification_type: str,
    title: str,
    content: str,
    extra_data: dict[str, Any] | None = None,
) -> int:
    recipients = db.query(ClassMember).filter(
        ClassMember.class_id == class_id,
        ClassMember.role == "student",
    ).all()
    for recipient in recipients:
        db.add(Notification(
            user_id=recipient.user_id,
            type=notification_type,
            title=title,
            content=content,
            extra_data={
                "class_id": class_id,
                **(extra_data or {}),
            },
        ))
    return len(recipients)


def _teacher_task_item(task: Task, total: int) -> dict:
    return {
        "id": task.id,
        "type": task.task_type or "homework",
        "title": task.title,
        "deadline": _iso(task.due_date),
        "submitted": len(task.submissions or []),
        "total": total,
        "status": _task_status(task),
        "publishDate": _date(task.created_at),
        "attachments": [],
        "_sortAt": _iso(task.created_at),
    }


def _notice_rows_for_class(db: Session, class_id: str) -> list[Notification]:
    rows = (
        db.query(Notification)
        .filter(Notification.type == "system")
        .order_by(Notification.created_at.desc())
        .limit(500)
        .all()
    )
    notices: dict[str, Notification] = {}
    for row in rows:
        extra = row.extra_data or {}
        if extra.get("class_id") != class_id or extra.get("source") != "teacher_notice" or extra.get("deleted_at"):
            continue
        notice_id = extra.get("notice_id") or row.id
        notices.setdefault(str(notice_id), row)
    return list(notices.values())


def _notice_task_item(row: Notification, total: int) -> dict:
    extra = row.extra_data or {}
    return {
        "id": extra.get("notice_id") or row.id,
        "type": "notice",
        "title": row.title,
        "deadline": "-",
        "submitted": total,
        "total": total,
        "status": "已发布",
        "publishDate": _date(row.created_at),
        "attachments": extra.get("attachments") or [],
        "_sortAt": _iso(row.created_at),
    }


def _mark_related_notifications_deleted(
    db: Session,
    *,
    class_id: str,
    deleted_at: str,
    task_id: str | None = None,
    notice_id: str | None = None,
) -> int:
    rows = (
        db.query(Notification)
        .filter(Notification.type.in_(["system", "deadline", "exam"]))
        .order_by(Notification.created_at.desc())
        .limit(2000)
        .all()
    )
    updated = 0
    for row in rows:
        extra = dict(row.extra_data or {})
        if extra.get("class_id") != class_id:
            continue
        if task_id and str(extra.get("task_id") or "") != str(task_id):
            continue
        if notice_id and str(extra.get("notice_id") or "") != str(notice_id):
            continue
        extra["deleted_at"] = deleted_at
        row.extra_data = extra
        db.add(row)
        updated += 1
    return updated


@router.get("/student/dashboard", response_model=None)
def student_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    classes = course_service.get_student_classes(db, current_user.id)
    courses = []
    progress_courses = []
    pending_tasks = 0

    for index, item in enumerate(classes):
        class_id = item["id"]
        tasks = _task_count(db, class_id, published_only=True)
        pending_tasks += tasks
        course_name = item.get("course_name") or item.get("name") or "课程"
        courses.append({
            "id": class_id,
            "name": course_name,
            "teacher": item.get("teacher_name") or "",
            "progress": 0,
            "unread": 0,
            "color": COLORS[index % len(COLORS)],
            "image": _course_image(class_id),
        })
        progress_courses.append({
            "id": class_id,
            "name": course_name,
            "progress": 0,
            "chapter": item.get("semester") or "课程学习中",
            "unread": 0,
            "color": COLORS[index % len(COLORS)],
        })
    recommendations = []
    if classes:
        recommendations = _dashboard_recommendations(
            db,
            current_user,
            class_id=classes[0]["id"],
            limit=4,
        )

    return ok(data={
        "greetingName": current_user.real_name,
        "stats": {
            "activeCourses": len(classes),
            "pendingTasks": pending_tasks,
            "completionRate": 0,
        },
        "pendingItems": [],
        "progressCourses": progress_courses,
        "recommendations": recommendations,
        "activities": [],
        "notifications": _notifications_for_user(db, current_user.id),
        "courses": courses,
        "sidePanel": _student_side_panel(db, current_user, classes),
    })


def _dashboard_recommendations(
    db: Session,
    user: User,
    *,
    class_id: str,
    limit: int = 4,
) -> list[dict[str, Any]]:
    try:
        payload = personalized_recommendation_service.get_personalized_recommendations(
            db,
            user,
            class_id=class_id,
            surface="dashboard",
            limit=limit,
        )
    except Exception:
        return []
    return [
        _personalized_item_to_dashboard_card(item, index=index)
        for index, item in enumerate(payload.get("items") or [])
    ]


def _personalized_item_to_dashboard_card(item: dict[str, Any], *, index: int) -> dict[str, Any]:
    target_type = str(item.get("type") or "material")
    tone_map = {
        "material": "blue",
        "concept": "teal",
        "faq": "purple",
        "mistake": "amber",
        "flashcard": "green",
        "path": "purple",
        "task": "orange",
        "followup": "pink",
    }
    icon_map = {
        "material": "ri-file-text-line",
        "concept": "ri-mind-map",
        "faq": "ri-question-answer-line",
        "mistake": "ri-error-warning-line",
        "flashcard": "ri-stack-line",
        "path": "ri-route-line",
        "task": "ri-task-line",
        "followup": "ri-chat-follow-up-line",
    }
    content = item.get("reason") or item.get("description") or "根据你的学习记录和课程内容推荐。"
    return {
        "id": item.get("id") or f"recommendation-{index}",
        "title": item.get("title") or "个性化学习建议",
        "content": content,
        "tone": tone_map.get(target_type, COLORS[index % len(COLORS)]),
        "icon": icon_map.get(target_type, "ri-lightbulb-line"),
        "meta": f"{int(item.get('relevance') or 0)}% 匹配",
    }


def _truncate_text(value: str | None, limit: int = 90) -> str:
    text = re.sub(r"\s+", " ", (value or "").strip())
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _class_name_map(db: Session, class_ids: list[str]) -> dict[str, str]:
    if not class_ids:
        return {}
    rows = (
        db.query(Class, Course)
        .join(Course, Course.id == Class.course_id)
        .filter(Class.id.in_(class_ids))
        .all()
    )
    return {cls.id: course.name or cls.name or "课程" for cls, course in rows}


def _side_panel_payload(
    *,
    role: str,
    tag: str,
    title: str,
    body: str,
    source_type: str,
    course_id: str | None = None,
    course_name: str | None = None,
) -> dict[str, Any]:
    role_defaults = {
        "student": {
            "badge": "Study Mood",
            "panelTitle": "把学习留给安静而清晰的节奏",
            "quote": "先完成最小的一步，学习就会开始流动。",
            "quoteCaption": "今天适合先把最接近截止的一件事做完。",
        },
        "teacher": {
            "badge": "Teaching Mood",
            "panelTitle": "好的答疑，往往来自克制而稳定的判断",
            "quote": "好教学不是一次说完，而是一次次让学生真正听懂。",
            "quoteCaption": "今天适合先看重复率最高的问题，再统一回应。",
        },
        "admin": {
            "badge": "Ops Mood",
            "panelTitle": "稳定感来自很多细小问题被及时处理",
            "quote": "真正高级的系统体验，是大多数问题在用户察觉前就被处理掉。",
            "quoteCaption": "今天适合先看影响链路稳定的问题。",
        },
    }
    defaults = role_defaults.get(role, role_defaults["student"])
    return {
        **defaults,
        "insight": {
            "tag": tag,
            "title": title,
            "body": body,
            "sourceType": source_type,
            "courseId": course_id,
            "courseName": course_name,
        },
    }


def _student_side_panel(db: Session, user: User, classes: list[dict[str, Any]]) -> dict[str, Any]:
    if not classes:
        return _side_panel_payload(
            role="student",
            tag="微知识",
            title="加入课程后生成个人微知识",
            body="当前还没有课程数据。加入课程、浏览资料或向 AI 助教提问后，这里会显示与你学习进度相关的知识提示。",
            source_type="empty",
        )

    class_ids = [str(item["id"]) for item in classes if item.get("id")]
    class_names = _class_name_map(db, class_ids)

    weak = (
        db.query(StudentConceptMastery)
        .filter(
            StudentConceptMastery.user_id == user.id,
            StudentConceptMastery.class_id.in_(class_ids),
            StudentConceptMastery.evidence_count > 0,
        )
        .order_by(StudentConceptMastery.mastery_score.asc(), StudentConceptMastery.confidence.desc())
        .first()
    )
    if weak:
        score = max(0, min(100, round((weak.mastery_score or 0) * 100)))
        return _side_panel_payload(
            role="student",
            tag="微知识",
            title=f"{weak.concept_name} 是待巩固知识点",
            body=f"系统结合你的学习证据估计该知识点掌握度约 {score}%。建议先回看相关资料，再用 AI 助教追问一个具体例题。",
            source_type="mastery",
            course_id=weak.class_id,
            course_name=class_names.get(weak.class_id),
        )

    recent_question = (
        db.query(ChatMessage, ChatSession)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .filter(
            ChatSession.user_id == user.id,
            ChatSession.class_id.in_(class_ids),
            ChatMessage.role == "user",
            ChatSession.is_active == True,
        )
        .order_by(ChatMessage.created_at.desc())
        .first()
    )
    if recent_question:
        message, session = recent_question
        return _side_panel_payload(
            role="student",
            tag="最近提问",
            title="从最近的问题继续追一层",
            body=f"你最近问到「{_truncate_text(message.content, 38)}」。可以继续让 AI 助教补充定义、过程图、易错点或练习题。",
            source_type="question",
            course_id=session.class_id,
            course_name=class_names.get(session.class_id),
        )

    concept = (
        db.query(KnowledgeEntity)
        .filter(
            KnowledgeEntity.class_id.in_(class_ids),
            KnowledgeEntity.status != "rejected",
        )
        .order_by(KnowledgeEntity.confidence.desc(), KnowledgeEntity.created_at.desc())
        .first()
    )
    if concept:
        return _side_panel_payload(
            role="student",
            tag="微知识",
            title=concept.name,
            body=_truncate_text(concept.description, 96) or "这是课程知识图谱中的核心节点，可以从定义、关联概念和典型题三个角度复习。",
            source_type="knowledge_graph",
            course_id=concept.class_id,
            course_name=class_names.get(concept.class_id),
        )

    material = (
        db.query(Material)
        .filter(Material.class_id.in_(class_ids), Material.is_active == True)
        .order_by(Material.created_at.desc())
        .first()
    )
    if material:
        return _side_panel_payload(
            role="student",
            tag="课程资料",
            title=f"从《{material.title}》开始学习",
            body="这门课已有资料入库。建议先浏览资料摘要，再向 AI 助教提问一个具体概念，系统会逐步形成个性化微知识。",
            source_type="material",
            course_id=material.class_id,
            course_name=class_names.get(material.class_id),
        )

    first = classes[0]
    class_id = str(first["id"])
    return _side_panel_payload(
        role="student",
        tag="微知识",
        title="等待课程资料生成微知识",
        body="你已加入课程，但当前课程资料和学习记录还较少。开始提问或等待教师上传资料后，这里会显示课程相关提示。",
        source_type="empty",
        course_id=class_id,
        course_name=class_names.get(class_id) or first.get("course_name") or first.get("name"),
    )


def _teacher_side_panel(db: Session, user: User, classes: list[dict[str, Any]]) -> dict[str, Any]:
    if not classes:
        return _side_panel_payload(
            role="teacher",
            tag="教学摘记",
            title="创建课程后生成教学摘记",
            body="当前还没有课程数据。创建课程并上传资料后，这里会根据资料、学生提问和反馈生成教学侧重点。",
            source_type="empty",
        )

    class_ids = [str(item["id"]) for item in classes if item.get("id")]
    class_names = _class_name_map(db, class_ids)

    disliked = (
        db.query(ReviewItem)
        .filter(
            ReviewItem.class_id.in_(class_ids),
            ReviewItem.trigger == "dislike",
            ReviewItem.status == "pending",
        )
        .order_by(ReviewItem.created_at.desc())
        .all()
    )
    if disliked:
        class_id = disliked[0].class_id
        return _side_panel_payload(
            role="teacher",
            tag="教学摘记",
            title=f"{len(disliked)} 条学生反馈待审核",
            body="学生主动点踩的回答更能反映真实困惑。建议先查看反馈原因，修正答案后回流知识库。",
            source_type="feedback",
            course_id=class_id,
            course_name=class_names.get(class_id),
        )

    recent_question = (
        db.query(ChatMessage, ChatSession)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .filter(
            ChatSession.class_id.in_(class_ids),
            ChatMessage.role == "user",
            ChatSession.is_active == True,
        )
        .order_by(ChatMessage.created_at.desc())
        .first()
    )
    if recent_question:
        message, session = recent_question
        return _side_panel_payload(
            role="teacher",
            tag="学生问题",
            title="最近学生提问可转化为讲解重点",
            body=f"最近学生问到「{_truncate_text(message.content, 44)}」。可以考虑补充一个课堂例子或在资料中增加说明。",
            source_type="question",
            course_id=session.class_id,
            course_name=class_names.get(session.class_id),
        )

    concept = (
        db.query(KnowledgeEntity)
        .filter(
            KnowledgeEntity.class_id.in_(class_ids),
            KnowledgeEntity.status != "rejected",
        )
        .order_by(KnowledgeEntity.confidence.desc(), KnowledgeEntity.created_at.desc())
        .first()
    )
    if concept:
        return _side_panel_payload(
            role="teacher",
            tag="教学摘记",
            title=f"可围绕「{concept.name}」组织讲解",
            body=_truncate_text(concept.description, 96) or "该节点来自课程知识图谱。建议检查其关联关系，并补充容易混淆的例题或课堂说明。",
            source_type="knowledge_graph",
            course_id=concept.class_id,
            course_name=class_names.get(concept.class_id),
        )

    material = (
        db.query(Material)
        .filter(Material.class_id.in_(class_ids), Material.is_active == True)
        .order_by(Material.created_at.desc())
        .first()
    )
    if material:
        return _side_panel_payload(
            role="teacher",
            tag="教学摘记",
            title=f"《{material.title}》可作为备课入口",
            body="这份资料已进入课程资料区。完成索引后，系统会结合知识图谱和学生提问生成更具体的教学摘记。",
            source_type="material",
            course_id=material.class_id,
            course_name=class_names.get(material.class_id),
        )

    first = classes[0]
    class_id = str(first["id"])
    return _side_panel_payload(
        role="teacher",
        tag="教学摘记",
        title="新课程需要先上传资料",
        body="当前课程还没有可用资料。建议先上传教学大纲、课件或作业说明，系统会据此生成课程知识点和教学摘记。",
        source_type="empty",
        course_id=class_id,
        course_name=class_names.get(class_id) or first.get("course_name") or first.get("name"),
    )


@router.get("/teacher/dashboard", response_model=None)
def teacher_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    classes = course_service.get_teacher_classes(db, current_user.id)
    courses = []
    total_students = 0

    for index, item in enumerate(classes):
        class_id = item["id"]
        students = item.get("student_count") or 0
        total_students += students
        course_name = item.get("course_name") or item.get("name") or "课程"
        courses.append({
            "id": class_id,
            "name": course_name,
            "code": item.get("invite_code") or item.get("course_id") or "",
            "students": students,
            "unread": 0,
            "color": COLORS[index % len(COLORS)],
            "image": _course_image(class_id),
        })

    return ok(data={
        "greetingName": current_user.real_name,
        "stats": {
            "activeCourses": len(classes),
            "totalStudents": total_students,
            "pendingReviews": 0,
            "aiAnswerRate": 0,
            "manualAnswerRate": 0,
            "satisfactionScore": 0,
            "todayTodo": 0,
            "pendingQuestions": 0,
            "dueSoon": 0,
            "courseSetupCompleted": _material_count(db, classes[0]["id"]) if classes else 0,
            "courseSetupTotal": len(classes),
            "weeklyStudentTrend": [0, 0, 0, 0, 0, 0, 0],
        },
        "calendarEvents": [],
        "aiWeeklyMetrics": [],
        "hotQuestionTopics": [],
        "todoItems": [],
        "warningItems": [],
        "notifications": _notifications_for_user(db, current_user.id),
        "courses": courses,
        "sidePanel": _teacher_side_panel(db, current_user, classes),
    })


@router.get("/admin/dashboard", response_model=None)
def admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    teacher_count = db.query(User).filter(User.role == "teacher").count()
    student_count = db.query(User).filter(User.role == "student").count()
    course_count = db.query(Course).filter(Course.is_active == True).count()
    class_count = db.query(Class).filter(Class.is_active == True).count()
    users = db.query(User).order_by(User.created_at.desc()).limit(20).all()
    classes = db.query(Class).filter(Class.is_active == True).order_by(Class.created_at.desc()).limit(20).all()

    return ok(data={
        "greetingName": current_user.real_name,
        "stats": [
            {"id": "teachers", "label": "注册教师", "value": str(teacher_count), "change": "", "tone": "blue", "icon": "ri-user-star-line"},
            {"id": "students", "label": "注册学生", "value": str(student_count), "change": "", "tone": "green", "icon": "ri-group-line"},
            {"id": "courses", "label": "开设课程", "value": str(course_count), "change": "", "tone": "purple", "icon": "ri-book-open-line"},
            {"id": "classes", "label": "活跃班级", "value": str(class_count), "change": "", "tone": "orange", "icon": "ri-team-line"},
        ],
        "todoReminders": [],
        "activities": [],
        "systemStatus": [],
        "userReviews": [],
        "users": [
            {
                "id": user.id,
                "name": user.real_name,
                "role": user.role,
                "roleLabel": {"student": "学生", "teacher": "教师", "admin": "管理员"}.get(user.role, user.role),
                "department": user.college or user.department or "",
                "registeredAt": _date(user.created_at),
                "status": "online" if user.is_active else "disabled",
                "statusLabel": "正常" if user.is_active else "禁用",
            }
            for user in users
        ],
        "courses": [
            {
                "id": cls.id,
                "name": (_get_course(db, cls.course_id).name if _get_course(db, cls.course_id) else cls.name),
                "teacher": (_get_teacher(db, cls.teacher_id).real_name if _get_teacher(db, cls.teacher_id) else ""),
                "students": _student_count(db, cls.id),
                "knowledgeBaseStatus": "normal",
                "knowledgeBaseStatusLabel": "正常",
                "documentCount": _material_count(db, cls.id),
                "lastActive": _date(cls.updated_at or cls.created_at),
            }
            for cls in classes
        ],
        "auditAnswers": [],
        "auditReports": [],
        "sensitiveWords": [],
    })


@router.post("/student/courses/join", response_model=None)
def student_join_course(
    body: JoinClassRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    cls = course_service.join_class_by_invite(db, current_user.id, body.invite_code)
    return ok(data={"course": _course_summary(db, cls)}, message="Joined class successfully")


@router.post("/teacher/courses", response_model=None)
def teacher_create_course(
    body: CreateClassRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = course_service.create_class(db, current_user.id, body.model_dump())
    return ok(data={
        "course": _course_summary(db, cls),
        "inviteCode": cls.invite_code,
    }, message="Course created")


@router.post("/teacher/courses/{class_id}/invite-code", response_model=None)
def teacher_invite_code(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = course_service.get_class_or_404(db, class_id)
    if cls.teacher_id != current_user.id:
        raise ForbiddenException("Only the class teacher can access the invite code")
    return ok(data={
        "courseId": cls.id,
        "classId": cls.id,
        "knowledgeCourseId": cls.course_id,
        "inviteCode": cls.invite_code,
    })


@router.get("/student/courses/{class_id}", response_model=None)
def student_course_bootstrap(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    member = db.query(ClassMember).filter(
        ClassMember.class_id == class_id,
        ClassMember.user_id == current_user.id,
    ).first()
    return ok(data={
        "course": _course_summary(db, cls),
        "defaultSection": "home",
        "enrolledAt": _iso(member.joined_at if member else cls.created_at),
        "completionRate": 0,
        "unreadCount": 0,
    })


@router.get("/teacher/courses/{class_id}", response_model=None)
def teacher_course_bootstrap(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    return ok(data={
        "course": _course_summary(db, cls),
        "defaultSection": "home",
        "inviteCode": cls.invite_code,
        "studentCount": _student_count(db, class_id),
        "materialCount": _material_count(db, class_id),
        "pendingQuestionCount": _discussion_count(db, class_id),
    })


@router.get("/student/courses/{class_id}/materials", response_model=None)
def student_course_materials(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    materials = course_service.list_materials(db, cls.id)
    return ok(data={
        "files": [
            {
                "id": item["id"],
                "name": item["title"] or item["file_name"],
                "type": _student_file_type(item.get("file_type")),
                "size": _size_text(item.get("file_size")),
                "date": _date(item.get("created_at")),
                "views": 0,
            }
            for item in materials
        ]
    })


@router.get("/teacher/courses/{class_id}/materials", response_model=None)
def teacher_course_materials(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    materials = course_service.list_materials(db, cls.id)
    return ok(data={
        "files": [
            {
                "id": item["id"],
                "name": item["title"] or item["file_name"],
                "type": _file_type(item.get("file_type")),
                "size": _size_text(item.get("file_size")),
                "status": item.get("kb_status") or "pending",
                "date": _date(item.get("created_at")),
                "category": "lecture",
                "downloads": 0,
                "classId": class_id,
                "courseId": cls.course_id,
            }
            for item in materials
        ]
    })


@router.post("/teacher/courses/{class_id}/files", response_model=None)
async def teacher_upload_course_files(
    class_id: str,
    files: list[UploadFile] = File(...),
    async_index: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    results = []
    for file in files:
        response = await kb_api.upload_course_file(
            course_id=cls.course_id,
            class_id=cls.id,
            file=file,
            title=None,
            description=None,
            async_index=async_index,
            db=db,
            current_user=current_user,
        )
        results.append(response.get("data") if isinstance(response, dict) else response)
    return ok(data={"files": results}, message="Files uploaded")


@router.delete("/teacher/courses/{class_id}/files/{file_id}", response_model=None)
async def teacher_delete_course_file(
    class_id: str,
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    material = kb_service.get_material_for_user(db, cls.course_id, file_id, current_user)
    if material.class_id != cls.id:
        raise NotFoundException("Material not found")
    graph_cleanup = kb_service.remove_material_graph_contributions(
        db,
        class_id=cls.id,
        material_id=material.id,
        commit=False,
    )
    index_cleanup = await kb_service.delete_material_index_artifacts(
        class_id=cls.id,
        material_id=material.id,
    )
    material.is_active = False
    material.kb_status = "pending"
    db.commit()
    return ok(data={
        "file_id": material.id,
        "graph_cleanup": graph_cleanup,
        "index_cleanup": index_cleanup,
    }, message="File deleted")


@router.post("/teacher/courses/{class_id}/files/{file_id}/kb/retry", response_model=None)
async def teacher_retry_course_file_index(
    class_id: str,
    file_id: str,
    async_retry: bool = Query(True),
    force: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    return await kb_api.retry_file_index(
        course_id=cls.course_id,
        file_id=file_id,
        force=force,
        async_retry=async_retry,
        db=db,
        current_user=current_user,
    )


@router.post("/teacher/courses/{class_id}/kb/rebuild", response_model=None)
def teacher_rebuild_course_kb(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    materials = db.query(Material).filter(
        Material.class_id == cls.id,
        Material.is_active == True,
    ).order_by(Material.created_at.asc()).all()
    graph_cleanup = kb_service.clear_class_graph_contributions(
        db,
        class_id=cls.id,
        commit=False,
    )

    queue_results = []
    for material in materials:
        parse_task = kb_service.prepare_parse_task_for_enqueue(
            db,
            cls=cls,
            material=material,
            file_hash=None,
            force=True,
        )
        queue_info = kb_service.enqueue_parse_task(
            db,
            parse_task=parse_task,
            force=True,
        )
        queue_results.append({
            "file_id": material.id,
            "task_id": parse_task.id,
            "queue_task_id": queue_info.get("queue_task_id"),
            "queue_status": queue_info.get("queue_status"),
        })

    if not materials:
        db.commit()

    return ok(data={
        "class_id": cls.id,
        "queued_count": len(queue_results),
        "files": queue_results,
        "graph_cleanup": graph_cleanup,
    }, message="Course knowledge base rebuild queued")


@router.get("/teacher/courses/{class_id}/materials/{file_id}/analysis", response_model=None)
def teacher_course_material_analysis(
    class_id: str,
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    raw = kb_service.get_material_analysis(db, cls.course_id, file_id, current_user)
    keywords = raw.get("keywords") or []
    return ok(data={
        "fileId": file_id,
        "summary": raw.get("summary") or "资料仍在解析中，完成后将展示自动摘要。",
        "keyPoints": keywords[:8],
        "difficulties": [
            {"title": keyword, "difficulty": "中等"}
            for keyword in keywords[:5]
        ],
        "recommendedStudyDuration": "30 分钟",
        "generatedAt": _iso(datetime.now(timezone.utc)),
        "raw": raw,
    })


@router.get("/teacher/courses/{class_id}/materials/{file_id}/preview", response_model=None)
def teacher_course_material_preview(
    class_id: str,
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    raw = kb_service.get_material_preview(db, cls.course_id, file_id, current_user)
    preview_type = "video" if raw.get("file_type") in {"video", "mp4"} else "document"
    return ok(data={
        "fileId": file_id,
        "previewType": preview_type,
        "previewUrl": "",
        "note": raw.get("summary") or "暂无自动摘要",
        "textContent": raw.get("preview_text") or "",
        "textTruncated": bool(raw.get("preview_text_truncated")),
        "previewSource": raw.get("preview_source"),
        "chunkCount": raw.get("chunk_count", 0),
        "raw": raw,
    })


@router.get("/teacher/courses/{class_id}/materials/{file_id}/download", response_class=FileResponse)
def teacher_course_material_download(
    class_id: str,
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    material = kb_service.get_material_for_user(db, cls.course_id, file_id, current_user)
    return FileResponse(
        path=material.file_path,
        filename=material.file_name,
        media_type=material.mime_type,
    )


@router.get("/student/courses/{class_id}/tasks", response_model=None)
def student_course_tasks(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    _class_or_404_with_access(db, class_id, current_user)
    tasks = course_service.list_tasks(db, class_id, published_only=True)
    return ok(data={
        "tasks": [
            {
                "id": item["id"],
                "title": item["title"],
                "deadline": _iso(item.get("due_date")),
                "status": "待完成",
                "score": None,
                "urgent": False,
                "questions": [],
            }
            for item in tasks
        ]
    })


@router.get("/teacher/courses/{class_id}/tasks", response_model=None)
def teacher_course_tasks(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    _class_or_404_with_access(db, class_id, current_user)
    total = _student_count(db, class_id)
    task_rows = db.query(Task).filter(Task.class_id == class_id, Task.is_published == True).all()
    items = [_teacher_task_item(task, total) for task in task_rows]
    items.extend(_notice_task_item(row, total) for row in _notice_rows_for_class(db, class_id))
    items.sort(key=lambda item: item.pop("_sortAt", ""), reverse=True)
    return ok(data={
        "tasks": items
    })


@router.get("/teacher/courses/{class_id}/tasks/{task_id}", response_model=None)
def teacher_course_task_detail(
    class_id: str,
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    _teacher_class_or_404(db, class_id, current_user)
    total = _student_count(db, class_id)
    task = db.query(Task).filter(Task.id == task_id, Task.class_id == class_id, Task.is_published == True).first()
    if task:
        item = _teacher_task_item(task, total)
        item.pop("_sortAt", None)
        scores = [submission.score for submission in task.submissions if submission.score is not None]
        return ok(data={
            **item,
            "description": task.description or "",
            "requirements": [],
            "participantCount": total,
            "averageScore": round(sum(scores) / len(scores), 1) if scores else 0,
            "highestScore": max(scores) if scores else 0,
            "lowestScore": min(scores) if scores else 0,
            "submissions": [
                {
                    "id": submission.id,
                    "studentName": submission.student.real_name if submission.student else "",
                    "studentId": submission.student.student_id if submission.student else "",
                    "groupName": "未分组",
                    "status": "graded" if submission.score is not None else "submitted",
                    "submittedAt": _iso(submission.submitted_at),
                    "score": submission.score,
                }
                for submission in task.submissions
            ],
        })

    notice = next(
        (row for row in _notice_rows_for_class(db, class_id)
         if str((row.extra_data or {}).get("notice_id") or row.id) == str(task_id)),
        None,
    )
    if not notice:
        raise NotFoundException("Task not found")
    item = _notice_task_item(notice, total)
    item.pop("_sortAt", None)
    return ok(data={
        **item,
        "description": notice.content,
        "requirements": [],
        "participantCount": total,
        "submissions": [],
    })


@router.patch("/teacher/courses/{class_id}/tasks/{task_id}/status", response_model=None)
def teacher_course_task_status(
    class_id: str,
    task_id: str,
    body: TeacherTaskStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    _teacher_class_or_404(db, class_id, current_user)
    task = db.query(Task).filter(Task.id == task_id, Task.class_id == class_id).first()
    if not task:
        raise NotFoundException("Task not found")
    if body.is_published is not None:
        task.is_published = body.is_published
    elif body.status:
        task.is_published = body.status in {"已发布", "进行中", "未开始"}
    else:
        task.is_published = not task.is_published
    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ok(data={"id": task.id, "is_published": task.is_published, "status": _task_status(task)})


@router.delete("/teacher/courses/{class_id}/tasks/{task_id}", response_model=None)
def teacher_delete_course_task(
    class_id: str,
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = _teacher_class_or_404(db, class_id, current_user)
    deleted_at = _iso(datetime.now(timezone.utc))
    task = db.query(Task).filter(Task.id == task_id, Task.class_id == class_id).first()
    if task:
        task.is_published = False
        task.updated_at = datetime.now(timezone.utc)
        db.add(task)
        _mark_related_notifications_deleted(db, class_id=class_id, task_id=task.id, deleted_at=deleted_at)
        db.commit()
        return ok(data={"id": task.id, "type": task.task_type, "deleted": True}, message="Task deleted")

    notice_rows = [
        row for row in _notice_rows_for_class(db, class_id)
        if str((row.extra_data or {}).get("notice_id") or row.id) == str(task_id)
    ]
    if not notice_rows:
        raise NotFoundException("Task not found")
    notice = notice_rows[0]
    notice_extra = notice.extra_data or {}
    notice_id = str(notice_extra.get("notice_id") or notice.id)
    _mark_related_notifications_deleted(db, class_id=class_id, notice_id=notice_id, deleted_at=deleted_at)
    if cls.announcement and notice.title in cls.announcement:
        cls.announcement = None
        cls.updated_at = datetime.now(timezone.utc)
        db.add(cls)
    db.commit()
    return ok(data={"id": notice_id, "type": "notice", "deleted": True}, message="Notice deleted")


@router.post("/teacher/courses/{class_id}/notices", response_model=None)
def teacher_publish_notice(
    class_id: str,
    body: TeacherNoticeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = _teacher_class_or_404(db, class_id, current_user)
    notice_id = str(uuid.uuid4())
    cls.announcement = f"{body.title}\n{body.content}".strip()
    cls.updated_at = datetime.now(timezone.utc)
    notice_extra = {
        "source": "teacher_notice",
        "notice_id": notice_id,
        "importance": body.importance,
        "scope": body.scope,
        "attachments": body.attachments,
    }
    recipient_count = _publish_class_notifications(
        db,
        class_id=class_id,
        notification_type="system",
        title=body.title,
        content=body.content,
        extra_data=notice_extra,
    )
    db.add(Notification(
        user_id=current_user.id,
        type="system",
        title=body.title,
        content=body.content,
        extra_data={
            "class_id": class_id,
            **notice_extra,
        },
    ))
    db.commit()
    return ok(data={
        "id": notice_id,
        "title": body.title,
        "recipientCount": recipient_count,
    }, message="Notice published")


@router.post("/teacher/courses/{class_id}/homeworks", response_model=None)
def teacher_create_homework(
    class_id: str,
    body: TeacherHomeworkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    _teacher_class_or_404(db, class_id, current_user)
    question_text = "\n".join(
        f"{index}. {question.get('description', '')}".strip()
        for index, question in enumerate(body.questions, start=1)
        if question.get("description")
    )
    task = Task(
        class_id=class_id,
        created_by=current_user.id,
        title=body.title,
        description=question_text,
        task_type="homework",
        due_date=_parse_datetime(body.deadline),
        max_score=100,
        is_published=True,
    )
    db.add(task)
    db.flush()
    _publish_class_notifications(
        db,
        class_id=class_id,
        notification_type="deadline",
        title=f"新作业：{body.title}",
        content=f"作业已发布，请在截止时间前完成。截止时间：{body.deadline or '未设置'}",
        extra_data={
            "source": "teacher_homework",
            "task_id": task.id,
            "allow_late": body.allowLate,
            "attachments": body.attachments,
        },
    )
    db.commit()
    db.refresh(task)
    return ok(data={"id": task.id, "title": task.title}, message="Homework created")


@router.post("/teacher/courses/{class_id}/exams", response_model=None)
def teacher_create_exam(
    class_id: str,
    body: TeacherExamRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    _teacher_class_or_404(db, class_id, current_user)
    question_text = "\n".join(
        f"{index}. [{question.get('type', '题目')}] {question.get('content', '')}".strip()
        for index, question in enumerate(body.questions, start=1)
        if question.get("content")
    )
    description = (
        f"开始时间：{body.startTime or '未设置'}\n"
        f"结束时间：{body.endTime or '未设置'}\n"
        f"考试时长：{body.duration} 分钟\n\n"
        f"{question_text}"
    ).strip()
    task = Task(
        class_id=class_id,
        created_by=current_user.id,
        title=body.name,
        description=description,
        task_type="exam",
        due_date=_parse_datetime(body.endTime),
        max_score=body.totalScore,
        is_published=True,
    )
    db.add(task)
    db.flush()
    _publish_class_notifications(
        db,
        class_id=class_id,
        notification_type="exam",
        title=f"新考试：{body.name}",
        content=f"考试已发布。开始时间：{body.startTime or '未设置'}，结束时间：{body.endTime or '未设置'}。",
        extra_data={
            "source": "teacher_exam",
            "task_id": task.id,
            "duration": body.duration,
            "attachments": body.attachments,
        },
    )
    db.commit()
    db.refresh(task)
    return ok(data={"id": task.id, "title": task.title}, message="Exam created")


@router.get("/student/courses/{class_id}/home", response_model=None)
def student_course_home(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    tasks = (
        db.query(Task)
        .filter(Task.class_id == class_id, Task.is_published == True)
        .order_by(Task.due_date.asc().nullslast(), Task.created_at.desc())
        .limit(5)
        .all()
    )
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(30)
        .all()
    )
    class_notifications = [
        item for item in notifications
        if (item.extra_data or {}).get("class_id") == class_id
        and not (item.extra_data or {}).get("deleted_at")
    ][:5]
    return ok(data={
        "welcome": {
            "studentName": current_user.real_name,
            "weeklyStudyHours": "0",
            "weeklyGoalRemaining": "0",
            "courseProgress": 0,
            "streakDays": 0,
            "homeworkCompleted": "0/0",
            "learnedChapters": "0",
            "aiQuestions": "0",
        },
        "quickActions": [],
        "notices": [{
            "title": "课程公告",
            "content": cls.announcement or "暂无公告",
            "time": _date(cls.updated_at or cls.created_at),
            "important": False,
            "tag": "公告",
        }] if cls.announcement else [],
        "upcomingTasks": [_student_home_task_item(task) for task in tasks],
        "todayUpdates": [_student_home_update_item(item) for item in class_notifications],
        "classActivities": [],
        "milestones": [],
        "progress": {
            "percent": 0,
            "startDate": _date(cls.created_at),
            "endDate": "",
        },
    })


@router.get("/teacher/courses/{class_id}/home", response_model=None)
def teacher_course_home(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    return ok(data={
        "inviteCode": cls.invite_code,
        "stats": [
            {"label": "学生人数", "value": str(_student_count(db, class_id)), "sub": "当前班级", "icon": "ri-group-line", "iconBg": "bg-blue-50", "iconColor": "text-blue-600", "trend": None},
            {"label": "课程资料", "value": str(_material_count(db, class_id)), "sub": "已上传", "icon": "ri-file-list-line", "iconBg": "bg-green-50", "iconColor": "text-green-600", "trend": None},
            {"label": "任务数量", "value": str(_task_count(db, class_id)), "sub": "全部任务", "icon": "ri-task-line", "iconBg": "bg-orange-50", "iconColor": "text-orange-600", "trend": None},
        ],
        "recentTasks": [],
        "warningStudents": [],
        "activities": [],
        "weeklyStats": [],
        "groupPerformance": [],
    })


@router.get("/student/courses/{class_id}/knowledge-graph", response_model=None)
def student_course_knowledge_graph(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    return _knowledge_graph_payload(db, cls, student=current_user)


@router.get("/teacher/courses/{class_id}/knowledge-graph", response_model=None)
def teacher_course_knowledge_graph(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    return _knowledge_graph_payload(db, cls)


def _graph_source_kind(value: dict[str, Any] | None) -> str:
    return str((value or {}).get("kind") or "").strip().lower()


def _looks_like_graph_noise_label(label: str | None) -> bool:
    normalized = str(label or "").strip()
    if not normalized:
        return True

    normalized_key = re.sub(r"[\s_-]+", "_", normalized.lower())
    if normalized_key in {"unknown", "unknown_entity", "none", "null", "undefined"}:
        return True

    basename = os.path.basename(normalized)
    if GRAPH_FILE_LABEL_RE.search(basename):
        return True
    if GRAPH_UUID_RE.fullmatch(normalized):
        return True
    if GRAPH_FILE_HASH_RE.search(normalized):
        return True
    if re.fullmatch(r"[a-f0-9]{12,}", normalized, flags=re.IGNORECASE):
        return True
    if re.fullmatch(r"[A-Za-z0-9_-]{16,}", normalized) and any(char.isdigit() for char in normalized):
        return True
    if "/" in normalized or "\\" in normalized:
        return True
    compact = re.sub(r"[\s_：:：-]+", "", normalized_key)
    artifact_compacts = {
        re.sub(r"[\s_：:：-]+", "", item.lower())
        for item in GRAPH_ARTIFACT_LABELS
    }
    if normalized.lower() in GRAPH_ARTIFACT_LABELS or compact in artifact_compacts:
        return True
    artifact_patterns = (
        r"^(?:第?\d+[行列]|row\s*\d+|column\s*\d+)$",
        r"^(?:表格?|table)\s*(?:\d+|结构|内容|组织|摘要|描述)?$",
        r"^(?:图片|图像|figure|image)\s*(?:\d+|内容|描述|摘要)?$",
        r"^(?:公式|equation|formula)\s*(?:\d+|内容|描述|摘要)?$",
        r"^(?:页码|页面|page)\s*\d*$",
    )
    if any(re.fullmatch(pattern, normalized, flags=re.IGNORECASE) for pattern in artifact_patterns):
        return True
    return False


def _is_default_graph_entity(entity: KnowledgeEntity) -> bool:
    kind = _graph_source_kind(entity.source_span)
    entity_type = str(entity.entity_type or "").strip().lower()

    if kind in GRAPH_HIDDEN_ENTITY_KINDS or entity_type in {"material", "document", "file", "page", "chunk"}:
        return False
    if _looks_like_graph_noise_label(entity.name):
        return False
    if kind.startswith("candidate_") and float(entity.confidence or 0.0) < 0.7:
        return False
    return True


def _graph_node_color(entity_type: str | None) -> str:
    type_colors = {
        "algorithm": "#7c3aed",
        "formula": "#dc2626",
        "table": "#059669",
        "image": "#ea580c",
        "concept": "#0891b2",
        "conception": "#0891b2",
        "category": "#0f766e",
        "candidate_concept": "#0f766e",
    }
    return type_colors.get((entity_type or "").lower(), "#475569")


def _normalize_graph_entity_type(entity_type: str | None) -> str:
    normalized = str(entity_type or "").strip().lower()
    if normalized in {"", "unknown", "unknown_entity", "none", "null", "undefined"}:
        return "concept"
    if normalized == "conception":
        return "concept"
    return normalized


def _build_graph_positions(entities: list[KnowledgeEntity]) -> dict[str, tuple[float, float]]:
    positions: dict[str, tuple[float, float]] = {}
    for index, entity in enumerate(entities, start=1):
        angle = (2 * math.pi * index) / max(len(entities), 1)
        radius = 220 + 36 * (index % 4)
        positions[entity.id] = (round(math.cos(angle) * radius, 2), round(math.sin(angle) * radius, 2))
    return positions


def _graph_record_material_ids(record: Any) -> set[str]:
    material_ids: set[str] = set()
    provenance = getattr(record, "provenance", None)
    if isinstance(provenance, dict):
        raw_ids = provenance.get("source_material_ids") or provenance.get("material_ids") or []
        if not isinstance(raw_ids, list):
            raw_ids = [raw_ids]
        material_ids.update(str(item) for item in raw_ids if item)

    source_span = getattr(record, "source_span", None)
    if isinstance(source_span, dict):
        for key in ("material_id", "source_material_id", "doc_id", "full_doc_id"):
            value = source_span.get(key)
            if value:
                material_ids.add(str(value))

    source_material_id = getattr(record, "source_material_id", None)
    if source_material_id:
        material_ids.add(str(source_material_id))
    return material_ids


def _graph_record_has_active_material(record: Any, active_material_ids: set[str]) -> bool:
    material_ids = _graph_record_material_ids(record)
    return bool(material_ids & active_material_ids)


def _material_source_summaries(db: Session, material_ids: set[str]) -> dict[str, dict[str, Any]]:
    if not material_ids:
        return {}
    rows = (
        db.query(Material)
        .filter(Material.id.in_(list(material_ids)))
        .all()
    )
    return {
        material.id: {
            "id": material.id,
            "title": material.title,
            "fileName": material.file_name,
            "fileType": material.file_type,
            "mimeType": material.mime_type,
        }
        for material in rows
    }


def _attach_graph_source_summary(record: Any, material_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    material_ids = sorted(_graph_record_material_ids(record))
    materials = [
        material_by_id[material_id]
        for material_id in material_ids
        if material_id in material_by_id
    ]
    if not materials:
        return {}
    primary = materials[0]
    return {
        "sourceMaterials": materials,
        "materialTitle": primary.get("title"),
        "fileName": primary.get("fileName"),
        "sourceName": primary.get("title") or primary.get("fileName"),
    }


def _knowledge_graph_payload(db: Session, cls: Class, student: User | None = None):
    course = _get_course(db, cls.course_id)
    root_id = cls.course_id
    active_material_ids = {
        str(row[0])
        for row in db.query(Material.id).filter(
            Material.class_id == cls.id,
            Material.is_active == True,
        ).all()
        if row[0]
    }
    raw_entities = (
        db.query(KnowledgeEntity)
        .filter(KnowledgeEntity.class_id == cls.id)
        .filter(KnowledgeEntity.status != "rejected")
        .order_by(KnowledgeEntity.confidence.desc(), KnowledgeEntity.created_at.desc())
        .limit(GRAPH_ENTITY_FETCH_LIMIT)
        .all()
    )
    active_raw_entities = [
        entity for entity in raw_entities
        if _graph_record_has_active_material(entity, active_material_ids)
    ]
    entities = [
        entity for entity in active_raw_entities
        if _is_default_graph_entity(entity)
    ][:GRAPH_ENTITY_LIMIT]
    entity_ids = {entity.id for entity in entities}
    mastery_by_entity_id = _student_mastery_by_entity_id(db, student=student, class_id=cls.id) if student else {}
    relations = (
        db.query(KnowledgeRelation)
        .filter(KnowledgeRelation.class_id == cls.id)
        .filter(KnowledgeRelation.source_id.in_(entity_ids))
        .filter(KnowledgeRelation.target_id.in_(entity_ids))
        .order_by(KnowledgeRelation.confidence.desc(), KnowledgeRelation.created_at.desc())
        .limit(160)
        .all()
        if entity_ids
        else []
    )
    relations = [
        relation for relation in relations
        if _graph_source_kind(relation.source_span) not in GRAPH_HIDDEN_RELATION_KINDS
        and _graph_record_has_active_material(relation, active_material_ids)
    ]
    connected_entity_ids = {
        relation.source_id
        for relation in relations
    } | {
        relation.target_id
        for relation in relations
    }
    root_entity_ids = set(connected_entity_ids)
    root_entity_ids.update({
        entity.id for entity in sorted(
            entities,
            key=lambda item: (float(item.confidence or 0.0), str(item.created_at or "")),
            reverse=True,
        )[:GRAPH_ROOT_EDGE_LIMIT]
    })
    for material_id in active_material_ids:
        material_entities = [
            entity for entity in entities
            if material_id in _graph_record_material_ids(entity)
        ]
        root_entity_ids.update({
            entity.id for entity in sorted(
                material_entities,
                key=lambda item: (float(item.confidence or 0.0), str(item.created_at or "")),
                reverse=True,
            )[:GRAPH_ROOT_EDGE_PER_MATERIAL_LIMIT]
        })
    graph_material_ids: set[str] = set()
    for entity in entities:
        graph_material_ids.update(_graph_record_material_ids(entity))
    for relation in relations:
        graph_material_ids.update(_graph_record_material_ids(relation))
    material_by_id = _material_source_summaries(db, graph_material_ids)
    positions = _build_graph_positions(entities)

    nodes = [
        {
            "id": root_id,
            "label": course.name if course else cls.name,
            "x": 0,
            "y": 0,
            "color": "#2563eb",
            "type": "course",
            "description": "课程知识图谱根节点。RAG-Anything 索引完成后将同步更多实体与关系。",
            "expandable": True,
        }
    ]
    for entity in entities:
        x, y = positions.get(entity.id, (0, 0))
        mastery = mastery_by_entity_id.get(entity.id)
        mastery_score = float(mastery.mastery_score) if mastery else None
        entity_type = _normalize_graph_entity_type(entity.entity_type)
        nodes.append({
            "id": entity.id,
            "label": entity.name,
            "x": x,
            "y": y,
            "color": _graph_node_color(entity_type),
            "type": entity_type,
            "description": entity.description or "",
            "confidence": entity.confidence,
            "sourceSpan": entity.source_span or {},
            "provenance": entity.provenance or {},
            "sourceSummary": _attach_graph_source_summary(entity, material_by_id),
            "masteryScore": mastery_score,
            "masteryConfidence": float(mastery.confidence) if mastery else None,
            "masteryEvidenceCount": int(mastery.evidence_count) if mastery else 0,
            "learningStatus": _learning_status_from_mastery(mastery_score),
            "lastLearningEventAt": _iso(mastery.last_event_at) if mastery and mastery.last_event_at else None,
            "expandable": False,
        })

    edges = [
        {
            "id": f"{root_id}->{entity.id}",
            "source": root_id,
            "target": entity.id,
            "label": "concept",
            "weight": 0.3,
        }
        for entity in entities
        if entity.id in root_entity_ids
    ]
    edges.extend([
        {
            "id": relation.id,
            "source": relation.source_id,
            "target": relation.target_id,
            "label": relation.relation_type or "related_to",
            "weight": relation.weight or 1.0,
            "confidence": relation.confidence,
            "sourceSpan": relation.source_span or {},
            "provenance": relation.provenance or {},
            "sourceSummary": _attach_graph_source_summary(relation, material_by_id),
        }
        for relation in relations
    ])

    return ok(data={
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "rootNodeId": root_id,
            "layout": "force",
            "entityCount": len(entities),
            "relationCount": len(relations),
            "rawEntityCount": len(raw_entities),
            "activeRawEntityCount": len(active_raw_entities),
            "filteredEntityCount": max(0, len(raw_entities) - len(entities)),
            "source": "knowledge_entities",
            "defaultView": "concept_graph",
        },
    })


def _student_mastery_by_entity_id(db: Session, *, student: User | None, class_id: str) -> dict[str, StudentConceptMastery]:
    if not student:
        return {}
    concepts = (
        db.query(LearningConcept)
        .filter(
            LearningConcept.class_id == class_id,
            LearningConcept.source_entity_id.isnot(None),
        )
        .all()
    )
    concept_to_entity = {
        concept.id: concept.source_entity_id
        for concept in concepts
        if concept.id and concept.source_entity_id
    }
    if not concept_to_entity:
        return {}
    rows = (
        db.query(StudentConceptMastery)
        .filter(
            StudentConceptMastery.user_id == student.id,
            StudentConceptMastery.class_id == class_id,
            StudentConceptMastery.concept_id.in_(list(concept_to_entity.keys())),
        )
        .all()
    )
    result: dict[str, StudentConceptMastery] = {}
    for row in rows:
        entity_id = concept_to_entity.get(row.concept_id)
        if entity_id:
            result[entity_id] = row
    return result


def _learning_status_from_mastery(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 0.82:
        return "mastered"
    if score >= 0.62:
        return "learning"
    if score >= 0.38:
        return "needs_review"
    return "weak"


@router.get("/student/courses/{class_id}/questions", response_model=None)
def student_course_questions(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    _class_or_404_with_access(db, class_id, current_user)
    return ok(data={"questions": []})


@router.get("/teacher/courses/{class_id}/questions", response_model=None)
def teacher_course_questions(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    _class_or_404_with_access(db, class_id, current_user)
    return ok(data={"questions": []})


@router.get("/student/courses/{class_id}/faqs", response_model=None)
def student_course_faqs(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    _class_or_404_with_access(db, class_id, current_user)
    return ok(data={"faqs": []})


@router.get("/student/courses/{class_id}/discussions", response_model=None)
def student_course_discussions(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    _class_or_404_with_access(db, class_id, current_user)
    return _discussion_payload(db, class_id)


@router.get("/teacher/courses/{class_id}/discussions", response_model=None)
def teacher_course_discussions(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    _class_or_404_with_access(db, class_id, current_user)
    return _discussion_payload(db, class_id)


def _discussion_payload(db: Session, class_id: str):
    items = course_service.list_discussions(db, class_id)
    return ok(data={
        "discussions": [
            {
                "id": item["id"],
                "student": item.get("author_name") or "用户",
                "title": item.get("title") or "课程讨论",
                "content": item.get("content") or "",
                "replies": [],
                "likes": item.get("likes") or 0,
                "time": _iso(item.get("created_at")),
                "pinned": bool(item.get("is_pinned")),
                "liked": False,
            }
            for item in items
        ]
    })


@router.get("/teacher/courses/{class_id}/students", response_model=None)
def teacher_course_students(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    _class_or_404_with_access(db, class_id, current_user)
    members = db.query(ClassMember).filter(
        ClassMember.class_id == class_id,
        ClassMember.role == "student",
    ).all()
    students = []
    for index, membership in enumerate(members, start=1):
        user = db.query(User).filter(User.id == membership.user_id).first()
        if not user:
            continue
        students.append({
            "id": index,
            "name": user.real_name,
            "studentId": user.student_id or user.id,
            "group": 1,
            "progress": 0,
            "homework": 0,
            "attendance": 100,
            "status": "正常",
        })
    return ok(data={"students": students})


@router.get("/ai/recommendations", response_model=None)
def ai_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "student":
        return ok(data=[])
    classes = course_service.get_student_classes(db, current_user.id)
    if not classes:
        return ok(data=[])
    try:
        payload = personalized_recommendation_service.get_personalized_recommendations(
            db,
            current_user,
            class_id=classes[0]["id"],
            surface="ai_panel",
            limit=6,
        )
    except Exception:
        return ok(data=[])
    return ok(data=[
        _personalized_item_to_legacy_ai_recommendation(item, index=index)
        for index, item in enumerate(payload.get("items") or [])
    ])


def _personalized_item_to_legacy_ai_recommendation(item: dict[str, Any], *, index: int) -> dict[str, Any]:
    target_type = str(item.get("type") or "material")
    legacy_type = {
        "material": "pdf",
        "concept": "exercise",
        "faq": "report",
        "mistake": "exercise",
        "flashcard": "template",
        "path": "ppt",
        "task": "exercise",
        "followup": "template",
    }.get(target_type, "pdf")
    evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    keywords = []
    for value in evidence.values():
        if isinstance(value, str) and value.strip():
            keywords.append(value.strip())
        elif isinstance(value, list):
            keywords.extend(str(v).strip() for v in value if str(v).strip())
    if not keywords:
        keywords = [str(item.get("title") or "课程推荐")[:20]]
    return {
        "id": index + 1,
        "title": item.get("title") or "个性化推荐",
        "type": legacy_type,
        "chapter": "个性化推荐",
        "relevance": int(item.get("relevance") or 0),
        "reason": item.get("reason") or item.get("description") or "根据你的学习记录推荐。",
        "matchKeywords": keywords[:5],
    }


@router.get("/ai/messages/{message_id}/sources", response_model=None)
def ai_message_sources(
    message_id: str,
    current_user: User = Depends(get_current_user),
):
    return ok(data=[])


@router.post("/ai/feedback", response_model=None)
async def ai_feedback(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = await _read_json_payload(request)
    updated = _backfill_legacy_feedback_reason(db, current_user.id, payload)
    return ok(data={"reason_backfilled": updated}, message="Feedback recorded")


@router.post("/ai/escalate", response_model=None)
async def ai_escalate(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = await _read_json_payload(request)
    updated = _backfill_legacy_feedback_reason(db, current_user.id, payload)
    return ok(data={"reason_backfilled": updated}, message="Escalation request recorded")


async def _read_json_payload(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _backfill_legacy_feedback_reason(db: Session, user_id: str, payload: dict[str, Any]) -> bool:
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        return False

    question = str(payload.get("questionContent") or payload.get("question_content") or "").strip()
    recent_cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    query = (
        db.query(ReviewItem)
        .join(ChatMessage, ChatMessage.id == ReviewItem.message_id)
        .filter(
            ReviewItem.student_id == user_id,
            ReviewItem.trigger == "dislike",
            ReviewItem.status == "pending",
            ChatMessage.feedback == "dislike",
            (ChatMessage.feedback_reason == None) | (ChatMessage.feedback_reason == ""),
        )
        .order_by(ReviewItem.created_at.desc())
    )
    items = query.limit(8).all()
    target = None
    if question:
        target = next((item for item in items if str(item.question_content or "").strip() == question), None)
    if target is None:
        target = next((item for item in items if _aware_datetime(item.created_at) >= recent_cutoff), None)
    if target is None and items:
        target = items[0]
    if target is None or not target.message:
        return False

    target.message.feedback_reason = reason
    db.add(target.message)
    db.commit()
    return True


def _aware_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


@router.patch("/ai/context", response_model=None)
def ai_context(current_user: User = Depends(get_current_user)):
    return ok(message="Conversation context updated")


@router.patch("/ai/style", response_model=None)
def ai_style(current_user: User = Depends(get_current_user)):
    return ok(message="Conversation style updated")


@router.get("/teacher/ai/questions", response_model=None)
def teacher_ai_questions(current_user: User = Depends(get_current_teacher)):
    return ok(data=[])


@router.get("/teacher/ai/questions/{question_id}", response_model=None)
def teacher_ai_question_detail(
    question_id: int,
    current_user: User = Depends(get_current_teacher),
):
    return ok(data={
        "id": question_id,
        "student": "",
        "avatar": "",
        "question": "",
        "aiAnswer": "",
        "confidence": 0,
        "confidenceLevel": "low",
        "sources": [],
        "time": "",
        "status": "pending",
    })


@router.post("/teacher/ai/questions/reply", response_model=None)
def teacher_ai_question_reply(current_user: User = Depends(get_current_teacher)):
    return ok(message="Reply recorded")


@router.post("/teacher/ai/questions/{question_id}/adopt", response_model=None)
def teacher_ai_question_adopt(
    question_id: int,
    current_user: User = Depends(get_current_teacher),
):
    return ok(message="AI answer adopted")


@router.get("/teacher/ai/feedback", response_model=None)
def teacher_ai_feedback(current_user: User = Depends(get_current_teacher)):
    return ok(data=[])


@router.post("/teacher/ai/feedback/{feedback_id}/resolve", response_model=None)
def teacher_ai_feedback_resolve(
    feedback_id: str,
    current_user: User = Depends(get_current_teacher),
):
    return ok(message="Feedback resolved")


@router.post("/teacher/ai/tools/lesson-plan", response_model=None)
def teacher_ai_lesson_plan(current_user: User = Depends(get_current_teacher)):
    return ok(data="教案生成接口已接入，后续可进一步连接课程知识库和生成模型。")


@router.post("/teacher/ai/tools/exam", response_model=None)
def teacher_ai_exam(current_user: User = Depends(get_current_teacher)):
    return ok(data="试题生成接口已接入，后续可进一步连接课程知识库和生成模型。")


@router.post("/teacher/ai/tools/learning-analysis", response_model=None)
def teacher_ai_learning_analysis(current_user: User = Depends(get_current_teacher)):
    return ok(data="学情分析接口已接入，后续可进一步聚合真实学习行为数据。")


@router.post("/teacher/ai/tools/flashcards", response_model=None)
def teacher_ai_flashcards(current_user: User = Depends(get_current_teacher)):
    return ok(data="闪卡生成接口已接入，后续可进一步结合知识点和错题记录。")
