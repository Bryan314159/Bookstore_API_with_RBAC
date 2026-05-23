import re
from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, EmailStr, field_validator, ConfigDict

from app.config import settings


# ---------- 请求体 ----------

class UserCreate(BaseModel):
    """用户注册"""
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < settings.PASSWORD_MIN_LENGTH:
            raise ValueError(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters")
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Password must contain both letters and numbers")
        return v


class UserLogin(BaseModel):
    """用户登录"""
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """刷新Token"""
    refresh_token: str


class PasswordChange(BaseModel):
    """修改密码"""
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        # 复用注册时的密码规则
        return UserCreate.validate_password(v)


class ForgotPassword(BaseModel):
    """忘记密码"""
    email: EmailStr


class ResetPassword(BaseModel):
    """重置密码"""
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return UserCreate.validate_password(v)


class UserRoleUpdate(BaseModel):
    """管理员修改用户角色"""
    role: Literal["user", "admin"]


class UserStatusUpdate(BaseModel):
    """管理员修改用户状态"""
    is_active: bool


# ---------- 响应体 ----------

class TokenResponse(BaseModel):
    """Token 对响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """用户公开信息"""
    id: int
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)