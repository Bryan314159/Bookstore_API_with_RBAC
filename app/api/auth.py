from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.user import (
    UserCreate,
    UserLogin,
    RefreshRequest,
    ForgotPassword,
    ResetPassword,
    TokenResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    return await auth_service.register_user(db, user_data.email, user_data.password)


@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    return await auth_service.login_user(db, login_data.email, login_data.password)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.refresh_access_token(db, refresh_data.refresh_token)


@router.post("/forgot-password")
async def forgot_password(forgot_data: ForgotPassword, db: AsyncSession = Depends(get_db)):
    reset_token = await auth_service.forgot_password_request(db, forgot_data.email)
    if reset_token:
        print(f"[DEV] Password reset token for {forgot_data.email}: {reset_token}")
    return {"message": "If the email exists, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(reset_data: ResetPassword, db: AsyncSession = Depends(get_db)):
    await auth_service.reset_user_password(db, reset_data.token, reset_data.new_password)
    return {"message": "Password has been reset successfully."}