from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT 签名算法
ALGORITHM = "HS256"

def hash_password(plain: str) -> str:
    """对明文密码进行 bcrypt 哈希"""
    return pwd_context.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    """验证明文密码与哈希是否匹配"""
    return pwd_context.verify(plain, hashed)

def _create_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """内部通用 Token 生成函数"""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=15)
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)

def create_access_token(user_id: int, role: str) -> str:
    """生成 Access Token，有效期从配置读取"""
    expire = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _create_token(
        {"sub": str(user_id), "role": role, "type": "access"},
        expires_delta=expire,
    )

def create_refresh_token(user_id: int, version: int = 0) -> str:
    """生成 Refresh Token，有效期从配置读取，包含版本号用于滚动更新"""
    expire = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _create_token(
        {
            "sub": str(user_id),
            "type": "refresh",
            "version": version,
        },
        expires_delta=expire,
    )

def create_reset_token(user_id: int, expires_delta: Optional[int] = None) -> str:
    """生成一次性密码重置 Token，默认有效期 15 分钟"""
    if expires_delta is None:
        expires_delta = settings.RESET_TOKEN_EXPIRE_MINUTES
    delta = timedelta(minutes=expires_delta)
    return _create_token(
        {"sub": str(user_id), "type": "reset"},
        expires_delta=delta,
    )

def decode_token(token: str) -> dict:
    """解码并验证 JWT Token，返回载荷字典；无效时抛出 JWTError"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_exp": True},
        )
        return payload
    except JWTError:
        raise