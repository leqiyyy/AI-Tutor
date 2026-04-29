from datetime import datetime, timezone
import math
from typing import Any

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.v1 import kb as kb_api
from app.core.deps import get_current_admin, get_current_student, get_current_teacher, get_current_user
from app.core.exceptions import ForbiddenException
from app.core.response import ok
from app.db.base import get_db
from app.models.course import Class, ClassMember, Course, Discussion, Material, Task
from app.models.knowledge import KnowledgeEntity, KnowledgeRelation
from app.models.notification import Notification
from app.models.user import User
from app.schemas.course import CreateClassRequest, JoinClassRequest
from app.services import course_service, kb_service

router = APIRouter(tags=["frontend-compat"])

COLORS = ["blue", "green", "purple", "orange", "teal", "pink", "amber"]


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return ""


def _date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    return ""


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
        .limit(limit)
        .all()
    )
    return [
        {
            "id": item.id,
            "type": item.type,
            "title": item.title,
            "content": item.content,
            "time": _date(item.created_at),
            "unread": not bool(item.is_read),
        }
        for item in rows
    ]


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

    return ok(data={
        "greetingName": current_user.real_name,
        "stats": {
            "activeCourses": len(classes),
            "pendingTasks": pending_tasks,
            "completionRate": 0,
        },
        "pendingItems": [],
        "progressCourses": progress_courses,
        "recommendations": [],
        "activities": [],
        "notifications": _notifications_for_user(db, current_user.id),
        "courses": courses,
    })


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
        "generatedAt": datetime.now(timezone.utc).isoformat(),
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
        "note": raw.get("preview_text") or raw.get("summary") or "暂无可预览内容",
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
    tasks = course_service.list_tasks(db, class_id, published_only=False)
    total = _student_count(db, class_id)
    return ok(data={
        "tasks": [
            {
                "id": item["id"],
                "type": item.get("task_type") or "homework",
                "title": item["title"],
                "deadline": _iso(item.get("due_date")),
                "submitted": item.get("submission_count") or 0,
                "total": total,
                "status": "已发布" if item.get("is_published") else "草稿",
                "publishDate": _date(item.get("created_at")),
                "attachments": [],
            }
            for item in tasks
        ]
    })


@router.get("/student/courses/{class_id}/home", response_model=None)
def student_course_home(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
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
        "upcomingTasks": [],
        "todayUpdates": [],
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
    return _knowledge_graph_payload(db, cls)


@router.get("/teacher/courses/{class_id}/knowledge-graph", response_model=None)
def teacher_course_knowledge_graph(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = _class_or_404_with_access(db, class_id, current_user)
    return _knowledge_graph_payload(db, cls)


def _knowledge_graph_payload(db: Session, cls: Class):
    course = _get_course(db, cls.course_id)
    root_id = cls.course_id
    entities = (
        db.query(KnowledgeEntity)
        .filter(KnowledgeEntity.class_id == cls.id)
        .filter(KnowledgeEntity.status != "rejected")
        .order_by(KnowledgeEntity.confidence.desc(), KnowledgeEntity.created_at.desc())
        .limit(80)
        .all()
    )
    entity_ids = {entity.id for entity in entities}
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

    preferred_kinds = {"material", "raganything_entity", "raganything_relation", "content_item", "entity_material_link"}
    has_explicit_entities = any((entity.source_span or {}).get("kind") == "raganything_entity" for entity in entities)
    if has_explicit_entities:
        entities = [
            entity for entity in entities
            if (entity.source_span or {}).get("kind") in preferred_kinds
        ]
        entity_ids = {entity.id for entity in entities}
        relations = [
            relation for relation in relations
            if relation.source_id in entity_ids
            and relation.target_id in entity_ids
            and (relation.source_span or {}).get("kind") in preferred_kinds
        ]

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
    type_colors = {
        "material": "#64748b",
        "algorithm": "#7c3aed",
        "formula": "#dc2626",
        "table": "#059669",
        "image": "#ea580c",
        "concept": "#0891b2",
        "conception": "#0891b2",
        "category": "#0f766e",
    }
    for index, entity in enumerate(entities, start=1):
        angle = (2 * math.pi * index) / max(len(entities), 1)
        radius = 180 + 30 * (index % 3)
        nodes.append({
            "id": entity.id,
            "label": entity.name,
            "x": round(math.cos(angle) * radius, 2),
            "y": round(math.sin(angle) * radius, 2),
            "color": type_colors.get((entity.entity_type or "").lower(), "#475569"),
            "type": entity.entity_type or "concept",
            "description": entity.description or "",
            "confidence": entity.confidence,
            "sourceSpan": entity.source_span or {},
            "provenance": entity.provenance or {},
            "expandable": False,
        })

    edges = [
        {
            "id": f"{root_id}->{entity.id}",
            "source": root_id,
            "target": entity.id,
            "label": "includes",
            "weight": 0.3,
        }
        for entity in entities
        if (entity.source_span or {}).get("kind") == "material"
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
            "source": "knowledge_entities",
        },
    })


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
def ai_recommendations(current_user: User = Depends(get_current_user)):
    return ok(data=[])


@router.get("/ai/messages/{message_id}/sources", response_model=None)
def ai_message_sources(
    message_id: str,
    current_user: User = Depends(get_current_user),
):
    return ok(data=[])


@router.post("/ai/feedback", response_model=None)
def ai_feedback(current_user: User = Depends(get_current_user)):
    return ok(message="Feedback recorded")


@router.post("/ai/escalate", response_model=None)
def ai_escalate(current_user: User = Depends(get_current_user)):
    return ok(message="Escalation request recorded")


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
