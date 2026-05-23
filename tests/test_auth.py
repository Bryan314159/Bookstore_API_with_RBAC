import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from datetime import datetime, timedelta, timezone

from app.models.user import User


@pytest.mark.asyncio
async def test_register_success(async_client: AsyncClient):
    resp = await async_client.post("/auth/register", json={
        "email": "new@test.com",
        "password": "a1234567"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(async_client: AsyncClient):
    await async_client.post("/auth/register", json={
        "email": "dup@test.com", "password": "a1234567"
    })
    resp = await async_client.post("/auth/register", json={
        "email": "dup@test.com", "password": "b1234567"
    })
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Email already registered"


@pytest.mark.asyncio
async def test_register_weak_password(async_client: AsyncClient):
    # 太短
    resp = await async_client.post("/auth/register", json={
        "email": "x@test.com", "password": "a1"
    })
    assert resp.status_code == 422
    # 纯数字
    resp = await async_client.post("/auth/register", json={
        "email": "x@test.com", "password": "12345678"
    })
    assert resp.status_code == 422
    # 纯字母
    resp = await async_client.post("/auth/register", json={
        "email": "x@test.com", "password": "abcdefgh"
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient):
    await async_client.post("/auth/register", json={
        "email": "login@test.com", "password": "a1234567"
    })
    resp = await async_client.post("/auth/login", json={
        "email": "login@test.com", "password": "a1234567"
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(async_client: AsyncClient):
    await async_client.post("/auth/register", json={
        "email": "wrongpwd@test.com", "password": "a1234567"
    })
    resp = await async_client.post("/auth/login", json={
        "email": "wrongpwd@test.com", "password": "wrongpassword1"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(async_client: AsyncClient):
    resp = await async_client.post("/auth/login", json={
        "email": "ghost@test.com", "password": "a1234567"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_disabled_user(async_client: AsyncClient, db_session):
    await async_client.post("/auth/register", json={
        "email": "disabled@test.com", "password": "a1234567"
    })
    await db_session.execute(
        update(User).where(User.email == "disabled@test.com").values(is_active=False)
    )
    await db_session.commit()
    resp = await async_client.post("/auth/login", json={
        "email": "disabled@test.com", "password": "a1234567"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_valid_token(async_client: AsyncClient):
    reg_resp = await async_client.post("/auth/register", json={
        "email": "me@test.com", "password": "a1234567"
    })
    token = reg_resp.json()["access_token"]
    resp = await async_client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@test.com"


@pytest.mark.asyncio
async def test_get_me_without_token(async_client: AsyncClient):
    resp = await async_client.get("/users/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_invalid_token(async_client: AsyncClient):
    resp = await async_client.get("/users/me", headers={"Authorization": "Bearer fake.token.here"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_success(async_client: AsyncClient):
    reg_resp = await async_client.post("/auth/register", json={
        "email": "refresh@test.com", "password": "a1234567"
    })
    old_refresh = reg_resp.json()["refresh_token"]
    resp = await async_client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    new_refresh = data["refresh_token"]
    assert new_refresh != old_refresh
    # 旧 Refresh Token 应失效
    resp2 = await async_client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_invalid_token(async_client: AsyncClient):
    resp = await async_client.post("/auth/refresh", json={"refresh_token": "invalid"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_password_success(async_client: AsyncClient):
    reg_resp = await async_client.post("/auth/register", json={
        "email": "changepwd@test.com", "password": "a1234567"
    })
    token = reg_resp.json()["access_token"]
    resp = await async_client.post(
        "/users/me/change-password",
        json={"old_password": "a1234567", "new_password": "b1234567"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    login_resp = await async_client.post("/auth/login", json={
        "email": "changepwd@test.com", "password": "b1234567"
    })
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_old(async_client: AsyncClient):
    reg_resp = await async_client.post("/auth/register", json={
        "email": "wrongold@test.com", "password": "a1234567"
    })
    token = reg_resp.json()["access_token"]
    resp = await async_client.post(
        "/users/me/change-password",
        json={"old_password": "incorrect", "new_password": "b1234567"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Old password is incorrect"


@pytest.mark.asyncio
async def test_forgot_password_endpoint(async_client: AsyncClient):
    # 不存在的邮箱也应返回相同消息
    resp = await async_client.post("/auth/forgot-password", json={"email": "nobody@test.com"})
    assert resp.status_code == 200
    assert "If the email exists" in resp.json()["message"]

    await async_client.post("/auth/register", json={
        "email": "forgot@test.com", "password": "a1234567"
    })
    resp = await async_client.post("/auth/forgot-password", json={"email": "forgot@test.com"})
    assert resp.status_code == 200
    assert "If the email exists" in resp.json()["message"]


@pytest.mark.asyncio
async def test_reset_password_flow(async_client: AsyncClient, db_session):
    """U8: 完整重置密码流程"""
    # 注册用户
    await async_client.post("/auth/register", json={
        "email": "resetflow@test.com", "password": "a1234567"
    })

    # 1. 请求忘记密码，从数据库获取真实 token
    await async_client.post("/auth/forgot-password", json={"email": "resetflow@test.com"})
    result = await db_session.execute(select(User).where(User.email == "resetflow@test.com"))
    user = result.scalar_one()
    reset_token = user.reset_token
    assert reset_token is not None

    # 2. 第一次重置成功
    resp = await async_client.post("/auth/reset-password", json={
        "token": reset_token,
        "new_password": "newpass123"
    })
    assert resp.status_code == 200

    # 3. 重复使用同一 Token 应失败（一次性）
    resp = await async_client.post("/auth/reset-password", json={
        "token": reset_token,
        "new_password": "anotherpassword1"
    })
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid or expired reset token"

    # 4. 过期 Token 测试：再次请求忘记密码，然后手动将过期时间改为过去
    await async_client.post("/auth/forgot-password", json={"email": "resetflow@test.com"})
    result = await db_session.execute(select(User).where(User.email == "resetflow@test.com"))
    user = result.scalar_one()
    expired_token = user.reset_token
    now_aware = datetime.now(timezone.utc)
    expired_aware = now_aware - timedelta(minutes=1)
    # 存入数据库前，去掉时区信息
    await db_session.execute(
        update(User)
        .where(User.id == user.id)
        .values(reset_token_expires=expired_aware.replace(tzinfo=None))
    )
    await db_session.commit()

    resp = await async_client.post("/auth/reset-password", json={
        "token": expired_token,
        "new_password": "expiredpass1"
    })
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid or expired reset token"


@pytest.mark.asyncio
async def test_disabled_user_token_rejected(async_client: AsyncClient, db_session):
    reg_resp = await async_client.post("/auth/register", json={
        "email": "deadtoken@test.com", "password": "a1234567"
    })
    token = reg_resp.json()["access_token"]
    resp = await async_client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    await db_session.execute(
        update(User).where(User.email == "deadtoken@test.com").values(is_active=False)
    )
    await db_session.commit()

    resp = await async_client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401