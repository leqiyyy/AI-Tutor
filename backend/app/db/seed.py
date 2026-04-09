"""Seed data for local development and MVP validation."""

from sqlalchemy.orm import Session

from app.core.database import SessionLocal, initialize_database
from app.core.security import hash_password
from app.models.analytics import LearningRecord, QuestionAnalytics
from app.models.course import Class, ClassMember, Course, Submission, Task
from app.models.knowledge import Flashcard
from app.models.notification import Notification
from app.models.user import User
from app.services import analytics_service

DEFAULT_USERS = [
    {
        "email": "admin@aitutor.local",
        "real_name": "System Admin",
        "role": "admin",
        "password": "Admin123!",
    },
    {
        "email": "teacher@aitutor.local",
        "real_name": "Wang Teacher",
        "role": "teacher",
        "teacher_id": "T2024001",
        "school": "Demo University",
        "department": "Computer Science",
        "title": "Professor",
        "password": "Teacher123!",
    },
    {
        "email": "student@aitutor.local",
        "real_name": "Li Student",
        "role": "student",
        "student_id": "2024301001",
        "school": "Demo University",
        "college": "Computer Science",
        "major": "Computer Science",
        "grade": "2024",
        "class_no": "1",
        "password": "Student123!",
    },
]


def _get_or_create_user(db: Session, payload: dict) -> User:
    user = db.query(User).filter(User.email == payload["email"]).first()
    if user:
        return user

    user = User(
        email=payload["email"],
        hashed_password=hash_password(payload["password"]),
        real_name=payload["real_name"],
        role=payload["role"],
        teacher_id=payload.get("teacher_id"),
        student_id=payload.get("student_id"),
        school=payload.get("school"),
        college=payload.get("college"),
        major=payload.get("major"),
        grade=payload.get("grade"),
        class_no=payload.get("class_no"),
        department=payload.get("department"),
        title=payload.get("title"),
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def seed_data() -> dict:
    initialize_database()

    with SessionLocal() as db:
        users = {payload["role"]: _get_or_create_user(db, payload) for payload in DEFAULT_USERS}

        teacher = users["teacher"]
        student = users["student"]

        course = db.query(Course).filter(Course.code == "CS301").first()
        if not course:
            course = Course(
                name="Computer Networks",
                code="CS301",
                description="Seed course for local MVP validation",
                cover_color="#0f766e",
                created_by=teacher.id,
            )
            db.add(course)
            db.flush()

        cls = db.query(Class).filter(Class.course_id == course.id, Class.name == "CS301 Spring Demo").first()
        if not cls:
            cls = Class(
                course_id=course.id,
                teacher_id=teacher.id,
                name="CS301 Spring Demo",
                semester="2026 Spring",
                invite_code="CS301A1",
                announcement="Welcome to the demo class.",
            )
            db.add(cls)
            db.flush()

        if not db.query(ClassMember).filter(ClassMember.class_id == cls.id, ClassMember.user_id == teacher.id).first():
            db.add(ClassMember(class_id=cls.id, user_id=teacher.id, role="teacher"))
        if not db.query(ClassMember).filter(ClassMember.class_id == cls.id, ClassMember.user_id == student.id).first():
            db.add(ClassMember(class_id=cls.id, user_id=student.id, role="student"))

        if not db.query(Task).filter(Task.class_id == cls.id, Task.title == "Week 1 Homework").first():
            db.add(Task(
                class_id=cls.id,
                created_by=teacher.id,
                title="Week 1 Homework",
                description="Seed homework for Phase 2 validation",
                task_type="homework",
                max_score=100,
                is_published=True,
            ))

        db.flush()
        task = db.query(Task).filter(Task.class_id == cls.id, Task.title == "Week 1 Homework").first()

        if task and not db.query(Submission).filter(Submission.task_id == task.id, Submission.student_id == student.id).first():
            db.add(Submission(
                task_id=task.id,
                student_id=student.id,
                content="Seed submission",
                score=92,
                feedback="Good work",
                status="graded",
            ))

        if not db.query(Notification).filter(Notification.user_id == student.id, Notification.title == "Welcome to AI Tutor").first():
            db.add(Notification(
                user_id=student.id,
                type="system",
                title="Welcome to AI Tutor",
                content="Your demo account is ready to use.",
                extra_data={"seed": True},
            ))

        if not db.query(Flashcard).filter(Flashcard.user_id == student.id, Flashcard.question == "What is TCP slow start?").first():
            db.add(Flashcard(
                class_id=cls.id,
                user_id=student.id,
                question="What is TCP slow start?",
                answer="It is the initial congestion control phase where the congestion window grows quickly to probe available capacity.",
                tags=["tcp", "congestion-control", "transport"],
                interval_days=1,
            ))
        if not db.query(Flashcard).filter(Flashcard.user_id == student.id, Flashcard.question == "What does CIDR /24 mean?").first():
            db.add(Flashcard(
                class_id=cls.id,
                user_id=student.id,
                question="What does CIDR /24 mean?",
                answer="It means the subnet mask has 24 leading 1 bits, equivalent to 255.255.255.0.",
                tags=["cidr", "subnet", "network"],
                interval_days=2,
            ))

        if not db.query(LearningRecord).filter(LearningRecord.user_id == student.id, LearningRecord.activity_type == "seed_activity").first():
            db.add(LearningRecord(
                user_id=student.id,
                class_id=cls.id,
                activity_type="seed_activity",
                extra_data={"seed": True},
            ))

        if not db.query(QuestionAnalytics).filter(QuestionAnalytics.class_id == cls.id, QuestionAnalytics.topic == "tcp").first():
            db.add(QuestionAnalytics(class_id=cls.id, topic="tcp", question_count=3))
        if not db.query(QuestionAnalytics).filter(QuestionAnalytics.class_id == cls.id, QuestionAnalytics.topic == "subnet").first():
            db.add(QuestionAnalytics(class_id=cls.id, topic="subnet", question_count=2))

        db.commit()
        analytics_service.build_student_profile(db, student)

        return {
            "admin": {"email": "admin@aitutor.local", "password": "Admin123!"},
            "teacher": {"email": "teacher@aitutor.local", "password": "Teacher123!", "teacher_id": "T2024001"},
            "student": {"email": "student@aitutor.local", "password": "Student123!", "student_id": "2024301001"},
            "course_code": "CS301",
            "invite_code": "CS301A1",
        }


if __name__ == "__main__":
    result = seed_data()
    for role, creds in result.items():
        print(role, creds)
