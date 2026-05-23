from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from jose import JWTError

from app.database import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    create_reset_token,
)
from app.schemas.user import (
    UserCreate,
    UserLogin,
    RefreshRequest,
    ForgotPassword,
    ResetPassword,
    TokenResponse,
)
from app.models.user import User
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    hashed_pw = hash_password(user_data.password)
    new_user = User(
        email=user_data.email,
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

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == login_data.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
        )

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id, user.refresh_token_version)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshRequest, db: AsyncSession = Depends(get_db)
):
    try:
        payload = decode_token(refresh_data.refresh_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id_str = payload.get("sub")
    token_version = payload.get("version")
    if user_id_str is None or token_version is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or disabled",
        )

    if token_version != user.refresh_token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    new_version = user.refresh_token_version + 1
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(refresh_token_version=new_version)
    )
    await db.commit()

    access_token = create_access_token(user.id, user.role)
    new_refresh_token = create_refresh_token(user.id, new_version)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.post("/forgot-password")
async def forgot_password(
    forgot_data: ForgotPassword, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == forgot_data.email))
    user = result.scalar_one_or_none()

    if user is not None:
        reset_token = create_reset_token(user.id)
        now_aware = datetime.now(timezone.utc)
        expires_aware = now_aware + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)

        # 存入数据库前，转换为 naive UTC
        await db.execute(
            update(User)
            .where(User.id == user.id)
            .values(reset_token=reset_token, reset_token_expires=expires_aware.replace(tzinfo=None))
        )
        await db.commit()

        print(f"[DEV] Password reset token for {user.email}: {reset_token}")

    return {"message": "If the email exists, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(
    reset_data: ResetPassword, db: AsyncSession = Depends(get_db)
):
    try:
        payload = decode_token(reset_data.token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    if payload.get("type") != "reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or user.reset_token != reset_data.token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # 将数据库中的 naive datetime 恢复为 aware UTC
    token_expires_utc = (
        user.reset_token_expires.replace(tzinfo=timezone.utc)
        if user.reset_token_expires else None
    )
    now_aware = datetime.now(timezone.utc)

    if token_expires_utc is None or token_expires_utc < now_aware:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    new_hashed = hash_password(reset_data.new_password)
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            hashed_password=new_hashed,
            reset_token=None,
            reset_token_expires=None,
        )
    )
    await db.commit()

    return {"message": "Password has been reset successfully."}