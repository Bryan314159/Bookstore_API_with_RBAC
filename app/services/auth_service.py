from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from jose import JWTError
from datetime import datetime, timedelta, timezone

from app.models.user import User
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    create_reset_token,
)
from app.schemas.user import TokenResponse
from app.config import settings


async def register_user(db: AsyncSession, email: str, password: str) -> TokenResponse:
    # 检查邮箱唯一
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    hashed_pw = hash_password(password)
    new_user = User(
        email=email,
        hashed_password=hashed_pw,
        role="user",
        is_active=True,
        refresh_token_version=0,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    access_token = create_access_token(new_user.id, new_user.role)
    refresh_token = create_refresh_token(new_user.id, new_user.refresh_token_version)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


async def login_user(db: AsyncSession, email: str, password: str) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="User account is disabled")

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id, user.refresh_token_version)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


async def refresh_access_token(db: AsyncSession, refresh_token_str: str) -> TokenResponse:
    try:
        payload = decode_token(refresh_token_str)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id_str = payload.get("sub")
    token_version = payload.get("version")
    if user_id_str is None or token_version is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")

    if token_version != user.refresh_token_version:
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    new_version = user.refresh_token_version + 1
    await db.execute(
        update(User).where(User.id == user.id).values(refresh_token_version=new_version)
    )
    await db.commit()

    access_token = create_access_token(user.id, user.role)
    new_refresh_token = create_refresh_token(user.id, new_version)

    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


async def forgot_password_request(db: AsyncSession, email: str) -> str:
    """返回重置 token（开发环境打印用），无论用户是否存在都返回 None 或空字符串"""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is not None:
        reset_token = create_reset_token(user.id)
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)
        await db.execute(
            update(User)
            .where(User.id == user.id)
            .values(reset_token=reset_token, reset_token_expires=expires.replace(tzinfo=None))
        )
        await db.commit()
        return reset_token  # 开发环境可打印
    return ""


async def reset_user_password(db: AsyncSession, token: str, new_password: str) -> None:
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    if payload.get("type") != "reset":
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or user.reset_token != token:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    token_expires_utc = (
        user.reset_token_expires.replace(tzinfo=timezone.utc)
        if user.reset_token_expires else None
    )
    now = datetime.now(timezone.utc)
    if token_expires_utc is None or token_expires_utc < now:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    new_hashed = hash_password(new_password)
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(hashed_password=new_hashed, reset_token=None, reset_token_expires=None)
    )
    await db.commit()