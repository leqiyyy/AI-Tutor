from typing import Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, field_validator


class SendVerifyCodeRequest(BaseModel):
    email: EmailStr
    purpose: Literal["register", "reset_password"] = "register"


class StudentRegisterRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    role: Literal["student"] = "student"
    real_name: str = Field(validation_alias=AliasChoices("real_name", "realName"))
    student_id: str = Field(validation_alias=AliasChoices("student_id", "studentId"))
    email: EmailStr
    phone: Optional[str] = None
    school: Optional[str] = None
    college: Optional[str] = None
    major: Optional[str] = None
    grade: Optional[str] = None
    class_no: Optional[str] = Field(default=None, validation_alias=AliasChoices("class_no", "classNo"))
    password: str
    confirm_password: str = Field(validation_alias=AliasChoices("confirm_password", "confirmPassword"))
    verify_code: str = Field(validation_alias=AliasChoices("verify_code", "verifyCode"))

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, value, info):
        if "password" in info.data and value != info.data["password"]:
            raise ValueError("Passwords do not match")
        return value


class TeacherRegisterRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    role: Literal["teacher"] = "teacher"
    real_name: str = Field(validation_alias=AliasChoices("real_name", "realName"))
    teacher_id: str = Field(validation_alias=AliasChoices("teacher_id", "teacherId"))
    email: EmailStr
    phone: Optional[str] = None
    school: Optional[str] = None
    college: Optional[str] = None
    department: Optional[str] = None
    title: Optional[str] = None
    id_card_no: Optional[str] = Field(default=None, validation_alias=AliasChoices("id_card_no", "idCardNo"))
    cert_file: Optional[str] = Field(default=None, validation_alias=AliasChoices("cert_file", "certFile"))
    password: str
    confirm_password: str = Field(validation_alias=AliasChoices("confirm_password", "confirmPassword"))
    verify_code: str = Field(validation_alias=AliasChoices("verify_code", "verifyCode"))

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, value, info):
        if "password" in info.data and value != info.data["password"]:
            raise ValueError("Passwords do not match")
        return value


class LoginRequest(BaseModel):
    account: str = Field(validation_alias=AliasChoices("account", "email"))
    password: str
    role: Optional[Literal["student", "teacher", "admin"]] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: str
    real_name: str
