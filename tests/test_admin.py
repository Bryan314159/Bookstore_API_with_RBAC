import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from datetime import datetime, timedelta, timezone

import asyncio

from app.models.user import User
from app.models.audit_log import AuditLog


# --------------- 辅助函数 ---------------
async def _register_and_login(async_client, email, password="a1234567"):
    """注册并登录，返回 access_token"""
    await async_client.post("/auth/register", json={"email": email, "password": password})
    resp = await async_client.post("/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


async def _make_admin(async_client, db_session, email):
    """将指定用户提升为管理员，并返回新的 admin token"""
    await db_session.execute(
        update(User).where(User.email == email).values(role="admin")
    )
    await db_session.commit()
    # 重新登录以获取包含 admin 角色的新 token
    login_resp = await async_client.post("/auth/login", json={"email": email, "password": "a1234567"})
    return login_resp.json()["access_token"]


async def _create_user(async_client, email, password="a1234567"):
    """注册用户，返回用户 ID（通过 GET /users/me）"""
    token = await _register_and_login(async_client, email, password)
    me = await async_client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    return me.json()["id"]


# ==============================
# 用户列表 (M1)
# ==============================
@pytest.mark.asyncio
async def test_get_users_by_admin(async_client: AsyncClient, db_session):
    """管理员可以获取所有用户列表，字段不含密码"""
    # 创建管理员
    await _register_and_login(async_client, "admin@test.com")
    admin_token = await _make_admin(async_client, db_session, "admin@test.com")
    # 创建几个普通用户
    await _create_user(async_client, "user1@test.com")
    await _create_user(async_client, "user2@test.com")

    resp = await async_client.get("/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)
    assert len(users) >= 3  # admin + user1 + user2

    # 验证返回字段
    required_keys = {"id", "email", "role", "is_active", "created_at"}
    for u in users:
        assert required_keys.issubset(u.keys())
        assert "hashed_password" not in u


@pytest.mark.asyncio
async def test_get_users_by_regular_user_forbidden(async_client: AsyncClient, db_session):
    """普通用户无权获取用户列表，返回 403"""
    user_token = await _register_and_login(async_client, "normal@test.com")
    resp = await async_client.get("/admin/users", headers={"Authorization": f"Bearer {user_token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_users_unauthorized(async_client: AsyncClient):
    """未登录请求返回 401"""
    resp = await async_client.get("/admin/users")
    assert resp.status_code == 401


# ==============================
# 修改用户状态 (M2)
# ==============================
@pytest.mark.asyncio
async def test_admin_disable_user(async_client: AsyncClient, db_session):
    """管理员可以禁用其他用户，被禁用用户无法登录"""
    # 创建管理员
    await _register_and_login(async_client, "admin2@test.com")
    admin_token = await _make_admin(async_client, db_session, "admin2@test.com")
    # 创建待禁用的用户
    user_id = await _create_user(async_client, "victim@test.com")

    # 管理员禁用该用户
    resp = await async_client.patch(
        f"/admin/users/{user_id}/status",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_active"] is False

    # 确认该用户无法登录
    login_resp = await async_client.post("/auth/login", json={
        "email": "victim@test.com", "password": "a1234567"
    })
    assert login_resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_cannot_disable_self(async_client: AsyncClient, db_session):
    """管理员不能禁用自己，返回 403"""
    await _register_and_login(async_client, "admin_self@test.com")
    admin_token = await _make_admin(async_client, db_session, "admin_self@test.com")
    # 获取自己的 ID
    me = await async_client.get("/users/me", headers={"Authorization": f"Bearer {admin_token}"})
    admin_id = me.json()["id"]

    resp = await async_client.patch(
        f"/admin/users/{admin_id}/status",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 403
    assert "cannot disable yourself" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_regular_user_cannot_change_status(async_client: AsyncClient, db_session):
    """普通用户不能修改他人状态（管理端点），应返回 403"""
    user_token = await _register_and_login(async_client, "normal2@test.com")
    target_id = await _create_user(async_client, "target@test.com")

    resp = await async_client.patch(
        f"/admin/users/{target_id}/status",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert resp.status_code == 403


# ==============================
# 修改用户角色 (M3)
# ==============================
@pytest.mark.asyncio
async def test_admin_change_user_role(async_client: AsyncClient, db_session):
    """管理员可以修改其他用户的角色"""
    await _register_and_login(async_client, "admin3@test.com")
    admin_token = await _make_admin(async_client, db_session, "admin3@test.com")
    user_id = await _create_user(async_client, "user_to_promote@test.com")

    resp = await async_client.patch(
        f"/admin/users/{user_id}/role",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"

    # 验证该用户现在拥有管理员权限（访问 /admin/users 成功）
    # 先重新登录获取新 token
    login_resp = await async_client.post("/auth/login", json={
        "email": "user_to_promote@test.com", "password": "a1234567"
    })
    new_token = login_resp.json()["access_token"]
    admin_check = await async_client.get("/admin/users", headers={"Authorization": f"Bearer {new_token}"})
    assert admin_check.status_code == 200


@pytest.mark.asyncio
async def test_admin_cannot_change_own_role(async_client: AsyncClient, db_session):
    """管理员不能修改自己的角色，返回 403"""
    await _register_and_login(async_client, "admin_immortal@test.com")
    admin_token = await _make_admin(async_client, db_session, "admin_immortal@test.com")
    me = await async_client.get("/users/me", headers={"Authorization": f"Bearer {admin_token}"})
    admin_id = me.json()["id"]

    resp = await async_client.patch(
        f"/admin/users/{admin_id}/role",
        json={"role": "user"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 403
    assert "cannot change your own role" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_regular_user_cannot_change_role(async_client: AsyncClient, db_session):
    """普通用户不能修改他人角色，返回 403"""
    user_token = await _register_and_login(async_client, "normal3@test.com")
    target_id = await _create_user(async_client, "target2@test.com")

    resp = await async_client.patch(
        f"/admin/users/{target_id}/role",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert resp.status_code == 403


# ==============================
# 审计日志查看 (L3)
# ==============================
@pytest.mark.asyncio
async def test_admin_view_audit_logs(async_client: AsyncClient, db_session):
    """管理员可以查看审计日志，支持过滤"""
    # 创建管理员并获取 token
    await _register_and_login(async_client, "audit_admin@test.com")
    admin_token = await _make_admin(async_client, db_session, "audit_admin@test.com")

    # 插入一些审计日志（使用 naive datetime 与 SQLite 兼容）
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    logs = [
        AuditLog(user_id=1, action="CREATE", resource_type="Book", resource_id=10,
                 description="Created a book", created_at=now),
        AuditLog(user_id=2, action="UPDATE", resource_type="Author", resource_id=5,
                 description="Updated author", created_at=now),
        AuditLog(user_id=1, action="DELETE", resource_type="Book", resource_id=10,
                 description="Deleted a book", created_at=now - timedelta(days=1)),
    ]
    for log in logs:
        db_session.add(log)
    await db_session.commit()

    # 无过滤查询所有日志
    resp = await async_client.get("/admin/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    all_logs = resp.json()
    assert len(all_logs) == 3

    # 按 user_id 过滤
    resp = await async_client.get("/admin/audit-logs", params={"user_id": 1},
                                  headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    filtered = resp.json()
    assert len(filtered) == 2
    assert all(log["user_id"] == 1 for log in filtered)

    # 按 action 过滤
    resp = await async_client.get("/admin/audit-logs", params={"action": "UPDATE"},
                                  headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # 按时间范围过滤（传入 ISO 格式字符串，由 httpx 编码）
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    resp = await async_client.get("/admin/audit-logs", params={"start_time": yesterday},
                                  headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    # 只应返回两条今天创建的日志（排除昨天那条）
    assert len(resp.json()) == 2

@pytest.mark.asyncio
async def test_audit_logs_access_forbidden(async_client: AsyncClient, db_session):
    """普通用户无法查看审计日志（403）"""
    user_token = await _register_and_login(async_client, "normal4@test.com")
    resp = await async_client.get("/admin/audit-logs", headers={"Authorization": f"Bearer {user_token}"})
    assert resp.status_code == 403

    # 未登录访问
    resp = await async_client.get("/admin/audit-logs")
    assert resp.status_code == 401


# ==============================
# 审计日志写入验证 (L1, L2)
# ==============================
@pytest.mark.asyncio
async def test_audit_log_created_on_author_creation(async_client: AsyncClient, db_session):
    """创建作者时，审计日志中应出现对应记录"""
    # 准备管理员
    await _register_and_login(async_client, "admin_audit1@test.com")
    admin_token = await _make_admin(async_client, db_session, "admin_audit1@test.com")

    # 创建一个作者
    resp = await async_client.post(
        "/authors",
        json={"name": "Log Author", "bio": "for audit test"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 201
    author_id = resp.json()["id"]

    await asyncio.sleep(0.1)

    # 查询审计日志，应至少包含一条 CREATE 记录
    resp = await async_client.get("/admin/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    logs = resp.json()
    matching = [log for log in logs if log["action"] == "CREATE" and log["resource_type"] == "Author"]
    assert len(matching) >= 1

    # 验证日志字段
    last_log = matching[0]
    assert last_log["resource_id"] == author_id
    assert "Created author" in last_log["description"] or "Log Author" in last_log["description"]
    assert last_log["user_id"] is not None  # 记录操作者


@pytest.mark.asyncio
async def test_audit_log_created_on_book_creation(async_client: AsyncClient, db_session):
    """创建图书时，审计日志应记录"""
    await _register_and_login(async_client, "admin_audit2@test.com")
    admin_token = await _make_admin(async_client, db_session, "admin_audit2@test.com")

    # 先创建一个作者用于图书
    author_resp = await async_client.post(
        "/authors",
        json={"name": "Author for Book Audit"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    author_id = author_resp.json()["id"]

    # 创建图书
    book_resp = await async_client.post(
        "/books",
        json={"title": "Audited Book", "author_id": author_id, "published_year": 2024},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert book_resp.status_code == 201
    book_id = book_resp.json()["id"]
    await asyncio.sleep(0.1)
    resp = await async_client.get("/admin/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
    logs = resp.json()
    matching = [log for log in logs if log["action"] == "CREATE" and log["resource_type"] == "Book"]
    assert len(matching) >= 1
    last_log = matching[0]
    assert last_log["resource_id"] == book_id
    assert "Created book" in last_log["description"] or "Audited Book" in last_log["description"]


@pytest.mark.asyncio
async def test_audit_log_on_update(async_client: AsyncClient, db_session):
    """更新作者时应记录 UPDATE 日志"""
    await _register_and_login(async_client, "admin_audit3@test.com")
    admin_token = await _make_admin(async_client, db_session, "admin_audit3@test.com")

    # 创建作者
    author_resp = await async_client.post(
        "/authors",
        json={"name": "To Update Author"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    author_id = author_resp.json()["id"]

    # 更新作者
    resp = await async_client.put(
        f"/authors/{author_id}",
        json={"name": "Updated Author", "bio": "new bio"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200

    # 检查审计日志
    await asyncio.sleep(0.1)
    resp = await async_client.get("/admin/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
    logs = resp.json()
    matching = [log for log in logs if log["action"] == "UPDATE" and log["resource_type"] == "Author"]
    assert len(matching) >= 1
    assert matching[0]["resource_id"] == author_id


@pytest.mark.asyncio
async def test_audit_log_on_delete(async_client: AsyncClient, db_session):
    """删除图书时应记录 DELETE 日志"""
    await _register_and_login(async_client, "admin_audit4@test.com")
    admin_token = await _make_admin(async_client, db_session, "admin_audit4@test.com")

    # 准备作者和图书
    author_resp = await async_client.post(
        "/authors",
        json={"name": "Author for Del"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    author_id = author_resp.json()["id"]
    book_resp = await async_client.post(
        "/books",
        json={"title": "Book to delete", "author_id": author_id},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    book_id = book_resp.json()["id"]

    # 删除图书
    del_resp = await async_client.delete(
        f"/books/{book_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert del_resp.status_code == 204

    # 检查审计日志中的 DELETE 记录
    await asyncio.sleep(0.1)
    resp = await async_client.get("/admin/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
    logs = resp.json()
    matching = [log for log in logs if log["action"] == "DELETE" and log["resource_type"] == "Book"]
    assert len(matching) >= 1
    assert matching[0]["resource_id"] == book_id