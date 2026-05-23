from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./bookstore.db"

    # JWT 密钥与过期时间
    SECRET_KEY: str = "change-me-in-production-use-a-real-secret"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    RESET_TOKEN_EXPIRE_MINUTES: int = 15

    # 密码规则
    PASSWORD_MIN_LENGTH: int = 8
    BCRYPT_ROUNDS: int = 12

    # 应用元信息
    APP_NAME: str = "Bookstore API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # 邮件配置（开发环境下无需真实发信，仅用于打印重置链接）
    EMAIL_BACKEND: str = "console"  # console / smtp
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: str = "noreply@bookstore.local"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()