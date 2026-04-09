from typing import Optional
from fastapi import Depends, Header
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.core.security import decode_token
from app.core.exceptions import AuthException, ForbiddenException
from app.models.user import User


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthException("缺少认证令牌")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload:
        raise AuthException("令牌无效或已过期")
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise AuthException("用户不存在")
    return user


def require_role(*roles: str):
    def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise ForbiddenException(f"需要角色: {', '.join(roles)}")
        return current_user
    return _checker


def get_current_teacher(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "teacher":
        raise ForbiddenException("仅教师可操作")
    return current_user


def get_current_student(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "student":
        raise ForbiddenException("仅学生可操作")
    return current_user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise ForbiddenException("仅管理员可操作")
    return current_user
