import os
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

import app.storage as storage
from app.ai.mock_rag import get_rag_engine
from app.core.deps import get_current_student, get_current_teacher, get_current_user
from app.core.exceptions import ForbiddenException, NotFoundException
from app.core.response import ok
from app.db.base import get_db
from app.models.course import Class, ClassMember, Discussion, Material, Task
from app.models.user import User
from app.schemas.course import (
    CreateClassRequest,
    CreateDiscussionRequest,
    CreateTaskRequest,
    JoinClassRequest,
    UpdateClassRequest,
)
from app.services import course_service

router = APIRouter(prefix="/classes", tags=["classes"])


@router.post("", response_model=None)
def create_class(
    body: CreateClassRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = course_service.create_class(db, current_user.id, body.model_dump())
    return ok(
        data={
            "id": cls.id,
            "course_id": cls.course_id,
            "name": cls.name,
            "invite_code": cls.invite_code,
            "created_at": cls.created_at,
        }
    )


@router.get("", response_model=None)
def list_my_classes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "teacher":
        data = course_service.get_teacher_classes(db, current_user.id)
    else:
        data = course_service.get_student_classes(db, current_user.id)
    return ok(data=data)


@router.get("/{class_id}", response_model=None)
def get_class(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cls = course_service.get_class_or_404(db, class_id)
    if not course_service.check_class_member(db, class_id, current_user.id) and current_user.role != "admin":
        raise ForbiddenException("You are not a member of this class")

    teacher = db.query(User).filter(User.id == cls.teacher_id).first()
    from app.models.course import Course

    course = db.query(Course).filter(Course.id == cls.course_id).first()
    student_count = db.query(ClassMember).filter(
        ClassMember.class_id == class_id,
        ClassMember.role == "student",
    ).count()
    return ok(data={
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
    })


@router.put("/{class_id}", response_model=None)
def update_class(
    class_id: str,
    body: UpdateClassRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = course_service.get_class_or_404(db, class_id)
    if cls.teacher_id != current_user.id:
        raise ForbiddenException("Only the class teacher can update this class")
    for field, value in body.model_dump(exclude_none=True).items():
        if hasattr(cls, field):
            setattr(cls, field, value)
    db.commit()
    db.refresh(cls)
    return ok(data={"id": cls.id, "name": cls.name})


@router.post("/join", response_model=None)
def join_class(
    body: JoinClassRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    cls = course_service.join_class_by_invite(db, current_user.id, body.invite_code)
    return ok(data={"class_id": cls.id, "class_name": cls.name}, message="Joined class successfully")


@router.post("/{class_id}/invite", response_model=None)
def get_or_issue_invite_code(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = course_service.get_class_or_404(db, class_id)
    if cls.teacher_id != current_user.id:
        raise ForbiddenException("Only the class teacher can access the invite code")
    return ok(data={"class_id": cls.id, "invite_code": cls.invite_code})


@router.get("/{class_id}/materials", response_model=None)
def list_materials(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not course_service.check_class_member(db, class_id, current_user.id) and current_user.role != "admin":
        raise ForbiddenException("You are not a member of this class")
    return ok(data=course_service.list_materials(db, class_id))


@router.post("/{class_id}/materials", response_model=None)
async def upload_material(
    class_id: str,
    file: UploadFile = File(...),
    title: str = Form(None),
    description: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = course_service.get_class_or_404(db, class_id)
    if cls.teacher_id != current_user.id:
        raise ForbiddenException("Only the class teacher can upload materials")

    suffix = os.path.splitext(file.filename or "")[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    file_size = len(content)
    mime_type = file.content_type or "application/octet-stream"
    storage_key, stored_path = storage.save_upload(class_id, file.filename or "file", tmp_path)
    os.unlink(tmp_path)

    ext = suffix.lower().lstrip(".")
    file_type_map = {
        "pdf": "pdf",
        "docx": "docx",
        "doc": "docx",
        "pptx": "ppt",
        "ppt": "ppt",
        "md": "md",
        "txt": "txt",
        "png": "image",
        "jpg": "image",
        "jpeg": "image",
    }
    file_type = file_type_map.get(ext, "other")

    material = Material(
        class_id=class_id,
        uploaded_by=current_user.id,
        title=title or file.filename or "Untitled",
        file_name=file.filename or "file",
        file_path=stored_path,
        file_size=file_size,
        mime_type=mime_type,
        file_type=file_type,
        description=description,
        kb_status="pending",
    )
    db.add(material)
    db.commit()
    db.refresh(material)

    try:
        rag = get_rag_engine()
        file_path = storage.get_file_path(class_id, storage_key) or stored_path
        await rag.ingest_material(class_id, material.id, file_path, mime_type)
        material.kb_status = "indexed"
    except Exception as exc:
        material.kb_status = "failed"
        material.kb_error = str(exc)
    db.commit()

    return ok(
        data={
            "id": material.id,
            "title": material.title,
            "file_path": material.file_path,
            "kb_status": material.kb_status,
        },
        message="Material uploaded successfully",
    )


@router.delete("/{class_id}/materials/{material_id}", response_model=None)
def delete_material(
    class_id: str,
    material_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    material = db.query(Material).filter(
        Material.id == material_id,
        Material.class_id == class_id,
    ).first()
    if not material:
        raise NotFoundException("Material not found")
    material.is_active = False
    db.commit()
    return ok(message="Material deleted")


@router.get("/{class_id}/tasks", response_model=None)
def list_tasks(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not course_service.check_class_member(db, class_id, current_user.id) and current_user.role != "admin":
        raise ForbiddenException("You are not a member of this class")
    published_only = current_user.role == "student"
    return ok(data=course_service.list_tasks(db, class_id, published_only))


@router.post("/{class_id}/tasks", response_model=None)
def create_task(
    class_id: str,
    body: CreateTaskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = course_service.get_class_or_404(db, class_id)
    if cls.teacher_id != current_user.id:
        raise ForbiddenException("Only the class teacher can create tasks")
    task = Task(
        class_id=class_id,
        created_by=current_user.id,
        **body.model_dump(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return ok(data={"id": task.id, "title": task.title})


@router.put("/{class_id}/tasks/{task_id}/status", response_model=None)
def update_task_status(
    class_id: str,
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    task = db.query(Task).filter(Task.id == task_id, Task.class_id == class_id).first()
    if not task:
        raise NotFoundException("Task not found")
    task.is_published = not task.is_published
    db.commit()
    return ok(data={"id": task.id, "is_published": task.is_published})


@router.get("/{class_id}/discussions", response_model=None)
def list_discussions(
    class_id: str,
    parent_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not course_service.check_class_member(db, class_id, current_user.id) and current_user.role != "admin":
        raise ForbiddenException("You are not a member of this class")
    return ok(data=course_service.list_discussions(db, class_id, parent_id))


@router.post("/{class_id}/discussions", response_model=None)
def create_discussion(
    class_id: str,
    body: CreateDiscussionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not course_service.check_class_member(db, class_id, current_user.id) and current_user.role != "admin":
        raise ForbiddenException("You are not a member of this class")
    discussion = Discussion(
        class_id=class_id,
        author_id=current_user.id,
        title=body.title,
        content=body.content,
        parent_id=body.parent_id,
    )
    db.add(discussion)
    db.commit()
    db.refresh(discussion)
    return ok(data={"id": discussion.id})


@router.post("/{class_id}/discussions/{discussion_id}/like", response_model=None)
def like_discussion(
    class_id: str,
    discussion_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    discussion = db.query(Discussion).filter(
        Discussion.id == discussion_id,
        Discussion.class_id == class_id,
    ).first()
    if not discussion:
        raise NotFoundException("Discussion not found")
    discussion.likes += 1
    db.commit()
    return ok(data={"likes": discussion.likes})


@router.post("/{class_id}/discussions/{discussion_id}/pin", response_model=None)
def pin_discussion(
    class_id: str,
    discussion_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    discussion = db.query(Discussion).filter(
        Discussion.id == discussion_id,
        Discussion.class_id == class_id,
    ).first()
    if not discussion:
        raise NotFoundException("Discussion not found")
    discussion.is_pinned = not discussion.is_pinned
    db.commit()
    return ok(data={"is_pinned": discussion.is_pinned})


@router.get("/{class_id}/members", response_model=None)
def list_members(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not course_service.check_class_member(db, class_id, current_user.id) and current_user.role != "admin":
        raise ForbiddenException("You are not a member of this class")
    members = db.query(ClassMember).filter(
        ClassMember.class_id == class_id,
        ClassMember.role == "student",
    ).all()
    result = []
    for membership in members:
        user = db.query(User).filter(User.id == membership.user_id).first()
        if user:
            result.append({
                "user_id": user.id,
                "real_name": user.real_name,
                "email": user.email,
                "student_id": user.student_id,
                "major": user.major,
                "grade": user.grade,
                "joined_at": membership.joined_at,
            })
    return ok(data=result)
