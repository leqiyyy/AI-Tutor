from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_student, get_current_teacher, get_current_user
from app.core.response import ok
from app.db.base import get_db
from app.models.course import Class, Task
from app.models.user import User
from app.schemas.course import CreateTaskGlobalRequest
from app.services import kb_service, task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskSubmissionRequest(BaseModel):
    content: Optional[str] = None
    file_path: Optional[str] = None


@router.get("", response_model=None)
def list_tasks(
    class_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ok(data=task_service.list_tasks_for_user(db, current_user, class_id))


@router.get("/{task_id}", response_model=None)
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    parse_task = kb_service.get_parse_task_for_user(db, task_id, current_user)
    if parse_task:
        return ok(data=parse_task)
    task = task_service.get_task_for_user(db, task_id, current_user)
    return ok(data={
        "id": task.id,
        "class_id": task.class_id,
        "title": task.title,
        "description": task.description,
        "task_type": task.task_type,
        "due_date": task.due_date,
        "max_score": task.max_score,
        "is_published": task.is_published,
        "created_at": task.created_at,
    })


@router.post("", response_model=None)
def create_task_global(
    body: CreateTaskGlobalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = db.query(Class).filter(Class.id == body.class_id, Class.teacher_id == current_user.id).first()
    if not cls:
        from app.core.exceptions import ForbiddenException

        raise ForbiddenException("You do not have access to this class")
    task = Task(
        class_id=body.class_id,
        created_by=current_user.id,
        title=body.title,
        description=body.description,
        task_type=body.task_type,
        due_date=body.due_date,
        max_score=body.max_score,
        is_published=body.is_published,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return ok(data={"id": task.id, "class_id": task.class_id, "title": task.title}, message="Task created")


@router.post("/{task_id}/submit", response_model=None)
def submit_task(
    task_id: str,
    body: TaskSubmissionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    submission = task_service.submit_task(
        db,
        task_id=task_id,
        student=current_user,
        content=body.content,
        file_path=body.file_path,
    )
    return ok(data={"id": submission.id, "status": submission.status}, message="Task submitted")


@router.get("/{task_id}/submissions", response_model=None)
def list_submissions(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ok(data=task_service.list_task_submissions(db, task_id, current_user))
