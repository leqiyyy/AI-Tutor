from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Any, Optional
from datetime import datetime, timezone
from app.db.base import get_db
from app.core.deps import get_current_admin
from app.models.user import User
from app.models.course import Class, Course
from app.models.chat import ReviewItem
from app.models.admin import AdminSetting
from app.core.response import ok
from app.core.config import settings
from app.core.error_codes import ErrorCode
from app.core.openapi_examples import responses_with_success
from app.services import analytics_service, admin_service, audit_service, kb_service, model_routing_service, rag_metrics_service

router = APIRouter(prefix="/admin", tags=["admin"])


class ModelConfigUpdateRequest(BaseModel):
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_backend: Optional[str] = None
    llm_local_api_base: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_backend: Optional[str] = None
    embedding_local_api_base: Optional[str] = None
    vlm_model: Optional[str] = None
    vlm_backend: Optional[str] = None
    vlm_local_api_base: Optional[str] = None
    reranker_provider: Optional[str] = None
    reranker_model: Optional[str] = None
    reranker_local_model: Optional[str] = None
    rag_engine: Optional[str] = None
    storage_backend: Optional[str] = None
    email_dev_mode: Optional[bool] = None


class RAGStorageConfigUpdateRequest(BaseModel):
    rag_storage_backend: Optional[str] = None
    vector_db_provider: Optional[str] = None
    vector_db_url: Optional[str] = None
    vector_db_collection: Optional[str] = None
    graph_db_provider: Optional[str] = None
    graph_db_url: Optional[str] = None
    graph_db_database: Optional[str] = None
    graph_db_username: Optional[str] = None


class RegistrationReviewRequest(BaseModel):
    userId: str
    decision: str
    reason: Optional[str] = None


class UserStatusUpdateRequest(BaseModel):
    status: Optional[str] = None
    reason: Optional[str] = None


class CourseStatusUpdateRequest(BaseModel):
    status: str
    reason: Optional[str] = None


class ContentReviewRequest(BaseModel):
    itemId: str
    decision: str
    reason: Optional[str] = None


class SystemSettingsUpdateRequest(BaseModel):
    maintenanceMode: Optional[bool] = None
    examWeekLimit: Optional[bool] = None
    backupSchedule: Optional[str] = None
    announcement: Optional[dict[str, Any]] = None


def _upsert_admin_setting(
    db: Session,
    *,
    section: str,
    key: str,
    value: Any,
    description: str,
) -> None:
    setting = db.query(AdminSetting).filter(
        AdminSetting.section == section,
        AdminSetting.key == key,
    ).first()
    if not setting:
        setting = AdminSetting(
            section=section,
            key=key,
            value=value,
            description=description,
        )
        db.add(setting)
    else:
        setting.value = value


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
    body: UserStatusUpdateRequest | None = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("用户不存在")
    if body and body.status:
        user.is_active = body.status == "enabled"
    else:
        user.is_active = not user.is_active
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    audit_service.record_event(
        event_type="admin.user_status_updated",
        actor=current_admin,
        target_type="user",
        target_id=user.id,
        summary=f"User status set to {'enabled' if user.is_active else 'disabled'}",
        extra_data={"reason": body.reason if body else None, "status": body.status if body else None},
    )
    return ok(data={"user_id": user_id, "is_active": user.is_active})


@router.post("/registrations/review", response_model=None)
def review_registration(
    body: RegistrationReviewRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == body.userId).first()
    if not user:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("用户不存在")
    decision = body.decision.strip().lower()
    user.is_active = decision == "approve"
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    audit_service.record_event(
        event_type="admin.registration_reviewed",
        actor=current_admin,
        target_type="user",
        target_id=user.id,
        summary=f"Registration {decision}",
        extra_data={"decision": decision, "reason": body.reason},
    )
    return ok(data={
        "user_id": user.id,
        "decision": decision,
        "is_active": user.is_active,
    }, message="Registration reviewed")


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


@router.patch("/courses/{course_id}/status", response_model=None)
def update_course_status(
    course_id: str,
    body: CourseStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("课程不存在")
    normalized = body.status.strip().lower()
    course.is_active = normalized == "active"
    course.updated_at = datetime.now(timezone.utc)
    db.commit()
    audit_service.record_event(
        event_type="admin.course_status_updated",
        actor=current_admin,
        target_type="course",
        target_id=course.id,
        course_id=course.id,
        summary=f"Course status set to {normalized}",
        extra_data={"status": normalized, "reason": body.reason},
    )
    return ok(data={
        "course_id": course.id,
        "status": normalized,
        "is_active": course.is_active,
    }, message="Course status updated")


@router.get("/audit-events", response_model=None)
def list_audit_events(
    event_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    actor_role: Optional[str] = Query(None),
    class_id: Optional[str] = Query(None),
    course_id: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    return ok(data=audit_service.list_events(
        db,
        event_type=event_type,
        status=status,
        actor_role=actor_role,
        class_id=class_id,
        course_id=course_id,
        target_type=target_type,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    ))


@router.post("/content/review", response_model=None)
def review_content(
    body: ContentReviewRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    review = db.query(ReviewItem).filter(ReviewItem.id == body.itemId).first()
    if not review:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("审核内容不存在")
    decision = body.decision.strip().lower()
    if decision in {"approve", "markincorrect"}:
        review.status = "resolved"
    elif decision in {"reject", "delete"}:
        review.status = "dismissed"
    review.reviewed_by = current_admin.id
    review.reviewed_at = datetime.now(timezone.utc)
    if body.reason:
        review.teacher_answer = body.reason
    db.commit()
    audit_service.record_event(
        event_type="admin.content_reviewed",
        actor=current_admin,
        target_type="review_item",
        target_id=review.id,
        class_id=review.class_id,
        summary=f"Content review decision: {decision}",
        extra_data={"decision": decision, "reason": body.reason},
    )
    return ok(data={
        "item_id": review.id,
        "decision": decision,
        "status": review.status,
    }, message="Content reviewed")


@router.patch("/system-settings", response_model=None)
def update_system_settings(
    body: SystemSettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    payload = body.model_dump(exclude_unset=True)
    for key, value in payload.items():
        _upsert_admin_setting(
            db,
            section="system_settings",
            key=key,
            value=value,
            description=f"System setting for {key}",
        )
    db.commit()
    audit_service.record_event(
        event_type="admin.system_settings_updated",
        actor=current_admin,
        target_type="system_settings",
        summary="System settings updated",
        extra_data={"keys": sorted(payload.keys())},
    )
    return ok(data={
        "settings": payload,
        "applied_runtime": False,
        "restart_required": any(key in payload for key in {"maintenanceMode", "backupSchedule"}),
    }, message="System settings saved")


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


@router.get("/model-routing", response_model=None)
def get_model_routing(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    model_config = admin_service.get_model_config(db)
    data = model_routing_service.build_model_routing_snapshot(model_config)
    return ok(data=data)


@router.get("/rag-storage-config", response_model=None)
def get_rag_storage_config(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    return ok(data=admin_service.get_rag_storage_config(db))


@router.put("/rag-storage-config", response_model=None)
def update_rag_storage_config(
    body: RAGStorageConfigUpdateRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    effective = admin_service.update_rag_storage_config(db, body.model_dump())
    return ok(data=effective, message="RAG storage config saved")


@router.get("/rag-system-status", response_model=None)
def rag_system_status(
    days: int = Query(7, ge=1, le=90),
    class_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    data = admin_service.get_rag_system_status(
        db,
        days=days,
        class_id=class_id,
    )
    return ok(data=data)


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


@router.get("/index-tasks", response_model=None)
def list_index_tasks(
    course_id: Optional[str] = Query(None),
    class_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    data = kb_service.list_parse_tasks_admin(
        db,
        course_id=course_id,
        class_id=class_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return ok(data=data)


@router.get("/index-queue/{queue_task_id}", response_model=None)
def get_index_queue_status(
    queue_task_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    data = kb_service.get_queue_task_status(db, queue_task_id)
    return ok(data=data)


@router.post("/index-tasks/retry-failed", response_model=None)
def retry_failed_index_tasks(
    course_id: Optional[str] = Query(None),
    class_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=500),
    force: bool = Query(False),
    ignore_cooldown: bool = Query(False),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    data = kb_service.retry_failed_tasks_admin(
        db,
        course_id=course_id,
        class_id=class_id,
        limit=limit,
        force=force,
        ignore_cooldown=ignore_cooldown,
    )
    return ok(data=data, message="Batch retry submitted")


@router.get("/index-queue-metrics", response_model=None)
def index_queue_metrics(
    course_id: Optional[str] = Query(None),
    class_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    data = kb_service.get_index_queue_metrics(
        db,
        course_id=course_id,
        class_id=class_id,
    )
    return ok(data=data)


@router.get(
    "/rag-performance",
    response_model=None,
    responses=responses_with_success(
        example_data={
            "window_days": 7,
            "window_start": "2026-04-10T02:00:00Z",
            "window_end": "2026-04-17T02:00:00Z",
            "filters": {"class_id": None},
            "totals": {
                "queries": 143,
                "success": 143,
                "fallback": 27,
                "main_chain_success": 116,
            },
            "rates": {
                "success_rate": 1.0,
                "fallback_rate": 0.1888,
                "main_chain_success_rate": 0.8112,
            },
            "latency_ms": {"avg": 612.4, "p50": 540.0, "p95": 1210.0, "max": 1689.0},
            "quality": {"avg_confidence": 0.79, "avg_source_count": 2.1},
            "distributions": {
                "query_mode": {"mix": 121, "hybrid": 22},
                "engine": {"raganything": 143},
                "fallback_reason": {"query_exception": 14, "empty_answer": 13},
            },
        },
        include_errors=(
            ErrorCode.UNAUTHORIZED.value,
            ErrorCode.FORBIDDEN.value,
            ErrorCode.INTERNAL_ERROR.value,
        ),
    ),
)
def rag_performance(
    days: int = Query(7, ge=1, le=90),
    class_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    data = rag_metrics_service.get_rag_performance(
        db,
        days=days,
        class_id=class_id,
    )
    return ok(data=data)


@router.get(
    "/rag-ablation",
    response_model=None,
    responses=responses_with_success(
        example_data={
            "window_days": 7,
            "window_start": "2026-04-10T02:00:00Z",
            "window_end": "2026-04-17T02:00:00Z",
            "filters": {"class_id": None},
            "totals": {"queries": 143},
            "groups": {
                "rewrite_enabled": {
                    "enabled": {"queries": 84, "success_rate": 1.0, "fallback_rate": 0.12},
                    "disabled": {"queries": 59, "success_rate": 1.0, "fallback_rate": 0.29},
                },
                "rewrite_mode": {
                    "hybrid": {"queries": 52, "success_rate": 1.0, "fallback_rate": 0.13},
                    "keywords": {"queries": 32, "success_rate": 1.0, "fallback_rate": 0.11},
                    "disabled": {"queries": 59, "success_rate": 1.0, "fallback_rate": 0.29},
                },
                "query_variant_bucket": {
                    "1": {"queries": 59, "success_rate": 1.0, "fallback_rate": 0.29},
                    "2": {"queries": 37, "success_rate": 1.0, "fallback_rate": 0.16},
                    "3": {"queries": 47, "success_rate": 1.0, "fallback_rate": 0.1},
                },
            },
        },
        include_errors=(
            ErrorCode.UNAUTHORIZED.value,
            ErrorCode.FORBIDDEN.value,
            ErrorCode.INTERNAL_ERROR.value,
        ),
    ),
)
def rag_ablation(
    days: int = Query(7, ge=1, le=90),
    class_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    data = rag_metrics_service.get_rag_rewrite_ablation(
        db,
        days=days,
        class_id=class_id,
    )
    return ok(data=data)


@router.get(
    "/personalization-routing-metrics",
    response_model=None,
    responses=responses_with_success(
        example_data={
            "window_days": 30,
            "window_start": "2026-03-18T02:00:00Z",
            "window_end": "2026-04-17T02:00:00Z",
            "filters": {"class_id": None, "top_n": 12},
            "summary": {
                "total_queries": 214,
                "total_slices": 4,
                "total_users": 37,
                "best_confidence_slice": "api|api|api|local",
                "lowest_fallback_slice": "api|api|api|local",
            },
            "slices": [
                {
                    "routing_slice_key": "api|api|api|local",
                    "llm_backend": "api",
                    "embedding_backend": "api",
                    "vlm_backend": "api",
                    "reranker_backend": "local",
                    "queries": 128,
                    "users": 29,
                    "success_rate": 1.0,
                    "fallback_rate": 0.1719,
                    "avg_confidence": 0.8123,
                    "avg_source_count": 2.42,
                    "avg_latency_ms": 604.2,
                    "avg_activity_score": 0.74,
                    "avg_task_completion_rate": 0.67,
                    "avg_dislike_count": 1.14,
                    "learning_events_per_user": 8.5517,
                }
            ],
        },
        include_errors=(
            ErrorCode.UNAUTHORIZED.value,
            ErrorCode.FORBIDDEN.value,
            ErrorCode.INTERNAL_ERROR.value,
        ),
    ),
)
def personalization_routing_metrics(
    days: int = Query(30, ge=1, le=180),
    class_id: Optional[str] = Query(None),
    top_n: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    data = analytics_service.get_personalization_routing_metrics(
        db,
        days=days,
        class_id=class_id,
        top_n=top_n,
    )
    return ok(data=data)


@router.get(
    "/experiment-results",
    response_model=None,
    responses=responses_with_success(
        example_data={
            "report_window_days": 7,
            "generated_at": "2026-04-17T02:40:00Z",
            "summary": {
                "query_total": 143,
                "main_chain_success_rate": 0.8112,
                "fallback_rate": 0.1888,
                "avg_confidence": 0.79,
                "p95_latency_ms": 1210.0,
            },
            "model_snapshot": {
                "llm_provider": "mock",
                "llm_model": "claude-opus-4-6",
                "rag_engine": "raganything",
            },
            "rag_performance": {
                "totals": {"queries": 143, "success": 143, "fallback": 27, "main_chain_success": 116},
                "rates": {"success_rate": 1.0, "fallback_rate": 0.1888, "main_chain_success_rate": 0.8112},
            },
            "notes": [
                "Use this snapshot for weekly experiment comparison.",
                "Track fallback_reason distribution before model changes.",
            ],
        },
        include_errors=(
            ErrorCode.UNAUTHORIZED.value,
            ErrorCode.FORBIDDEN.value,
            ErrorCode.INTERNAL_ERROR.value,
        ),
    ),
)
def experiment_results(
    days: int = Query(7, ge=1, le=90),
    class_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    performance = rag_metrics_service.get_rag_performance(
        db,
        days=days,
        class_id=class_id,
    )
    model_snapshot = admin_service.get_model_config(db)
    model_routing = model_routing_service.build_model_routing_snapshot(model_snapshot)
    return ok(data={
        "report_window_days": days,
        "generated_at": datetime.now(timezone.utc),
        "summary": {
            "query_total": performance["totals"]["queries"],
            "main_chain_success_rate": performance["rates"]["main_chain_success_rate"],
            "fallback_rate": performance["rates"]["fallback_rate"],
            "avg_confidence": performance["quality"]["avg_confidence"],
            "p95_latency_ms": performance["latency_ms"]["p95"],
        },
        "model_snapshot": {
            "llm_provider": model_snapshot.get("llm_provider"),
            "llm_model": model_snapshot.get("llm_model"),
            "llm_backend": model_snapshot.get("llm_backend"),
            "embedding_model": model_snapshot.get("embedding_model"),
            "embedding_backend": model_snapshot.get("embedding_backend"),
            "vlm_model": model_snapshot.get("vlm_model"),
            "vlm_backend": model_snapshot.get("vlm_backend"),
            "reranker_provider": model_snapshot.get("reranker_provider"),
            "reranker_model": model_snapshot.get("reranker_model"),
            "rag_engine": model_snapshot.get("rag_engine"),
        },
        "model_routing": model_routing,
        "rag_performance": performance,
        "notes": [
            "Use this snapshot for weekly experiment comparison.",
            "Track fallback_reason distribution before model changes.",
        ],
    })
