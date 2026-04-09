from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.ai.mock_rag import get_rag_engine
from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.course import Class, ClassMember, Course, Material
from app.models.knowledge import FileParseTask
from app.models.user import User


def _accessible_classes_for_course(db: Session, course_id: str, user: User) -> list[Class]:
    query = db.query(Class).filter(Class.course_id == course_id, Class.is_active == True)
    if user.role == "admin":
        return query.all()
    if user.role == "teacher":
        return query.filter(Class.teacher_id == user.id).all()

    memberships = db.query(ClassMember).filter(
        ClassMember.user_id == user.id,
        ClassMember.role == "student",
    ).all()
    class_ids = [membership.class_id for membership in memberships]
    if not class_ids:
        return []
    return query.filter(Class.id.in_(class_ids)).all()


def ensure_course_access(db: Session, course_id: str, user: User) -> Course:
    course = db.query(Course).filter(Course.id == course_id, Course.is_active == True).first()
    if not course:
        raise NotFoundException("Course not found")
    accessible_classes = _accessible_classes_for_course(db, course_id, user)
    if user.role != "admin" and not accessible_classes and course.created_by != user.id:
        raise ForbiddenException("You do not have access to this course")
    return course


def resolve_class_for_course(
    db: Session,
    course_id: str,
    user: User,
    class_id: Optional[str] = None,
) -> Class:
    accessible_classes = _accessible_classes_for_course(db, course_id, user)
    if class_id:
        for cls in accessible_classes:
            if cls.id == class_id:
                return cls
        raise ForbiddenException("You do not have access to the requested class")
    if accessible_classes:
        return sorted(accessible_classes, key=lambda cls: cls.created_at)[0]
    raise NotFoundException("No accessible class found for this course")


def list_course_files(db: Session, course_id: str, user: User) -> list[dict]:
    ensure_course_access(db, course_id, user)
    class_ids = [cls.id for cls in _accessible_classes_for_course(db, course_id, user)] if user.role != "admin" else [
        cls.id for cls in db.query(Class).filter(Class.course_id == course_id, Class.is_active == True).all()
    ]
    if not class_ids and user.role != "admin":
        return []
    query = db.query(Material).join(Class, Class.id == Material.class_id).filter(
        Class.course_id == course_id,
        Material.is_active == True,
    )
    if class_ids:
        query = query.filter(Material.class_id.in_(class_ids))
    items = query.order_by(Material.created_at.desc()).all()
    return [{
        "id": item.id,
        "class_id": item.class_id,
        "title": item.title,
        "file_name": item.file_name,
        "file_path": item.file_path,
        "file_size": item.file_size,
        "mime_type": item.mime_type,
        "file_type": item.file_type,
        "kb_status": item.kb_status,
        "kb_error": item.kb_error,
        "description": item.description,
        "created_at": item.created_at,
    } for item in items]


def get_material_for_user(db: Session, course_id: str, file_id: str, user: User) -> Material:
    ensure_course_access(db, course_id, user)
    material = db.query(Material).join(
        Class, Class.id == Material.class_id
    ).filter(
        Material.id == file_id,
        Class.course_id == course_id,
        Material.is_active == True,
    ).first()
    if not material:
        raise NotFoundException("File not found")

    if user.role == "admin":
        return material
    accessible_classes = {cls.id for cls in _accessible_classes_for_course(db, course_id, user)}
    if material.class_id not in accessible_classes and material.uploaded_by != user.id:
        raise ForbiddenException("You do not have access to this file")
    return material


def get_material_preview(db: Session, course_id: str, file_id: str, user: User) -> dict:
    material = get_material_for_user(db, course_id, file_id, user)
    parse_task = db.query(FileParseTask).filter(FileParseTask.material_id == material.id).first()
    extracted_text = (parse_task.extracted_text if parse_task else "") or ""
    return {
        "id": material.id,
        "file_name": material.file_name,
        "mime_type": material.mime_type,
        "file_type": material.file_type,
        "kb_status": material.kb_status,
        "preview_text": extracted_text[:1500],
        "summary": parse_task.summary if parse_task else None,
    }


def get_material_analysis(db: Session, course_id: str, file_id: str, user: User) -> dict:
    material = get_material_for_user(db, course_id, file_id, user)
    parse_task = db.query(FileParseTask).filter(FileParseTask.material_id == material.id).first()
    if not parse_task:
        return {
            "file_id": material.id,
            "status": "pending",
            "summary": None,
            "keywords": [],
            "chunk_count": 0,
            "chunks": [],
        }

    extra = parse_task.extra_data or {}
    return {
        "file_id": material.id,
        "status": parse_task.status,
        "parser_name": parse_task.parser_name,
        "summary": parse_task.summary,
        "keywords": extra.get("keywords", []),
        "chunk_count": len(parse_task.chunks or []),
        "chunks": (parse_task.chunks or [])[:5],
        "content_items": extra.get("content_items", []),
    }


def search_course_content(db: Session, course_id: str, query: str, user: User) -> list[dict]:
    ensure_course_access(db, course_id, user)
    tasks = db.query(FileParseTask).filter(FileParseTask.course_id == course_id, FileParseTask.status == "completed").all()
    query_terms = _terms(query)
    results = []
    for task in tasks:
        for chunk in task.chunks or []:
            chunk_text = chunk.get("text", "")
            overlap = len(query_terms & _terms(chunk_text))
            if overlap <= 0:
                continue
            results.append({
                "material_id": task.material_id,
                "source_name": chunk.get("source_name"),
                "source_type": chunk.get("source_type"),
                "page": chunk.get("page"),
                "chunk_id": chunk.get("chunk_id"),
                "score": round(overlap / max(len(query_terms), 1), 3),
                "snippet": chunk_text[:280],
            })
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:10]


def get_parse_task_for_user(db: Session, task_id: str, user: User) -> dict | None:
    task = db.query(FileParseTask).filter(FileParseTask.id == task_id).first()
    if not task:
        return None
    course = ensure_course_access(db, task.course_id, user)
    _ = course
    return get_rag_engine().get_parse_task(task_id)


def _terms(text: str) -> set[str]:
    import re

    latin = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    cjk = re.findall(r"[\u4e00-\u9fff]{2,8}", text)
    return {token for token in [*latin, *cjk] if token}
