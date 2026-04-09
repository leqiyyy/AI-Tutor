from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserProfile(BaseModel):
    id: str
    email: str
    real_name: str
    role: str
    is_active: bool
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    school: Optional[str] = None
    bio: Optional[str] = None
    # Student
    student_id: Optional[str] = None
    college: Optional[str] = None
    major: Optional[str] = None
    grade: Optional[str] = None
    class_no: Optional[str] = None
    # Teacher
    teacher_id: Optional[str] = None
    department: Optional[str] = None
    title: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    real_name: Optional[str] = None
    phone: Optional[str] = None
    school: Optional[str] = None
    bio: Optional[str] = None
    college: Optional[str] = None
    major: Optional[str] = None
    grade: Optional[str] = None
    class_no: Optional[str] = None
    department: Optional[str] = None
    title: Optional[str] = None
