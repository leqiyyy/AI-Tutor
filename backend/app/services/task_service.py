from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.course import Class, ClassMember, Submission, Task
from app.models.user import User
from app.services import analytics_service


def list_tasks_for_user(db: Session, user: User, class_id: Optional[str] = None) -> List[dict]:
    query = db.query(Task)
    if class_id:
        query = query.filter(Task.class_id == class_id)
    elif user.role == "teacher":
        class_ids = [
            row.id
            for row in db.query(Class).filter(Class.teacher_id == user.id, Class.is_active == True).all()
        ]
        query = query.filter(Task.class_id.in_(class_ids))
    elif user.role == "student":
        class_ids = [
            row.class_id
            for row in db.query(ClassMember).filter(
                ClassMember.user_id == user.id,
                ClassMember.role == "student",
            ).all()
        ]
        query = query.filter(Task.class_id.in_(class_ids), Task.is_published == True)

    items = query.order_by(Task.created_at.desc()).all()
    result = []
    for task in items:
        submission_count = db.query(Submission).filter(Submission.task_id == task.id).count()
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
            "submission_count": submission_count,
        })
    return result


def get_task_for_user(db: Session, task_id: str, user: User) -> Task:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise NotFoundException("Task not found")

    if user.role == "teacher":
        owned = db.query(Class).filter(Class.id == task.class_id, Class.teacher_id == user.id).first()
        if not owned and user.role != "admin":
            raise ForbiddenException("You do not have access to this task")
    elif user.role == "student":
        member = db.query(ClassMember).filter(
            ClassMember.class_id == task.class_id,
            ClassMember.user_id == user.id,
        ).first()
        if not member:
            raise ForbiddenException("You do not have access to this task")
    return task


def submit_task(
    db: Session,
    task_id: str,
    student: User,
    content: Optional[str] = None,
    file_path: Optional[str] = None,
) -> Submission:
    task = get_task_for_user(db, task_id, student)
    existing = db.query(Submission).filter(
        Submission.task_id == task_id,
        Submission.student_id == student.id,
    ).first()
    if existing:
        existing.content = content
        existing.file_path = file_path
        analytics_service.record_learning(
            db,
            user_id=student.id,
            class_id=task.class_id,
            activity_type="submit_task",
            ref_id=existing.id,
            extra_data={"task_id": task.id, "resubmission": True},
        )
        db.commit()
        db.refresh(existing)
        return existing

    submission = Submission(
        task_id=task.id,
        student_id=student.id,
        content=content,
        file_path=file_path,
        status="submitted",
    )
    db.add(submission)
    db.flush()
    analytics_service.record_learning(
        db,
        user_id=student.id,
        class_id=task.class_id,
        activity_type="submit_task",
        ref_id=submission.id,
        extra_data={"task_id": task.id, "resubmission": False},
    )
    db.commit()
    db.refresh(submission)
    return submission


def list_task_submissions(db: Session, task_id: str, user: User) -> List[dict]:
    task = get_task_for_user(db, task_id, user)
    submissions = db.query(Submission).filter(Submission.task_id == task.id).all()

    if user.role == "student":
        submissions = [submission for submission in submissions if submission.student_id == user.id]

    result = []
    for submission in submissions:
        student = db.query(User).filter(User.id == submission.student_id).first()
        result.append({
            "id": submission.id,
            "task_id": submission.task_id,
            "student_id": submission.student_id,
            "student_name": student.real_name if student else "",
            "content": submission.content,
            "file_path": submission.file_path,
            "score": submission.score,
            "feedback": submission.feedback,
            "status": submission.status,
            "submitted_at": submission.submitted_at,
            "graded_at": submission.graded_at,
        })
    return result
