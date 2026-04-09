import os
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

import app.storage as storage
from app.ai.mock_rag import get_rag_engine
from app.core.deps import get_current_teacher, get_current_user
from app.core.response import ok
from app.db.base import get_db
from app.models.course import Material
from app.models.user import User
from app.services import kb_service

router = APIRouter(tags=["kb"])


@router.post("/courses/{course_id}/files/upload", response_model=None)
async def upload_course_file(
    course_id: str,
    class_id: Optional[str] = Form(None),
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = kb_service.resolve_class_for_course(db, course_id, current_user, class_id)

    suffix = os.path.splitext(file.filename or "")[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    storage_key, stored_path = storage.save_upload(cls.id, file.filename or "file", tmp_path)
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
    material = Material(
        class_id=cls.id,
        uploaded_by=current_user.id,
        title=title or file.filename or "Untitled",
        file_name=file.filename or "file",
        file_path=stored_path,
        file_size=len(content),
        mime_type=file.content_type or "application/octet-stream",
        file_type=file_type_map.get(ext, "other"),
        description=description,
        kb_status="pending",
    )
    db.add(material)
    db.commit()
    db.refresh(material)

    rag = get_rag_engine()
    await rag.ingest_material(cls.id, material.id, stored_path, material.mime_type or "application/octet-stream")
    db.refresh(material)
    parse_task = db.query(__import__("app.models.knowledge", fromlist=["FileParseTask"]).FileParseTask).filter_by(material_id=material.id).first()

    message = "File uploaded and indexed" if material.kb_status == "indexed" else "File uploaded but indexing was only partially successful"
    return ok(
        data={
            "id": material.id,
            "course_id": course_id,
            "class_id": cls.id,
            "file_name": material.file_name,
            "kb_status": material.kb_status,
            "kb_error": material.kb_error,
            "parse_task_id": parse_task.id if parse_task else None,
            "storage_key": storage_key,
        },
        message=message,
    )


@router.get("/courses/{course_id}/files", response_model=None)
def list_course_files(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ok(data=kb_service.list_course_files(db, course_id, current_user))


@router.get("/courses/{course_id}/files/{file_id}/preview", response_model=None)
def file_preview(
    course_id: str,
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ok(data=kb_service.get_material_preview(db, course_id, file_id, current_user))


@router.get("/courses/{course_id}/files/{file_id}/download", response_class=FileResponse)
def file_download(
    course_id: str,
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    material = kb_service.get_material_for_user(db, course_id, file_id, current_user)
    return FileResponse(path=material.file_path, filename=material.file_name, media_type=material.mime_type)


@router.get("/courses/{course_id}/files/{file_id}/analysis", response_model=None)
def file_analysis(
    course_id: str,
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ok(data=kb_service.get_material_analysis(db, course_id, file_id, current_user))


@router.get("/courses/{course_id}/kb/status", response_model=None)
def kb_status(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kb_service.ensure_course_access(db, course_id, current_user)
    return ok(data=get_rag_engine().get_kb_status(course_id))


@router.post("/courses/{course_id}/kb/rebuild", response_model=None)
async def rebuild_kb(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    kb_service.ensure_course_access(db, course_id, current_user)
    result = await get_rag_engine().rebuild_course(course_id)
    return ok(data=result, message="Knowledge base rebuilt")


@router.get("/courses/{course_id}/graph", response_model=None)
def course_graph(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kb_service.ensure_course_access(db, course_id, current_user)
    return ok(data=get_rag_engine().get_graph(course_id))


@router.get("/courses/{course_id}/search", response_model=None)
def search_course(
    course_id: str,
    q: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ok(data=kb_service.search_course_content(db, course_id, q, current_user))
