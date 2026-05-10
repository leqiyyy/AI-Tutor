from datetime import datetime, timedelta, timezone
import json
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
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.core.response import ok
from app.db.base import get_db
from app.models.course import Class, ClassMember, Course, Discussion, Material, Submission, Task
from app.models.chat import ChatMessage, ChatSession, ReviewItem
from app.models.knowledge import KnowledgeEntity, KnowledgeRelation
from app.models.notification import Notification
from app.models.personalization import LearningConcept, StudentConceptMastery
from app.models.user import User
from app.schemas.course import CreateClassRequest, JoinClassRequest
from app.services import auth_service, course_service, kb_service, personalized_recommendation_service, task_service

router = APIRouter(tags=["frontend-compat"])

COLORS = ["blue", "green", "purple", "orange", "teal", "pink", "amber"]
GRAPH_ENTITY_LIMIT = 1000
GRAPH_ENTITY_FETCH_LIMIT = 2000
GRAPH_RELATION_LIMIT = 2000
GRAPH_ROOT_EDGE_LIMIT = 24
GRAPH_ROOT_EDGE_PER_MATERIAL_LIMIT = 10
GRAPH_HIDDEN_ENTITY_KINDS = {
    "material",
    "content_item",
    "candidate_concept_identifier",
    "relation_endpoint",
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


class MaterialRenameRequest(BaseModel):
    name: str


class MaterialShareRequest(BaseModel):
    scope: str = "class"
    message: str | None = None


class CourseContentRequest(BaseModel):
    title: str | None = None
    content: str
    parentId: str | None = None
    parent_id: str | None = None
    attachments: list[str] = Field(default_factory=list)
    reason: str | None = None
    aiAnswer: str | None = None
    ai_answer: str | None = None


class StudentGroupMoveRequest(BaseModel):
    studentIds: list[Any] = Field(default_factory=list)
    targetGroup: int | str | None = None
    target_group: int | str | None = None


class StudentExportRequest(BaseModel):
    format: str = "json"
    fields: list[str] = Field(default_factory=list)


class CourseSubmissionRequest(BaseModel):
    content: str | None = None
    file_path: str | None = None
    filePath: str | None = None
    attachments: list[str] = Field(default_factory=list)
    answers: dict[str, Any] | None = None
    taskType: str | None = None


class GradeSubmissionRequest(BaseModel):
    score: int
    feedback: str | None = None


class TeacherToolRequest(BaseModel):
    prompt: str = ""


class TeacherAiQuestionReplyRequest(BaseModel):
    questionId: str
    reply: str


QUESTION_TITLE_PREFIX = "[student_question] "


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


def _material_preview_note(raw: dict[str, Any]) -> str:
    source = raw.get("preview_source")
    if source == "original_file":
        return "已直接读取原始文本文件，上传后即可预览。"
    if source in {"extracted_text", "chunks"}:
        return "当前展示解析文本；完整 AI 检索仍需等待索引完成。"
    status = raw.get("kb_status") or "pending"
    if status in {"pending", "processing"}:
        return "资料已上传，正在解析/索引；当前可下载原文件，文本预览稍后可用。"
    return "暂无可预览文本，可先下载原文件查看。"


def _material_download_url(course_id: str, file_id: str, file_name: str | None = None) -> str:
    query = f"?filename={quote(file_name or '')}" if file_name else ""
    return f"/api/v1/courses/{course_id}/files/{file_id}/download{query}"


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


def _question_storage_title(title: str | None) -> str:
    cleaned = str(title or "课程提问").strip() or "课程提问"
    if cleaned.startswith(QUESTION_TITLE_PREFIX):
        return cleaned
    return f"{QUESTION_TITLE_PREFIX}{cleaned}"


def _question_display_title(title: str | None) -> str:
    text = str(title or "").strip()
    if text.startswith(QUESTION_TITLE_PREFIX):
        return text[len(QUESTION_TITLE_PREFIX):].strip() or "课程提问"
    return text or "课程提问"


def _is_question_discussion(row: Discussion) -> bool:
    return str(row.title or "").startswith(QUESTION_TITLE_PREFIX)


def _discussion_author_name(db: Session, author_id: str | None) -> str:
    user = db.query(User).filter(User.id == author_id).first() if author_id else None
    return (user.real_name or user.email or "用户") if user else "用户"


def _discussion_reply_payload(db: Session, reply: Discussion) -> dict[str, Any]:
    author = db.query(User).filter(User.id == reply.author_id).first()
    role = author.role if author else ""
    return {
        "author": (author.real_name or author.email or "用户") if author else "用户",
        "content": reply.content or "",
        "time": _iso(reply.created_at),
        "isTeacher": role == "teacher",
        "isStudent": role == "student",
    }


def _discussion_replies(db: Session, parent_id: str) -> list[Discussion]:
    return (
        db.query(Discussion)
        .filter(
            Discussion.parent_id == parent_id,
            Discussion.is_active == True,
        )
        .order_by(Discussion.created_at.asc())
        .all()
    )


def _student_members_with_users(db: Session, class_id: str) -> list[tuple[ClassMember, User]]:
    rows: list[tuple[ClassMember, User]] = []
    memberships = (
        db.query(ClassMember)
        .filter(ClassMember.class_id == class_id, ClassMember.role == "student")
        .order_by(ClassMember.joined_at.asc())
        .all()
    )
    for membership in memberships:
        user = db.query(User).filter(User.id == membership.user_id).first()
        if user:
            rows.append((membership, user))
    return rows


def _resolve_student_member_from_display_id(db: Session, class_id: str, value: Any) -> tuple[ClassMember, User] | None:
    raw = str(value)
    members = _student_members_with_users(db, class_id)
    for index, (membership, user) in enumerate(members, start=1):
        if raw in {str(index), str(user.id), str(user.student_id or "")}:
            return membership, user
    return None


def _resolve_student_from_display_id(db: Session, class_id: str, value: Any) -> User | None:
    resolved = _resolve_student_member_from_display_id(db, class_id, value)
    return resolved[1] if resolved else None


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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    auth_service.change_password(
        db,
        current_user,
        str(payload.get("oldPassword") or ""),
        str(payload.get("newPassword") or ""),
        str(payload.get("confirmPassword") or ""),
    )
    return ok(data={"status": "updated", "message": "密码修改成功"})


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
        start_at = _extract_exam_start_time(task)
        if start_at:
            now = datetime.now(start_at.tzinfo) if start_at.tzinfo else datetime.now(timezone.utc).replace(tzinfo=None)
            if start_at > now:
                return "未开始"
    if task.due_date:
        now = datetime.now(task.due_date.tzinfo) if task.due_date.tzinfo else datetime.now(timezone.utc).replace(tzinfo=None)
        if task.due_date < now:
            return "已结束"
    return "进行中"


def _task_extra(task: Task) -> dict[str, Any]:
    return task.extra_data if isinstance(task.extra_data, dict) else {}


def _extract_exam_start_time(task: Task) -> datetime | None:
    extra = _task_extra(task)
    start_value = extra.get("startTime") or extra.get("start_time")
    if start_value:
        return _parse_datetime(start_value)
    description = task.description
    if not description:
        return None
    match = re.search(r"开始时间：([^\n]+)", description)
    if not match:
        return None
    return _parse_datetime(match.group(1))


def _task_questions_for_student(task: Task) -> list[dict[str, Any]]:
    extra = _task_extra(task)
    structured_questions = extra.get("questions")
    if isinstance(structured_questions, list):
        questions = []
        for index, item in enumerate(structured_questions, start=1):
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or item.get("description") or "").strip()
            if not content:
                continue
            questions.append({
                "id": int(item.get("id") or index),
                "content": content,
                "type": _normalize_frontend_question_type(str(item.get("type") or "")),
                "answer": "",
            })
        if questions:
            return questions

    description = task.description or ""
    questions: list[dict[str, Any]] = []
    for line in description.splitlines():
        text = line.strip()
        if not text:
            continue
        if text.startswith(("开始时间：", "结束时间：", "考试时长：")):
            continue
        match = re.match(r"^(\d+)[.、]\s*(?:[【\\[]([^】\\]]+)[】\\]])?\s*(.+)$", text)
        if not match:
            continue
        index = int(match.group(1))
        question_type = _normalize_frontend_question_type(match.group(2) or "")
        content = match.group(3).strip()
        if content:
            questions.append({
                "id": index,
                "content": content,
                "type": question_type,
                "answer": "",
            })
    if not questions and description.strip():
        questions.append({
            "id": 1,
            "content": description.strip(),
            "type": "text",
            "answer": "",
        })
    return questions


def _normalize_frontend_question_type(value: str) -> str:
    normalized = value.strip().lower()
    if any(token in normalized for token in ("code", "编程", "代码", "program")):
        return "code"
    return "text"


def _homework_questions_payload(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload = []
    for index, question in enumerate(questions, start=1):
        content = str(question.get("description") or question.get("content") or "").strip()
        if not content:
            continue
        payload.append({
            "id": index,
            "type": _normalize_frontend_question_type(str(question.get("type") or "")),
            "content": content,
            "answer": str(question.get("answer") or "").strip(),
            "score": question.get("score"),
        })
    return payload


def _exam_questions_payload(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload = []
    for index, question in enumerate(questions, start=1):
        content = str(question.get("content") or question.get("description") or "").strip()
        if not content:
            continue
        payload.append({
            "id": index,
            "type": str(question.get("type") or "简答题").strip() or "简答题",
            "content": content,
            "score": question.get("score"),
        })
    return payload


def _student_task_status(task: Task, submission: Submission | None) -> str:
    if submission:
        if submission.score is not None or submission.status == "graded":
            return "graded"
        return "submitted"
    if task.due_date:
        now = datetime.now(task.due_date.tzinfo) if task.due_date.tzinfo else datetime.now(timezone.utc).replace(tzinfo=None)
        if task.due_date < now:
            return "overdue"
    return "pending"


def _assert_task_submission_window(task: Task) -> None:
    if task.task_type != "exam":
        return
    start_at = _extract_exam_start_time(task)
    if start_at:
        now = datetime.now(start_at.tzinfo) if start_at.tzinfo else datetime.now(timezone.utc).replace(tzinfo=None)
        if now < start_at:
            raise BadRequestException("考试尚未开始")
    if task.due_date:
        now = datetime.now(task.due_date.tzinfo) if task.due_date.tzinfo else datetime.now(timezone.utc).replace(tzinfo=None)
        if now > task.due_date:
            raise BadRequestException("考试已结束，不能提交")


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
    extra = _task_extra(task)
    return {
        "id": task.id,
        "type": task.task_type or "homework",
        "title": task.title,
        "deadline": _iso(task.due_date),
        "startTime": extra.get("startTime") or extra.get("start_time"),
        "duration": extra.get("duration"),
        "submitted": len(task.submissions or []),
        "total": total,
        "status": _task_status(task),
        "publishDate": _date(task.created_at),
        "attachments": extra.get("attachments") if isinstance(extra.get("attachments"), list) else [],
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
                "status": item.get("kb_status") or "pending",
                "kbStatus": item.get("kb_status") or "pending",
                "kbError": item.get("kb_error"),
            }
            for item in materials
        ]
    })


@router.get("/student/courses/{class_id}/materials/{file_id}/analysis", response_model=None)
def student_course_material_analysis(
    class_id: str,
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    raw = kb_service.get_material_analysis(db, cls.course_id, file_id, current_user)
    keywords = raw.get("keywords") or []
    return ok(data={
        "fileId": file_id,
        "summary": raw.get("summary") or "资料仍在解析中，解析完成后将展示自动摘要。",
        "keyPoints": keywords[:8],
        "difficulties": [
            {"title": keyword, "difficulty": "中等"}
            for keyword in keywords[:5]
        ],
        "recommendedStudyDuration": "30 分钟",
        "generatedAt": _iso(datetime.now(timezone.utc)),
        "raw": raw,
    })


@router.get("/student/courses/{class_id}/materials/{file_id}/preview", response_model=None)
def student_course_material_preview(
    class_id: str,
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    raw = kb_service.get_material_preview(db, cls.course_id, file_id, current_user)
    preview_type = "video" if raw.get("file_type") in {"video", "mp4"} else "document"
    return ok(data={
        "fileId": file_id,
        "previewType": preview_type,
        "previewUrl": "",
        "note": _material_preview_note(raw),
        "textContent": raw.get("preview_text") or "",
        "textTruncated": bool(raw.get("preview_text_truncated")),
        "previewSource": raw.get("preview_source"),
        "chunkCount": raw.get("chunk_count", 0),
        "pageCount": None,
        "raw": raw,
    })


@router.get("/student/courses/{class_id}/materials/{file_id}/download", response_model=None)
def student_course_material_download(
    class_id: str,
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    material = kb_service.get_material_for_user(db, cls.course_id, file_id, current_user)
    return ok(data={
        "fileId": material.id,
        "fileName": material.file_name,
        "downloadUrl": _material_download_url(cls.course_id, material.id, material.file_name),
    })


@router.get("/student/courses/{class_id}/search", response_model=None)
def student_course_search(
    class_id: str,
    q: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    return ok(data=kb_service.search_course_content(db, cls.course_id, q, current_user))


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
                "kbError": item.get("kb_error"),
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


@router.patch("/teacher/courses/{class_id}/files/{file_id}", response_model=None)
def teacher_rename_course_file(
    class_id: str,
    file_id: str,
    body: MaterialRenameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    material = kb_service.get_material_for_user(db, cls.course_id, file_id, current_user)
    if material.class_id != cls.id:
        raise NotFoundException("Material not found")
    material.title = body.name.strip() or material.title
    material.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(material)
    return ok(data={
        "id": material.id,
        "name": material.title or material.file_name,
    }, message="File renamed")


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


@router.post("/teacher/courses/{class_id}/files/{file_id}/share", response_model=None)
def teacher_share_course_file(
    class_id: str,
    file_id: str,
    body: MaterialShareRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    material = kb_service.get_material_for_user(db, cls.course_id, file_id, current_user)
    if material.class_id != cls.id or not material.is_active:
        raise NotFoundException("Material not found")
    recipient_count = _publish_class_notifications(
        db,
        class_id=class_id,
        notification_type="system",
        title=f"课程资料分享：{material.title or material.file_name}",
        content=body.message or "教师分享了一份课程资料，请及时查看。",
        extra_data={
            "source": "material_share",
            "material_id": material.id,
            "scope": body.scope,
        },
    )
    db.add(Notification(
        user_id=current_user.id,
        type="system",
        title=f"已分享资料：{material.title or material.file_name}",
        content=body.message or "",
        extra_data={
            "class_id": class_id,
            "source": "material_share",
            "material_id": material.id,
            "recipient_count": recipient_count,
        },
    ))
    db.commit()
    return ok(data={
        "file_id": material.id,
        "recipientCount": recipient_count,
    }, message="File shared")


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
        "note": _material_preview_note(raw),
        "textContent": raw.get("preview_text") or "",
        "textTruncated": bool(raw.get("preview_text_truncated")),
        "previewSource": raw.get("preview_source"),
        "chunkCount": raw.get("chunk_count", 0),
        "raw": raw,
    })


@router.get("/teacher/courses/{class_id}/materials/{file_id}/download", response_model=None)
def teacher_course_material_download(
    class_id: str,
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    material = kb_service.get_material_for_user(db, cls.course_id, file_id, current_user)
    return ok(data={
        "fileId": material.id,
        "fileName": material.file_name,
        "downloadUrl": _material_download_url(cls.course_id, material.id, material.file_name),
    })


@router.get("/student/courses/{class_id}/tasks", response_model=None)
def student_course_tasks(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    _class_or_404_with_access(db, class_id, current_user)
    tasks = course_service.list_tasks(db, class_id, published_only=True)
    task_ids = [item["id"] for item in tasks]
    task_by_id = {
        task.id: task
        for task in db.query(Task).filter(Task.id.in_(task_ids)).all()
    } if task_ids else {}
    submissions = {
        submission.task_id: submission
        for submission in db.query(Submission).filter(
            Submission.student_id == current_user.id,
            Submission.task_id.in_(task_ids),
        ).all()
    } if task_ids else {}
    return ok(data={
        "tasks": [
            {
                "id": item["id"],
                "title": item["title"],
                "deadline": _iso(item.get("due_date")),
                "status": _student_task_status(
                    task_by_id[item["id"]],
                    submissions.get(item["id"]),
                ),
                "score": submissions.get(item["id"]).score if submissions.get(item["id"]) else None,
                "urgent": bool(item.get("due_date") and not submissions.get(item["id"])),
                "questions": _task_questions_for_student(task_by_id[item["id"]]),
                "isExam": item.get("task_type") == "exam",
                "startTime": _task_extra(task_by_id[item["id"]]).get("startTime"),
                "duration": _task_extra(task_by_id[item["id"]]).get("duration"),
                "teacherComment": submissions.get(item["id"]).feedback if submissions.get(item["id"]) else None,
            }
            for item in tasks
            if item["id"] in task_by_id
        ]
    })


@router.post("/student/courses/{class_id}/tasks/{task_id}/submissions", response_model=None)
def student_submit_course_task(
    class_id: str,
    task_id: str,
    body: CourseSubmissionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    task = db.query(Task).filter(Task.id == str(task_id), Task.class_id == cls.id).first()
    if not task:
        raise NotFoundException("Task not found")
    _assert_task_submission_window(task)
    file_path = body.file_path or body.filePath
    if not file_path and body.attachments:
        file_path = ",".join(str(item) for item in body.attachments if item)
    content = body.content
    if content is None and body.answers is not None:
        content = json.dumps({
            "answers": body.answers,
            "taskType": body.taskType or task.task_type,
        }, ensure_ascii=False)
    submission = task_service.submit_task(
        db,
        task_id=task.id,
        student=current_user,
        content=content,
        file_path=file_path,
    )
    db.add(Notification(
        user_id=cls.teacher_id,
        type="system",
        title=f"作业提交：{task.title}",
        content=f"{current_user.real_name or current_user.email} 已提交任务。",
        extra_data={
            "class_id": class_id,
            "task_id": task.id,
            "submission_id": submission.id,
            "source": "task_submission",
        },
    ))
    db.commit()
    return ok(data={
        "id": submission.id,
        "status": submission.status,
        "submittedAt": _iso(submission.submitted_at),
    }, message="Task submitted")


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
            "questions": _task_questions_for_student(task),
            "extraData": _task_extra(task),
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


@router.post("/teacher/courses/{class_id}/tasks/{task_id}/submissions/{submission_id}/grade", response_model=None)
def teacher_grade_course_submission(
    class_id: str,
    task_id: str,
    submission_id: str,
    body: GradeSubmissionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = _teacher_class_or_404(db, class_id, current_user)
    task = db.query(Task).filter(Task.id == task_id, Task.class_id == cls.id).first()
    if not task:
        raise NotFoundException("Task not found")
    submission = db.query(Submission).filter(
        Submission.id == submission_id,
        Submission.task_id == task.id,
    ).first()
    if not submission:
        raise NotFoundException("Submission not found")
    submission.score = max(0, min(int(body.score), int(task.max_score or 100)))
    submission.feedback = body.feedback or ""
    submission.status = "graded"
    submission.graded_at = datetime.now(timezone.utc)
    db.add(Notification(
        user_id=submission.student_id,
        type="system",
        title=f"任务已批改：{task.title}",
        content=f"得分：{submission.score}。{submission.feedback or ''}".strip(),
        extra_data={
            "class_id": class_id,
            "task_id": task.id,
            "submission_id": submission.id,
            "source": "task_graded",
        },
    ))
    db.commit()
    db.refresh(submission)
    return ok(data={
        "id": submission.id,
        "score": submission.score,
        "feedback": submission.feedback,
        "status": submission.status,
        "gradedAt": _iso(submission.graded_at),
    }, message="Submission graded")


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
    structured_questions = _homework_questions_payload(body.questions)
    question_text = "\n".join(
        f"{question['id']}. {question['content']}".strip()
        for question in structured_questions
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
        extra_data={
            "kind": "homework",
            "deadline": body.deadline,
            "allowLate": body.allowLate,
            "attachments": body.attachments,
            "questions": structured_questions,
        },
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
    structured_questions = _exam_questions_payload(body.questions)
    question_text = "\n".join(
        f"{question['id']}. [{question['type']}] {question['content']}".strip()
        for question in structured_questions
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
        extra_data={
            "kind": "exam",
            "startTime": body.startTime,
            "endTime": body.endTime,
            "duration": body.duration,
            "totalScore": body.totalScore,
            "attachments": body.attachments,
            "questions": structured_questions,
        },
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
    description = str(entity.description or "").strip()

    if kind in GRAPH_HIDDEN_ENTITY_KINDS or entity_type in {"material", "document", "file", "page", "chunk"}:
        return False
    if description.startswith("RAG-Anything relation endpoint from "):
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
    raw_entity_total = (
        db.query(KnowledgeEntity)
        .filter(KnowledgeEntity.class_id == cls.id)
        .filter(KnowledgeEntity.status != "rejected")
        .count()
    )
    active_raw_entities = [
        entity for entity in raw_entities
        if _graph_record_has_active_material(entity, active_material_ids)
    ]
    active_raw_entity_total = (
        db.query(KnowledgeEntity)
        .filter(KnowledgeEntity.class_id == cls.id)
        .filter(KnowledgeEntity.status != "rejected")
        .filter(KnowledgeEntity.source_material_id.in_(list(active_material_ids)))
        .count()
        if active_material_ids
        else 0
    )
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
        .limit(GRAPH_RELATION_LIMIT)
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
            "rawEntityCount": raw_entity_total,
            "fetchedRawEntityCount": len(raw_entities),
            "activeRawEntityCount": active_raw_entity_total,
            "fetchedActiveRawEntityCount": len(active_raw_entities),
            "filteredEntityCount": max(0, len(active_raw_entities) - len(entities)),
            "entityDisplayLimit": GRAPH_ENTITY_LIMIT,
            "relationDisplayLimit": GRAPH_RELATION_LIMIT,
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
    rows = (
        db.query(Discussion)
        .filter(
            Discussion.class_id == class_id,
            Discussion.author_id == current_user.id,
            Discussion.parent_id == None,
            Discussion.is_active == True,
        )
        .order_by(Discussion.created_at.desc())
        .all()
    )
    return ok(data={
        "questions": [
            {
                "id": row.id,
                "title": _question_display_title(row.title),
                "content": row.content or "",
                "time": _iso(row.created_at),
                "status": "answered" if any(
                    reply.get("isTeacher")
                    for reply in [_discussion_reply_payload(db, item) for item in _discussion_replies(db, row.id)]
                ) else "pending",
                "replies": [_discussion_reply_payload(db, item) for item in _discussion_replies(db, row.id)],
            }
            for row in rows
            if _is_question_discussion(row)
        ]
    })


@router.post("/student/courses/{class_id}/questions", response_model=None)
def student_create_course_question(
    class_id: str,
    body: CourseContentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    _class_or_404_with_access(db, class_id, current_user)
    question = Discussion(
        class_id=class_id,
        author_id=current_user.id,
        title=_question_storage_title(body.title),
        content=body.content.strip(),
    )
    db.add(question)
    db.flush()
    cls = db.query(Class).filter(Class.id == class_id).first()
    if cls:
        db.add(Notification(
            user_id=cls.teacher_id,
            type="system",
            title=f"学生提问：{_question_display_title(question.title)}",
            content=question.content[:300],
            extra_data={
                "class_id": class_id,
                "question_id": question.id,
                "source": "student_question",
                "attachments": body.attachments,
            },
        ))
    db.commit()
    db.refresh(question)
    return ok(data={"id": question.id}, message="Question submitted")


@router.get("/teacher/courses/{class_id}/questions", response_model=None)
def teacher_course_questions(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    _class_or_404_with_access(db, class_id, current_user)
    rows = (
        db.query(Discussion)
        .filter(
            Discussion.class_id == class_id,
            Discussion.parent_id == None,
            Discussion.is_active == True,
        )
        .order_by(Discussion.created_at.desc())
        .all()
    )
    questions = []
    for row in rows:
        if not _is_question_discussion(row):
            continue
        replies = [_discussion_reply_payload(db, item) for item in _discussion_replies(db, row.id)]
        questions.append({
            "id": row.id,
            "student": _discussion_author_name(db, row.author_id),
            "question": row.content or _question_display_title(row.title),
            "confidence": "人工提问",
            "time": _iso(row.created_at),
            "status": "answered" if any(reply.get("isTeacher") for reply in replies) else "pending",
            "replies": replies,
        })
    return ok(data={"questions": questions})


def _reply_course_question(
    *,
    class_id: str,
    question_id: str,
    body: CourseContentRequest,
    db: Session,
    current_user: User,
) -> dict[str, Any]:
    _class_or_404_with_access(db, class_id, current_user)
    question = db.query(Discussion).filter(
        Discussion.id == str(question_id),
        Discussion.class_id == class_id,
        Discussion.parent_id == None,
        Discussion.is_active == True,
    ).first()
    if not question or not _is_question_discussion(question):
        raise NotFoundException("Question not found")
    reply = Discussion(
        class_id=class_id,
        author_id=current_user.id,
        content=body.content.strip(),
        parent_id=question.id,
    )
    db.add(reply)
    if current_user.role == "teacher":
        db.add(Notification(
            user_id=question.author_id,
            type="system",
            title=f"教师回复：{_question_display_title(question.title)}",
            content=reply.content[:300],
            extra_data={
                "class_id": class_id,
                "question_id": question.id,
                "source": "teacher_question_reply",
            },
        ))
    db.commit()
    db.refresh(reply)
    return {"id": reply.id, **_discussion_reply_payload(db, reply)}


@router.post("/student/courses/{class_id}/questions/{question_id}/replies", response_model=None)
def student_reply_course_question(
    class_id: str,
    question_id: str,
    body: CourseContentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    return ok(data=_reply_course_question(
        class_id=class_id,
        question_id=question_id,
        body=body,
        db=db,
        current_user=current_user,
    ), message="Reply created")


@router.post("/teacher/courses/{class_id}/questions/{question_id}/replies", response_model=None)
def teacher_reply_course_question(
    class_id: str,
    question_id: str,
    body: CourseContentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    return ok(data=_reply_course_question(
        class_id=class_id,
        question_id=question_id,
        body=body,
        db=db,
        current_user=current_user,
    ), message="Reply created")


@router.post("/student/courses/{class_id}/teacher-help-requests", response_model=None)
def student_request_teacher_help(
    class_id: str,
    body: CourseContentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    details = [
        body.content.strip(),
        f"申请原因：{body.reason}" if body.reason else "",
        f"AI回答：{body.aiAnswer or body.ai_answer}" if (body.aiAnswer or body.ai_answer) else "",
    ]
    question = Discussion(
        class_id=class_id,
        author_id=current_user.id,
        title=_question_storage_title(body.title or "AI 转人工申请"),
        content="\n\n".join(item for item in details if item),
    )
    db.add(question)
    db.flush()
    db.add(Notification(
        user_id=cls.teacher_id,
        type="system",
        title=f"AI 转人工：{_question_display_title(question.title)}",
        content=question.content[:300],
        extra_data={
            "class_id": class_id,
            "question_id": question.id,
            "source": "teacher_help_request",
            "reason": body.reason,
        },
    ))
    db.commit()
    db.refresh(question)
    return ok(data={"id": question.id}, message="Teacher help request submitted")


@router.get("/student/courses/{class_id}/faqs", response_model=None)
def student_course_faqs(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    _class_or_404_with_access(db, class_id, current_user)
    rows = (
        db.query(ReviewItem)
        .filter(
            ReviewItem.class_id == class_id,
            ReviewItem.status == "resolved",
            ReviewItem.teacher_answer.isnot(None),
        )
        .order_by(ReviewItem.reviewed_at.desc().nullslast(), ReviewItem.created_at.desc())
        .limit(30)
        .all()
    )
    return ok(data={
        "faqs": [
            {
                "id": index,
                "title": _faq_title(item.question_content),
                "date": _date(item.reviewed_at or item.created_at),
                "views": 0,
                "content": item.teacher_answer or item.ai_answer,
                "attachments": [],
            }
            for index, item in enumerate(rows, start=1)
        ]
    })


def _faq_title(question: str | None) -> str:
    text = re.sub(r"\s+", " ", str(question or "课程答疑")).strip()
    if len(text) <= 32:
        return text
    return f"{text[:32]}..."


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
    items = (
        db.query(Discussion)
        .filter(
            Discussion.class_id == class_id,
            Discussion.parent_id == None,
            Discussion.is_active == True,
        )
        .order_by(Discussion.is_pinned.desc(), Discussion.created_at.desc())
        .all()
    )
    return ok(data={
        "discussions": [
            {
                "id": item.id,
                "student": _discussion_author_name(db, item.author_id),
                "title": item.title or "课程讨论",
                "content": item.content or "",
                "replies": [_discussion_reply_payload(db, reply) for reply in _discussion_replies(db, item.id)],
                "likes": item.likes or 0,
                "time": _iso(item.created_at),
                "pinned": bool(item.is_pinned),
                "liked": False,
            }
            for item in items
            if not _is_question_discussion(item)
        ]
    })


@router.post("/student/courses/{class_id}/discussions", response_model=None)
def student_create_course_discussion(
    class_id: str,
    body: CourseContentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    _class_or_404_with_access(db, class_id, current_user)
    discussion = Discussion(
        class_id=class_id,
        author_id=current_user.id,
        title=(body.title or "课程讨论").strip(),
        content=body.content.strip(),
    )
    db.add(discussion)
    db.commit()
    db.refresh(discussion)
    return ok(data={"id": discussion.id}, message="Discussion created")


@router.post("/teacher/courses/{class_id}/discussions", response_model=None)
def teacher_create_course_discussion(
    class_id: str,
    body: CourseContentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    _class_or_404_with_access(db, class_id, current_user)
    discussion = Discussion(
        class_id=class_id,
        author_id=current_user.id,
        title=(body.title or "课程讨论").strip(),
        content=body.content.strip(),
    )
    db.add(discussion)
    db.commit()
    db.refresh(discussion)
    return ok(data={"id": discussion.id}, message="Discussion created")


def _reply_course_discussion(
    *,
    class_id: str,
    discussion_id: str,
    body: CourseContentRequest,
    db: Session,
    current_user: User,
) -> dict[str, Any]:
    _class_or_404_with_access(db, class_id, current_user)
    parent = db.query(Discussion).filter(
        Discussion.id == str(discussion_id),
        Discussion.class_id == class_id,
        Discussion.is_active == True,
    ).first()
    if not parent:
        raise NotFoundException("Discussion not found")
    reply = Discussion(
        class_id=class_id,
        author_id=current_user.id,
        content=body.content.strip(),
        parent_id=parent.id,
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return {"id": reply.id, **_discussion_reply_payload(db, reply)}


@router.post("/student/courses/{class_id}/discussions/{discussion_id}/replies", response_model=None)
def student_reply_course_discussion(
    class_id: str,
    discussion_id: str,
    body: CourseContentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    return ok(data=_reply_course_discussion(
        class_id=class_id,
        discussion_id=discussion_id,
        body=body,
        db=db,
        current_user=current_user,
    ), message="Reply created")


@router.post("/teacher/courses/{class_id}/discussions/{discussion_id}/replies", response_model=None)
def teacher_reply_course_discussion(
    class_id: str,
    discussion_id: str,
    body: CourseContentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    return ok(data=_reply_course_discussion(
        class_id=class_id,
        discussion_id=discussion_id,
        body=body,
        db=db,
        current_user=current_user,
    ), message="Reply created")


def _toggle_course_discussion_like(
    *,
    class_id: str,
    discussion_id: str,
    db: Session,
    current_user: User,
) -> dict[str, Any]:
    _class_or_404_with_access(db, class_id, current_user)
    discussion = db.query(Discussion).filter(
        Discussion.id == str(discussion_id),
        Discussion.class_id == class_id,
        Discussion.is_active == True,
    ).first()
    if not discussion:
        raise NotFoundException("Discussion not found")
    discussion.likes = max(0, int(discussion.likes or 0) + 1)
    db.commit()
    return {"id": discussion.id, "likes": discussion.likes}


@router.post("/student/courses/{class_id}/discussions/{discussion_id}/like", response_model=None)
def student_like_course_discussion(
    class_id: str,
    discussion_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    return ok(data=_toggle_course_discussion_like(
        class_id=class_id,
        discussion_id=discussion_id,
        db=db,
        current_user=current_user,
    ))


@router.post("/teacher/courses/{class_id}/discussions/{discussion_id}/like", response_model=None)
def teacher_like_course_discussion(
    class_id: str,
    discussion_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    return ok(data=_toggle_course_discussion_like(
        class_id=class_id,
        discussion_id=discussion_id,
        db=db,
        current_user=current_user,
    ))


@router.post("/teacher/courses/{class_id}/discussions/{discussion_id}/pin", response_model=None)
def teacher_pin_course_discussion(
    class_id: str,
    discussion_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    _class_or_404_with_access(db, class_id, current_user)
    discussion = db.query(Discussion).filter(
        Discussion.id == str(discussion_id),
        Discussion.class_id == class_id,
        Discussion.is_active == True,
    ).first()
    if not discussion:
        raise NotFoundException("Discussion not found")
    discussion.is_pinned = not bool(discussion.is_pinned)
    db.commit()
    return ok(data={"id": discussion.id, "pinned": discussion.is_pinned})


@router.get("/teacher/courses/{class_id}/students", response_model=None)
def teacher_course_students(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    _class_or_404_with_access(db, class_id, current_user)
    students = []
    for index, (membership, user) in enumerate(_student_members_with_users(db, class_id), start=1):
        students.append({
            "id": index,
            "name": user.real_name,
            "studentId": user.student_id or user.id,
            "group": membership.group_no or 1,
            "progress": 0,
            "homework": 0,
            "attendance": 100,
            "status": "正常",
        })
    return ok(data={"students": students})


@router.post("/teacher/courses/{class_id}/students/{student_id}/warning-reminders", response_model=None)
def teacher_send_warning_reminder(
    class_id: str,
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    _class_or_404_with_access(db, class_id, current_user)
    student = _resolve_student_from_display_id(db, class_id, student_id)
    if not student:
        raise NotFoundException("Student not found")
    db.add(Notification(
        user_id=student.id,
        type="system",
        title="学习提醒",
        content="教师提醒你关注近期学习进度，请及时查看课程任务和学习建议。",
        extra_data={
            "class_id": class_id,
            "source": "teacher_warning_reminder",
            "teacher_id": current_user.id,
        },
    ))
    db.commit()
    return ok(data={"studentId": student.student_id or student.id}, message="Reminder sent")


@router.patch("/teacher/courses/{class_id}/students/group", response_model=None)
def teacher_move_students_to_group(
    class_id: str,
    body: StudentGroupMoveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    _class_or_404_with_access(db, class_id, current_user)
    target_group = body.targetGroup if body.targetGroup is not None else body.target_group
    try:
        group_no = int(target_group)
    except (TypeError, ValueError):
        group_no = 1
    group_no = max(1, min(group_no, 99))
    resolved = [
        item for item in (
            _resolve_student_member_from_display_id(db, class_id, student_id)
            for student_id in body.studentIds
        )
        if item is not None
    ]
    for membership, _ in resolved:
        membership.group_no = group_no
    db.commit()
    return ok(data={
        "movedCount": len(resolved),
        "targetGroup": group_no,
        "persisted": True,
    }, message="Group move persisted")


@router.post("/teacher/courses/{class_id}/students/export", response_model=None)
def teacher_export_students(
    class_id: str,
    body: StudentExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    _class_or_404_with_access(db, class_id, current_user)
    students = []
    for index, (membership, user) in enumerate(_student_members_with_users(db, class_id), start=1):
        students.append({
            "id": index,
            "name": user.real_name,
            "studentId": user.student_id or user.id,
            "email": user.email,
            "group": membership.group_no or 1,
            "progress": 0,
            "homework": 0,
            "attendance": 100,
            "status": "正常",
        })
    return ok(data={
        "format": body.format,
        "fields": body.fields,
        "students": students,
        "count": len(students),
    }, message="Students exported")


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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    message = (
        db.query(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .filter(ChatMessage.id == message_id)
        .first()
    )
    if not message:
        raise NotFoundException("Message not found")
    session = message.session
    if session.user_id != current_user.id:
        teacher_access = (
            current_user.role == "teacher"
            and db.query(Class).filter(
                Class.id == session.class_id,
                Class.teacher_id == current_user.id,
            ).first()
        )
        if not teacher_access and current_user.role != "admin":
            raise ForbiddenException("You do not have access to this message")
    sources = message.sources
    if not sources and message.citations:
        sources = [{
            "name": citation.source_name,
            "page": citation.page,
            "type": citation.source_type,
            "score": citation.score,
            "chunk_id": citation.chunk_id,
            **(citation.extra_data or {}),
        } for citation in message.citations]
    return ok(data=sources or [])


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
def teacher_ai_questions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    class_ids = _teacher_active_class_ids(db, current_user)
    if not class_ids:
        return ok(data=[])
    rows = (
        db.query(ReviewItem)
        .filter(ReviewItem.class_id.in_(class_ids))
        .order_by(ReviewItem.created_at.desc())
        .limit(80)
        .all()
    )
    return ok(data=[_teacher_ai_question_payload(db, item) for item in rows])


@router.get("/teacher/ai/questions/{question_id}", response_model=None)
def teacher_ai_question_detail(
    question_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    item = _teacher_review_item_or_404(db, question_id, current_user)
    return ok(data=_teacher_ai_question_payload(db, item))


@router.post("/teacher/ai/questions/reply", response_model=None)
def teacher_ai_question_reply(
    body: TeacherAiQuestionReplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    item = _teacher_review_item_or_404(db, body.questionId, current_user)
    item.teacher_answer = body.reply.strip()
    item.status = "resolved"
    item.reviewed_by = current_user.id
    item.reviewed_at = datetime.now(timezone.utc)
    if item.message:
        item.message.needs_review = False
    db.commit()
    return ok(data=_teacher_ai_question_payload(db, item), message="Reply recorded")


@router.post("/teacher/ai/questions/{question_id}/adopt", response_model=None)
def teacher_ai_question_adopt(
    question_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    item = _teacher_review_item_or_404(db, question_id, current_user)
    item.teacher_answer = item.ai_answer
    item.status = "resolved"
    item.reviewed_by = current_user.id
    item.reviewed_at = datetime.now(timezone.utc)
    if item.message:
        item.message.needs_review = False
    db.commit()
    return ok(data=_teacher_ai_question_payload(db, item), message="AI answer adopted")


@router.get("/teacher/ai/feedback", response_model=None)
def teacher_ai_feedback(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    class_ids = _teacher_active_class_ids(db, current_user)
    if not class_ids:
        return ok(data=[])
    rows = (
        db.query(ReviewItem)
        .filter(ReviewItem.class_id.in_(class_ids), ReviewItem.status == "pending")
        .order_by(ReviewItem.created_at.desc())
        .limit(80)
        .all()
    )
    return ok(data=[_teacher_ai_feedback_payload(db, item) for item in rows])


@router.post("/teacher/ai/feedback/{feedback_id}/resolve", response_model=None)
def teacher_ai_feedback_resolve(
    feedback_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    item = _teacher_review_item_or_404(db, feedback_id, current_user)
    item.status = "resolved"
    item.reviewed_by = current_user.id
    item.reviewed_at = datetime.now(timezone.utc)
    if item.message:
        item.message.needs_review = False
    db.commit()
    return ok(data=_teacher_ai_feedback_payload(db, item), message="Feedback resolved")


def _teacher_active_class_ids(db: Session, teacher: User) -> list[str]:
    return [
        cls.id
        for cls in db.query(Class).filter(
            Class.teacher_id == teacher.id,
            Class.is_active == True,
        ).all()
    ]


def _teacher_review_item_or_404(db: Session, review_id: str, teacher: User) -> ReviewItem:
    class_ids = _teacher_active_class_ids(db, teacher)
    item = db.query(ReviewItem).filter(
        ReviewItem.id == str(review_id),
        ReviewItem.class_id.in_(class_ids),
    ).first() if class_ids else None
    if not item:
        raise NotFoundException("Review item not found")
    return item


def _confidence_level(value: float | None) -> str:
    confidence = float(value or 0.0)
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.55:
        return "medium"
    return "low"


def _review_sources_for_teacher(item: ReviewItem) -> list[dict[str, Any]]:
    message = item.message
    raw_sources = (message.sources if message else None) or []
    if not raw_sources and message and message.citations:
        raw_sources = [{
            "name": citation.source_name,
            "page": citation.page,
            "type": citation.source_type,
            "score": citation.score,
            "chunk_id": citation.chunk_id,
        } for citation in message.citations]
    result = []
    for source in raw_sources:
        if not isinstance(source, dict):
            continue
        result.append({
            "name": source.get("name") or source.get("file") or source.get("source") or "课程资料",
            "page": int(source.get("page") or source.get("page_start") or 0),
        })
    return result


def _teacher_ai_question_payload(db: Session, item: ReviewItem) -> dict[str, Any]:
    student = db.query(User).filter(User.id == item.student_id).first()
    confidence = item.message.confidence if item.message else 0.0
    status = "pending"
    if item.status == "resolved":
        status = "adopted" if (item.teacher_answer or "").strip() == (item.ai_answer or "").strip() else "replied"
    return {
        "id": item.id,
        "student": student.real_name if student else "学生",
        "avatar": student.real_name[:1] if student and student.real_name else "学",
        "question": item.question_content,
        "aiAnswer": item.ai_answer,
        "confidence": round(float(confidence or 0.0) * 100),
        "confidenceLevel": _confidence_level(confidence),
        "sources": _review_sources_for_teacher(item),
        "time": _iso(item.created_at),
        "status": status,
        "teacherReply": item.teacher_answer,
    }


def _teacher_ai_feedback_payload(db: Session, item: ReviewItem) -> dict[str, Any]:
    student = db.query(User).filter(User.id == item.student_id).first()
    cls = db.query(Class).filter(Class.id == item.class_id).first()
    return {
        "id": item.id,
        "messageId": item.message_id,
        "classId": item.class_id,
        "studentId": item.student_id,
        "studentName": student.real_name if student else "学生",
        "conversationTitle": cls.name if cls else "课程对话",
        "questionContent": item.question_content,
        "aiAnswer": item.ai_answer,
        "teacherAnswer": item.teacher_answer,
        "reason": item.message.feedback_reason if item.message and item.message.feedback_reason else item.trigger,
        "timestamp": _iso(item.created_at),
        "status": "resolved" if item.status == "resolved" else "pending",
        "trigger": item.trigger,
        "reviewContext": item.message.sources if item.message else {},
    }


@router.post("/teacher/ai/tools/lesson-plan", response_model=None)
def teacher_ai_lesson_plan(
    body: TeacherToolRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    context = _teacher_tool_context(db, current_user)
    material_lines = "\n".join(f"- {item}" for item in context["materials"][:6]) or "- 暂无已上传资料"
    task_lines = "\n".join(f"- {item}" for item in context["tasks"][:4]) or "- 暂无近期任务"
    prompt = body.prompt.strip() or "请基于当前课程生成一份教学设计"
    return ok(data=(
        f"# 教案草稿\n\n"
        f"## 生成要求\n{prompt}\n\n"
        f"## 课程上下文\n"
        f"- 班级数：{context['class_count']}\n"
        f"- 学生数：{context['student_count']}\n"
        f"- 待审核 AI 回答：{context['pending_reviews']}\n\n"
        f"## 可参考资料\n{material_lines}\n\n"
        f"## 近期任务\n{task_lines}\n\n"
        f"## 建议教学流程\n"
        f"1. 导入：用 1 个贴近学生已有问题的情境引出本节主题。\n"
        f"2. 概念讲解：围绕资料中的核心概念，拆成 3 个递进知识点。\n"
        f"3. 例题演示：选择一个容易出错的步骤做板书/屏幕演示。\n"
        f"4. 课堂练习：安排 2 道基础题和 1 道迁移题，要求学生说明理由。\n"
        f"5. 形成性评价：用 AI 助教收集学生疑问，低置信回答进入教师审核。\n"
        f"6. 课后巩固：把本节关键概念生成闪卡，并将错误率高的问题加入错题本。\n"
    ))


@router.post("/teacher/ai/tools/exam", response_model=None)
def teacher_ai_exam(
    body: TeacherToolRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    context = _teacher_tool_context(db, current_user)
    concepts = context["concepts"][:6] or ["核心概念", "资料理解", "综合应用"]
    prompt = body.prompt.strip() or "请生成一份阶段测验"
    questions = []
    for index, concept in enumerate(concepts[:5], start=1):
        questions.append(
            f"{index}. 【简答题】围绕“{concept}”设计一道能够检验理解深度的问题，并要求学生写出关键推理过程。"
        )
    return ok(data=(
        f"# 试题草稿\n\n"
        f"## 生成要求\n{prompt}\n\n"
        f"## 命题范围\n" + "\n".join(f"- {concept}" for concept in concepts) + "\n\n"
        f"## 题目建议\n" + "\n".join(questions) + "\n\n"
        f"## 评分建议\n"
        f"- 概念准确：40%\n"
        f"- 推理过程：35%\n"
        f"- 表达与规范：15%\n"
        f"- 能结合课程资料或案例：10%\n"
    ))


@router.post("/teacher/ai/tools/learning-analysis", response_model=None)
def teacher_ai_learning_analysis(
    body: TeacherToolRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    context = _teacher_tool_context(db, current_user)
    prompt = body.prompt.strip() or "请生成当前班级学情分析"
    return ok(data=(
        f"# 学情分析草稿\n\n"
        f"## 分析要求\n{prompt}\n\n"
        f"## 当前数据概况\n"
        f"- 班级数：{context['class_count']}\n"
        f"- 学生数：{context['student_count']}\n"
        f"- 已发布任务：{context['task_count']}\n"
        f"- 课程资料：{context['material_count']}\n"
        f"- 待审核 AI 回答：{context['pending_reviews']}\n\n"
        f"## 教学风险\n"
        f"- 若待审核回答较多，说明学生问题集中或资料证据不足，应优先处理审核队列。\n"
        f"- 若任务数较少，建议补充形成性练习以支撑学生画像。\n"
        f"- 若资料数较少，个性化推荐和 RAG 检索覆盖面会受限。\n\n"
        f"## 后续建议\n"
        f"1. 对低掌握知识点补充讲解资料。\n"
        f"2. 将高频错误问题发布为集中答疑。\n"
        f"3. 把教师纠错回流到班级知识库，提升后续 AI 助教稳定性。\n"
    ))


@router.post("/teacher/ai/tools/flashcards", response_model=None)
def teacher_ai_flashcards(
    body: TeacherToolRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    context = _teacher_tool_context(db, current_user)
    concepts = context["concepts"][:8] or ["课程核心概念", "关键步骤", "易错点"]
    cards = "\n".join(
        f"{index}. 正面：{concept} 是什么？\n   背面：请用课程资料中的定义、例子和常见误区进行回答。"
        for index, concept in enumerate(concepts, start=1)
    )
    prompt = body.prompt.strip() or "请生成学生复习闪卡"
    return ok(data=(
        f"# 闪卡草稿\n\n"
        f"## 生成要求\n{prompt}\n\n"
        f"{cards}\n\n"
        f"## 使用建议\n"
        f"- 初次学习后立即复习一次。\n"
        f"- 选择“忘记/模糊”的卡片自动进入次日复习。\n"
        f"- 与错题本联动，把反复遗忘的卡片转为针对性练习。\n"
    ))


def _teacher_tool_context(db: Session, teacher: User) -> dict[str, Any]:
    classes = db.query(Class).filter(
        Class.teacher_id == teacher.id,
        Class.is_active == True,
    ).order_by(Class.created_at.desc()).all()
    class_ids = [cls.id for cls in classes]
    materials = (
        db.query(Material)
        .filter(Material.class_id.in_(class_ids), Material.is_active == True)
        .order_by(Material.created_at.desc())
        .limit(12)
        .all()
        if class_ids
        else []
    )
    tasks = (
        db.query(Task)
        .filter(Task.class_id.in_(class_ids))
        .order_by(Task.created_at.desc())
        .limit(8)
        .all()
        if class_ids
        else []
    )
    entities = (
        db.query(KnowledgeEntity)
        .filter(KnowledgeEntity.class_id.in_(class_ids), KnowledgeEntity.status != "rejected")
        .order_by(KnowledgeEntity.confidence.desc(), KnowledgeEntity.created_at.desc())
        .limit(12)
        .all()
        if class_ids
        else []
    )
    student_count = (
        db.query(ClassMember)
        .filter(ClassMember.class_id.in_(class_ids), ClassMember.role == "student")
        .count()
        if class_ids
        else 0
    )
    pending_reviews = (
        db.query(ReviewItem)
        .filter(ReviewItem.class_id.in_(class_ids), ReviewItem.status == "pending")
        .count()
        if class_ids
        else 0
    )
    return {
        "class_count": len(classes),
        "student_count": student_count,
        "material_count": len(materials),
        "task_count": len(tasks),
        "pending_reviews": pending_reviews,
        "materials": [
            f"{material.title or material.file_name}（{material.kb_status or 'pending'}）"
            for material in materials
        ],
        "tasks": [
            f"{task.title}（{task.task_type}，{'已发布' if task.is_published else '未发布'}）"
            for task in tasks
        ],
        "concepts": [
            entity.name
            for entity in entities
            if entity.name and not _looks_like_graph_noise_label(entity.name)
        ],
    }
