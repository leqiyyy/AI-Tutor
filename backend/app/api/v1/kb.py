import os
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

import app.storage as storage
from app.core.deps import get_current_teacher, get_current_user
from app.core.error_codes import ErrorCode
from app.core.openapi_examples import responses_with_success
from app.core.response import ok
from app.db.base import get_db
from app.integrations.rag import get_rag_engine
from app.integrations.preprocessors import detect_material_file_type
from app.models.course import Class, Material
from app.models.knowledge import FileParseTask
from app.models.user import User
from app.services import kb_service

router = APIRouter(tags=["kb"])


@router.post(
    "/courses/{course_id}/files/upload",
    response_model=None,
    responses=responses_with_success(
        example_data={
            "id": "a5d4bbde-47cb-4f78-b17a-65d58f9699f2",
            "course_id": "f3ed6f3f-f8ea-46de-ab2a-05a5f7f674d2",
            "class_id": "a88ec0c2-7f20-4f41-a905-822e3de17a95",
            "file_name": "week3-network.pdf",
            "kb_status": "indexed",
            "kb_error": None,
            "parse_task_id": "22dd2ae5-5f7e-4fd8-a2dd-f90c96d1de54",
            "storage_key": "a88ec0c2-7f20-4f41-a905-822e3de17a95/week3-network.pdf",
        },
        message="File uploaded and indexed",
        include_errors=(
            ErrorCode.BAD_REQUEST.value,
            ErrorCode.UNAUTHORIZED.value,
            ErrorCode.FORBIDDEN.value,
            ErrorCode.VALIDATION_ERROR.value,
            ErrorCode.INTERNAL_ERROR.value,
        ),
    ),
)
async def upload_course_file(
    course_id: str,
    class_id: Optional[str] = Form(None),
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    async_index: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = kb_service.resolve_class_for_course(db, course_id, current_user, class_id)

    suffix = os.path.splitext(file.filename or "")[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    file_hash = kb_service.compute_file_hash(content)

    duplicate = kb_service.find_duplicate_material(
        db,
        class_id=cls.id,
        file_hash=file_hash,
    )
    if duplicate:
        existing_material, existing_task = duplicate
        if existing_task.status in {"pending", "processing", "completed"}:
            os.unlink(tmp_path)
            message = "Duplicate file detected; existing indexing task reused"
            if existing_task.status == "completed":
                message = "Duplicate file detected; existing indexed material reused"
            return ok(
                data={
                    "id": existing_material.id,
                    "course_id": course_id,
                    "class_id": cls.id,
                    "file_name": existing_material.file_name,
                    "kb_status": existing_material.kb_status,
                    "kb_error": existing_material.kb_error,
                    "parse_task_id": existing_task.id,
                    "storage_key": None,
                    "deduplicated": True,
                    "action": "reuse_existing",
                    "queue_task_id": (existing_task.extra_data or {}).get("ingest", {}).get("queue_task_id"),
                },
                message=message,
            )

    storage_key, stored_path = storage.save_upload(cls.id, file.filename or "file", tmp_path)
    os.unlink(tmp_path)

    detected_file_type = detect_material_file_type(
        file.filename or "file",
        file.content_type or "application/octet-stream",
    )
    material = Material(
        class_id=cls.id,
        uploaded_by=current_user.id,
        title=title or file.filename or "Untitled",
        file_name=file.filename or "file",
        file_path=stored_path,
        file_size=len(content),
        mime_type=file.content_type or "application/octet-stream",
        file_type=detected_file_type,
        description=description,
        kb_status="pending",
    )
    db.add(material)
    db.commit()
    db.refresh(material)

    queue_task_id = None
    material_id = material.id
    if async_index:
        parse_task = kb_service.prepare_parse_task_for_enqueue(
            db,
            cls=cls,
            material=material,
            file_hash=file_hash,
            force=False,
        )
        queue_info = kb_service.enqueue_parse_task(
            db,
            parse_task=parse_task,
            force=False,
        )
        queue_task_id = queue_info.get("queue_task_id")
        action = "queued"
        message = "File uploaded and indexing task queued"
    else:
        parse_task, action = await kb_service.ingest_material_with_retry(
            db,
            cls=cls,
            material=material,
            file_hash=file_hash,
            force=False,
        )
        db.expire_all()
        material = db.query(Material).filter(Material.id == material_id).first()
        if parse_task is None:
            parse_task = db.query(FileParseTask).filter_by(material_id=material.id).first()

        message = "File uploaded and indexed" if material and material.kb_status == "indexed" else "File uploaded but indexing was only partially successful"
        if action == "already_processing":
            message = "File uploaded; indexing is still processing"
        if action == "failed":
            message = "File uploaded but indexing failed after retries"

    db.expire_all()
    material = db.query(Material).filter(Material.id == material_id).first()
    if not parse_task:
        parse_task = db.query(FileParseTask).filter_by(material_id=material.id).first()

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
            "deduplicated": False,
            "action": action,
            "queue_task_id": queue_task_id or ((parse_task.extra_data or {}).get("ingest", {}).get("queue_task_id") if parse_task else None),
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


@router.get("/courses/{course_id}/files/{file_id}/transcript", response_model=None)
def file_transcript(
    course_id: str,
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ok(data=kb_service.get_material_transcript(db, course_id, file_id, current_user))


@router.get("/courses/{course_id}/files/{file_id}/keyframes", response_model=None)
def file_keyframes(
    course_id: str,
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ok(data=kb_service.get_material_keyframes(db, course_id, file_id, current_user))


@router.get("/courses/{course_id}/files/{file_id}/ocr", response_model=None)
def file_ocr(
    course_id: str,
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ok(data=kb_service.get_material_ocr(db, course_id, file_id, current_user))


@router.get(
    "/courses/{course_id}/kb/status",
    response_model=None,
    responses=responses_with_success(
        example_data={
            "course_id": "f3ed6f3f-f8ea-46de-ab2a-05a5f7f674d2",
            "status": "healthy",
            "materials_total": 13,
            "materials_indexed": 11,
            "materials_failed": 2,
            "last_rebuild_at": "2026-04-17T01:30:00Z",
        },
        include_errors=(
            ErrorCode.UNAUTHORIZED.value,
            ErrorCode.FORBIDDEN.value,
            ErrorCode.NOT_FOUND.value,
            ErrorCode.INTERNAL_ERROR.value,
        ),
    ),
)
def kb_status(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kb_service.ensure_course_access(db, course_id, current_user)
    return ok(data=get_rag_engine().get_kb_status(course_id))


@router.get("/courses/{course_id}/kb/tasks", response_model=None)
def kb_tasks(
    course_id: str,
    class_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = kb_service.list_course_parse_tasks(
        db,
        course_id=course_id,
        user=current_user,
        class_id=class_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return ok(data=data)


@router.post("/courses/{course_id}/kb/rebuild", response_model=None)
async def rebuild_kb(
    course_id: str,
    storage_migration_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    kb_service.ensure_course_access(db, course_id, current_user)
    result = await get_rag_engine().rebuild_course(
        course_id,
        storage_migration_only=storage_migration_only,
    )
    return ok(data=result, message="Knowledge base rebuilt")


@router.post("/courses/{course_id}/files/{file_id}/kb/retry", response_model=None)
async def retry_file_index(
    course_id: str,
    file_id: str,
    force: bool = Query(True),
    async_retry: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    material = kb_service.get_material_for_user(db, course_id, file_id, current_user)
    cls = db.query(Class).filter_by(id=material.class_id).first()
    queue_task_id = None
    if async_retry:
        parse_task = kb_service.prepare_parse_task_for_enqueue(
            db,
            cls=cls,
            material=material,
            file_hash=None,
            force=force,
        )
        queue_info = kb_service.enqueue_parse_task(
            db,
            parse_task=parse_task,
            force=force,
        )
        queue_task_id = queue_info.get("queue_task_id")
        action = "queued_reindex"
    else:
        parse_task, action = await kb_service.ingest_material_with_retry(
            db,
            cls=cls,
            material=material,
            file_hash=None,
            force=force,
        )
    task_payload = get_rag_engine().get_parse_task(parse_task.id) if parse_task else None
    return ok(data={
        "file_id": material.id,
        "action": action,
        "queue_task_id": queue_task_id,
        "task": task_payload,
    }, message="File reindex request processed")


@router.get("/courses/{course_id}/graph", response_model=None)
def course_graph(
    course_id: str,
    class_id: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(1000, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kb_service.ensure_course_access(db, course_id, current_user)
    return ok(data=get_rag_engine().get_graph(
        course_id,
        class_id=class_id,
        entity_type=entity_type,
        min_confidence=min_confidence,
        limit=limit,
    ))


@router.get("/courses/{course_id}/search", response_model=None)
def search_course(
    course_id: str,
    q: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ok(data=kb_service.search_course_content(db, course_id, q, current_user))
