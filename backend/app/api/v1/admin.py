from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from app.db.base import get_db
from app.core.deps import get_current_admin
from app.models.user import User
from app.models.course import Class, Course
from app.models.chat import ReviewItem
from app.core.response import ok
from app.core.config import settings
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


class ModelConfigUpdateRequest(BaseModel):
    llm_provider: Optional[str] = None
    rag_engine: Optional[str] = None
    storage_backend: Optional[str] = None
    email_dev_mode: Optional[bool] = None


@router.get("/overview", response_model=None)
def system_overview(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    total_users = db.query(User).count()
    total_students = db.query(User).filter(User.role == "student").count()
    total_teachers = db.query(User).filter(User.role == "teacher").count()
    total_classes = db.query(Class).filter(Class.is_active == True).count()
    pending_reviews = db.query(ReviewItem).filter(ReviewItem.status == "pending").count()
    return ok(data={
        "total_users": total_users,
        "total_students": total_students,
        "total_teachers": total_teachers,
        "total_classes": total_classes,
        "pending_reviews": pending_reviews,
    })


@router.get("/users", response_model=None)
def list_users(
    role: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    total = q.count()
    users = q.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    data = [{
        "id": u.id,
        "email": u.email,
        "real_name": u.real_name,
        "role": u.role,
        "is_active": u.is_active,
        "created_at": u.created_at,
    } for u in users]
    return ok(data={"items": data, "total": total, "page": page, "page_size": page_size})


@router.put("/users/{user_id}/status", response_model=None)
def toggle_user_status(
    user_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("用户不存在")
    user.is_active = not user.is_active
    db.commit()
    return ok(data={"user_id": user_id, "is_active": user.is_active})


@router.get("/classes", response_model=None)
def list_classes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    total = db.query(Class).count()
    classes = db.query(Class).order_by(Class.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    data = [{
        "id": c.id,
        "name": c.name,
        "teacher_id": c.teacher_id,
        "semester": c.semester,
        "is_active": c.is_active,
        "created_at": c.created_at,
    } for c in classes]
    return ok(data={"items": data, "total": total, "page": page, "page_size": page_size})


@router.get("/courses", response_model=None)
def list_courses_admin(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    total = db.query(Course).count()
    courses = db.query(Course).order_by(Course.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    data = [{
        "id": course.id,
        "name": course.name,
        "code": course.code,
        "description": course.description,
        "cover_color": course.cover_color,
        "created_by": course.created_by,
        "is_active": course.is_active,
        "created_at": course.created_at,
    } for course in courses]
    return ok(data={"items": data, "total": total, "page": page, "page_size": page_size})


@router.get("/settings", response_model=None)
def get_settings(_=Depends(get_current_admin)):
    return ok(data={
        "llm_provider": settings.LLM_PROVIDER,
        "rag_engine": settings.RAG_ENGINE,
        "storage_backend": settings.STORAGE_BACKEND,
        "email_dev_mode": settings.EMAIL_DEV_MODE,
        "cors_origins": settings.CORS_ORIGINS,
    })


@router.get("/model-config", response_model=None)
def get_model_config(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    return ok(data=admin_service.get_model_config(db))


@router.put("/model-config", response_model=None)
def update_model_config(
    body: ModelConfigUpdateRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    effective = admin_service.update_model_config(db, body.model_dump())
    return ok(data=effective, message="Model config saved")


@router.get("/reviews", response_model=None)
def list_all_reviews(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    q = db.query(ReviewItem)
    if status:
        q = q.filter(ReviewItem.status == status)
    total = q.count()
    items = q.order_by(ReviewItem.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    data = [{
        "id": i.id,
        "class_id": i.class_id,
        "trigger": i.trigger,
        "question_content": i.question_content,
        "ai_answer": i.ai_answer,
        "status": i.status,
        "created_at": i.created_at,
    } for i in items]
    return ok(data={"items": data, "total": total})
