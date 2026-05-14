import random
import string
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.integrations.rag.graph_schema import resolve_graph_schema
from app.models.course import Class, ClassMember, Course, Discussion, Material, Submission, Task
from app.models.user import User
from app.services import audit_service


def _random_invite_code(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def create_course(db: Session, created_by: str, data: dict) -> Course:
    graph_schema = resolve_graph_schema(
        data.get("graph_schema"),
        name=data.get("name"),
        description=data.get("description"),
    )
    course = Course(
        name=data["name"],
        code=data.get("code"),
        description=data.get("description"),
        cover_color=data.get("cover_color") or "#3b82f6",
        graph_schema=graph_schema,
        created_by=created_by,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def get_course_or_404(db: Session, course_id: str) -> Course:
    course = db.query(Course).filter(Course.id == course_id, Course.is_active == True).first()
    if not course:
        raise NotFoundException("Course not found")
    return course


def list_courses_for_user(db: Session, user: User) -> List[dict]:
    if user.role == "teacher":
        classes = db.query(Class).filter(
            Class.teacher_id == user.id,
            Class.is_active == True,
        ).all()
    elif user.role == "student":
        classes = db.query(Class).join(
            ClassMember, ClassMember.class_id == Class.id
        ).filter(
            ClassMember.user_id == user.id,
            ClassMember.role == "student",
            Class.is_active == True,
        ).all()
    else:
        classes = db.query(Class).filter(Class.is_active == True).all()

    items = []
    for cls in classes:
        course = db.query(Course).filter(Course.id == cls.course_id).first()
        teacher = db.query(User).filter(User.id == cls.teacher_id).first()
        student_count = db.query(ClassMember).filter(
            ClassMember.class_id == cls.id,
            ClassMember.role == "student",
        ).count()
        items.append({
            "id": course.id if course else cls.course_id,
            "class_id": cls.id,
            "name": course.name if course else cls.name,
            "code": course.code if course else None,
            "description": course.description if course else None,
            "cover_color": course.cover_color if course else "#3b82f6",
            "graph_schema": cls.graph_schema or (course.graph_schema if course else None),
            "semester": cls.semester,
            "teacher_id": cls.teacher_id,
            "teacher_name": teacher.real_name if teacher else None,
            "student_count": student_count,
            "invite_code": cls.invite_code,
            "unread": 0,
        })
    return items


def get_course_detail_for_user(db: Session, course_id: str, user: User) -> dict:
    course = get_course_or_404(db, course_id)
    classes = db.query(Class).filter(
        Class.course_id == course_id,
        Class.is_active == True,
    ).all()

    if user.role == "teacher":
        classes = [cls for cls in classes if cls.teacher_id == user.id]
    elif user.role == "student":
        member_class_ids = {
            row.class_id
            for row in db.query(ClassMember).filter(
                ClassMember.user_id == user.id,
                ClassMember.role == "student",
            ).all()
        }
        classes = [cls for cls in classes if cls.id in member_class_ids]

    if user.role != "admin" and not classes and course.created_by != user.id:
        raise ForbiddenException("You do not have access to this course")

    class_items = []
    for cls in classes:
        teacher = db.query(User).filter(User.id == cls.teacher_id).first()
        student_count = db.query(ClassMember).filter(
            ClassMember.class_id == cls.id,
            ClassMember.role == "student",
        ).count()
        class_items.append({
            "id": cls.id,
            "course_id": cls.course_id,
            "teacher_id": cls.teacher_id,
            "teacher_name": teacher.real_name if teacher else None,
            "name": cls.name,
            "semester": cls.semester,
            "invite_code": cls.invite_code,
            "announcement": cls.announcement,
            "is_active": cls.is_active,
            "created_at": cls.created_at,
            "student_count": student_count,
            "course_name": course.name,
            "graph_schema": cls.graph_schema or course.graph_schema,
        })

    return {
        "id": course.id,
        "name": course.name,
        "code": course.code,
        "description": course.description,
        "cover_color": course.cover_color,
        "graph_schema": course.graph_schema,
        "created_by": course.created_by,
        "created_at": course.created_at,
        "classes": class_items,
    }


def create_class(db: Session, teacher_id: str, data: dict) -> Class:
    course = None
    if data.get("course_id"):
        course = db.query(Course).filter(Course.id == data["course_id"], Course.is_active == True).first()
        if not course:
            raise NotFoundException("Course not found")
    if not course:
        course_graph_schema = resolve_graph_schema(
            data.get("graph_schema"),
            name=data.get("name"),
            description=data.get("description"),
        )
        course = Course(
            name=data["name"],
            code=data.get("code"),
            description=data.get("description"),
            cover_color=data.get("cover_color", "#3b82f6"),
            graph_schema=course_graph_schema,
            created_by=teacher_id,
        )
        db.add(course)
        db.flush()
    class_graph_schema = resolve_graph_schema(
        data.get("graph_schema") or course.graph_schema,
        name=f"{course.name or ''} {data.get('name') or ''}".strip(),
        description=data.get("description") or course.description,
    )
    invite_code = _random_invite_code()
    while db.query(Class).filter(Class.invite_code == invite_code).first():
        invite_code = _random_invite_code()
    cls = Class(
        course_id=course.id,
        teacher_id=teacher_id,
        name=data["name"],
        semester=data.get("semester"),
        invite_code=invite_code,
        graph_schema=class_graph_schema,
    )
    db.add(cls)
    db.flush()
    db.add(ClassMember(class_id=cls.id, user_id=teacher_id, role="teacher"))
    db.commit()
    db.refresh(cls)
    teacher = db.query(User).filter(User.id == teacher_id).first()
    audit_service.record_event(
        event_type="class.created",
        actor=teacher,
        actor_id=teacher_id,
        actor_role="teacher",
        target_type="class",
        target_id=cls.id,
        course_id=cls.course_id,
        class_id=cls.id,
        summary=f"教师创建班级：{cls.name}",
        extra_data={
            "class_name": cls.name,
            "course_id": cls.course_id,
            "invite_code": cls.invite_code,
            "semester": cls.semester,
        },
    )
    return cls


def get_teacher_classes(db: Session, teacher_id: str) -> List[dict]:
    teacher = db.query(User).filter(User.id == teacher_id).first()
    classes = db.query(Class).filter(
        Class.teacher_id == teacher_id,
        Class.is_active == True,
    ).all()
    result = []
    for cls in classes:
        student_count = db.query(ClassMember).filter(
            ClassMember.class_id == cls.id,
            ClassMember.role == "student",
        ).count()
        course = db.query(Course).filter(Course.id == cls.course_id).first()
        result.append({
            "id": cls.id,
            "course_id": cls.course_id,
            "course_name": course.name if course else "",
            "teacher_id": cls.teacher_id,
            "teacher_name": teacher.real_name if teacher else "",
            "name": cls.name,
            "semester": cls.semester,
            "invite_code": cls.invite_code,
            "announcement": cls.announcement,
            "is_active": cls.is_active,
            "created_at": cls.created_at,
            "student_count": student_count,
            "graph_schema": cls.graph_schema or (course.graph_schema if course else None),
        })
    return result


def get_student_classes(db: Session, student_id: str) -> List[dict]:
    memberships = db.query(ClassMember).filter(
        ClassMember.user_id == student_id,
        ClassMember.role == "student",
    ).all()
    result = []
    for membership in memberships:
        cls = db.query(Class).filter(Class.id == membership.class_id, Class.is_active == True).first()
        if not cls:
            continue
        course = db.query(Course).filter(Course.id == cls.course_id).first()
        teacher = db.query(User).filter(User.id == cls.teacher_id).first()
        result.append({
            "id": cls.id,
            "course_id": cls.course_id,
            "course_name": course.name if course else "",
            "teacher_id": cls.teacher_id,
            "teacher_name": teacher.real_name if teacher else "",
            "name": cls.name,
            "semester": cls.semester,
            "invite_code": cls.invite_code,
            "announcement": cls.announcement,
            "is_active": cls.is_active,
            "created_at": cls.created_at,
            "graph_schema": cls.graph_schema or (course.graph_schema if course else None),
        })
    return result


def get_class_or_404(db: Session, class_id: str) -> Class:
    cls = db.query(Class).filter(Class.id == class_id, Class.is_active == True).first()
    if not cls:
        raise NotFoundException("Class not found")
    return cls


def join_class_by_invite(db: Session, student_id: str, invite_code: str) -> Class:
    cls = db.query(Class).filter(Class.invite_code == invite_code, Class.is_active == True).first()
    if not cls:
        raise BadRequestException("Invalid invite code")
    existing = db.query(ClassMember).filter(
        ClassMember.class_id == cls.id,
        ClassMember.user_id == student_id,
    ).first()
    if existing:
        raise BadRequestException("You are already in this class")
    db.add(ClassMember(class_id=cls.id, user_id=student_id, role="student"))
    db.commit()
    student = db.query(User).filter(User.id == student_id).first()
    audit_service.record_event(
        event_type="class.student_joined",
        actor=student,
        actor_id=student_id,
        actor_role="student",
        target_type="class",
        target_id=cls.id,
        course_id=cls.course_id,
        class_id=cls.id,
        summary=f"学生加入班级：{cls.name}",
        extra_data={"class_name": cls.name, "invite_code": invite_code},
    )
    return cls


def check_class_member(db: Session, class_id: str, user_id: str) -> bool:
    return db.query(ClassMember).filter(
        ClassMember.class_id == class_id,
        ClassMember.user_id == user_id,
    ).first() is not None


def list_materials(db: Session, class_id: str) -> List[dict]:
    materials = db.query(Material).filter(
        Material.class_id == class_id,
        Material.is_active == True,
    ).order_by(Material.created_at.desc()).all()
    result = []
    for material in materials:
        uploader = db.query(User).filter(User.id == material.uploaded_by).first()
        result.append({
            "id": material.id,
            "class_id": material.class_id,
            "title": material.title,
            "file_name": material.file_name,
            "file_path": material.file_path,
            "file_size": material.file_size,
            "mime_type": material.mime_type,
            "file_type": material.file_type,
            "kb_status": material.kb_status,
            "kb_error": material.kb_error,
            "description": material.description,
            "created_at": material.created_at,
            "uploader_name": uploader.real_name if uploader else "",
        })
    return result


def list_tasks(db: Session, class_id: str, published_only: bool = True) -> List[dict]:
    query = db.query(Task).filter(Task.class_id == class_id)
    if published_only:
        query = query.filter(Task.is_published == True)
    tasks = query.order_by(Task.created_at.desc()).all()
    result = []
    for task in tasks:
        sub_count = db.query(Submission).filter(Submission.task_id == task.id).count()
        result.append({
            "id": task.id,
            "class_id": task.class_id,
            "title": task.title,
            "description": task.description,
            "task_type": task.task_type,
            "due_date": task.due_date,
            "max_score": task.max_score,
            "is_published": task.is_published,
            "created_at": task.created_at,
            "submission_count": sub_count,
        })
    return result


def list_discussions(db: Session, class_id: str, parent_id: Optional[str] = None) -> List[dict]:
    query = db.query(Discussion).filter(
        Discussion.class_id == class_id,
        Discussion.is_active == True,
        Discussion.parent_id == parent_id,
    ).order_by(Discussion.is_pinned.desc(), Discussion.created_at.desc())
    result = []
    for discussion in query.all():
        author = db.query(User).filter(User.id == discussion.author_id).first()
        reply_count = db.query(Discussion).filter(Discussion.parent_id == discussion.id).count()
        result.append({
            "id": discussion.id,
            "class_id": discussion.class_id,
            "author_id": discussion.author_id,
            "author_name": author.real_name if author else "",
            "title": discussion.title,
            "content": discussion.content,
            "parent_id": discussion.parent_id,
            "likes": discussion.likes,
            "is_pinned": discussion.is_pinned,
            "created_at": discussion.created_at,
            "reply_count": reply_count,
        })
    return result
