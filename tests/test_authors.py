import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.models.user import User
from app.models.author import Author
from app.models.book import Book


# --------------- 辅助函数 ---------------
async def _register_and_login(async_client, email, password="a1234567"):
    """注册并登录，返回 access_token"""
    await async_client.post("/auth/register", json={"email": email, "password": password})
    resp = await async_client.post("/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


async def _create_author(async_client, token, name, bio="A bio"):
    """创建作者，返回 httpx.Response"""
    return await async_client.post(
        "/authors",
        json={"name": name, "bio": bio},
        headers={"Authorization": f"Bearer {token}"}
    )


# --------------- 公开读取 ---------------
@pytest.mark.asyncio
async def test_get_authors_public(async_client: AsyncClient):
    """A2: 无需认证即可获取作者列表"""
    token = await _register_and_login(async_client, "listuser@test.com")
    await _create_author(async_client, token, "Public Author")

    resp = await async_client.get("/authors")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_single_author_public(async_client: AsyncClient):
    """A3: 无需认证即可获取单个作者"""
    token = await _register_and_login(async_client, "single@test.com")
    create_resp = await _create_author(async_client, token, "Single Author")
    author_id = create_resp.json()["id"]

    resp = await async_client.get(f"/authors/{author_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Single Author"


# --------------- 创建作者 ---------------
@pytest.mark.asyncio
async def test_create_author_requires_auth(async_client: AsyncClient):
    """未登录创建作者应返回 401"""
    resp = await async_client.post("/authors", json={"name": "NoAuth"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_author_success(async_client: AsyncClient):
    """A1: 正常创建作者，验证 created_by 自动记录"""
    token = await _register_and_login(async_client, "creator@test.com")
    resp = await _create_author(async_client, token, "New Author", "Some bio")
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "New Author"
    assert data["bio"] == "Some bio"

    # 验证 created_by 等于当前用户 ID
    me = await async_client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert data["created_by"] == me.json()["id"]


@pytest.mark.asyncio
async def test_create_author_duplicate_name(async_client: AsyncClient):
    """重复 name 返回 409"""
    token = await _register_and_login(async_client, "dup@test.com")
    await _create_author(async_client, token, "Duplicate")
    resp = await _create_author(async_client, token, "Duplicate")
    assert resp.status_code == 409


# --------------- 更新作者 ---------------
@pytest.mark.asyncio
async def test_update_author_requires_auth(async_client: AsyncClient):
    """未登录更新返回 401"""
    token = await _register_and_login(async_client, "upna@test.com")
    create_resp = await _create_author(async_client, token, "Up No Auth")
    author_id = create_resp.json()["id"]

    resp = await async_client.put(
        f"/authors/{author_id}",
        json={"name": "New Name", "bio": "new"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_author_by_owner(async_client: AsyncClient):
    """创建者可以更新自己的作者"""
    token = await _register_and_login(async_client, "owner@test.com")
    create_resp = await _create_author(async_client, token, "My Author")
    author_id = create_resp.json()["id"]

    resp = await async_client.put(
        f"/authors/{author_id}",
        json={"name": "Updated Name", "bio": "Updated bio"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_update_author_by_other_user_forbidden(async_client: AsyncClient):
    """普通用户不能修改他人的作者"""
    token_a = await _register_and_login(async_client, "a@test.com")
    token_b = await _register_and_login(async_client, "b@test.com")

    create_resp = await _create_author(async_client, token_a, "A's Author")
    author_id = create_resp.json()["id"]

    resp = await async_client.put(
        f"/authors/{author_id}",
        json={"name": "Hacked", "bio": "no"},
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_author_by_admin(async_client: AsyncClient, db_session):
    """管理员可以修改任意作者"""
    # 创建管理员
    admin_token = await _register_and_login(async_client, "admin@test.com")
    await db_session.execute(
        update(User).where(User.email == "admin@test.com").values(role="admin")
    )
    await db_session.commit()
    # 重新登录获取有效 token
    login_resp = await async_client.post("/auth/login", json={"email": "admin@test.com", "password": "a1234567"})
    admin_token = login_resp.json()["access_token"]

    # 普通用户创建作者
    user_token = await _register_and_login(async_client, "user@test.com")
    create_resp = await _create_author(async_client, user_token, "User's Author")
    author_id = create_resp.json()["id"]

    # admin 更新
    resp = await async_client.put(
        f"/authors/{author_id}",
        json={"name": "Admin Updated", "bio": "by admin"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Admin Updated"


@pytest.mark.asyncio
async def test_update_author_duplicate_name(async_client: AsyncClient):
    """更新时 name 不能与已有作者重复"""
    token = await _register_and_login(async_client, "updup@test.com")
    await _create_author(async_client, token, "Author X")
    create_resp = await _create_author(async_client, token, "Author Y")
    author_y_id = create_resp.json()["id"]

    resp = await async_client.put(
        f"/authors/{author_y_id}",
        json={"name": "Author X", "bio": "dup"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 409


# --------------- 删除作者 ---------------
@pytest.mark.asyncio
async def test_delete_author_by_owner_no_books(async_client: AsyncClient):
    """A5: 创建者可删除无图书的作者"""
    token = await _register_and_login(async_client, "delowner@test.com")
    create_resp = await _create_author(async_client, token, "To Delete")
    author_id = create_resp.json()["id"]

    resp = await async_client.delete(
        f"/authors/{author_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 204

    # 确认已删除
    get_resp = await async_client.get(f"/authors/{author_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_author_by_other_user_forbidden(async_client: AsyncClient):
    """普通用户不能删除他人的作者"""
    token_a = await _register_and_login(async_client, "da@test.com")
    token_b = await _register_and_login(async_client, "db@test.com")
    create_resp = await _create_author(async_client, token_a, "A2 Author")
    author_id = create_resp.json()["id"]

    resp = await async_client.delete(
        f"/authors/{author_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_author_by_admin(async_client: AsyncClient, db_session):
    """管理员可以删除任意作者（无图书）"""
    admin_token = await _register_and_login(async_client, "admin2@test.com")
    await db_session.execute(
        update(User).where(User.email == "admin2@test.com").values(role="admin")
    )
    await db_session.commit()
    login_resp = await async_client.post("/auth/login", json={"email": "admin2@test.com", "password": "a1234567"})
    admin_token = login_resp.json()["access_token"]

    user_token = await _register_and_login(async_client, "user2@test.com")
    create_resp = await _create_author(async_client, user_token, "U2 Author")
    author_id = create_resp.json()["id"]

    resp = await async_client.delete(
        f"/authors/{author_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_author_with_books_conflict(async_client: AsyncClient, db_session):
    """有图书时删除作者返回 409"""
    token = await _register_and_login(async_client, "withbook@test.com")
    author_resp = await _create_author(async_client, token, "Author With Books")
    author_id = author_resp.json()["id"]

    # 通过数据库直接添加一本图书
    me = await async_client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    user_id = me.json()["id"]
    book = Book(title="Test Book", author_id=author_id, published_year=2021, created_by=user_id)
    db_session.add(book)
    await db_session.commit()

    resp = await async_client.delete(
        f"/authors/{author_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 409

    # 确保作者依旧存在
    get_resp = await async_client.get(f"/authors/{author_id}")
    assert get_resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_author_requires_auth(async_client: AsyncClient):
    """未登录删除作者返回 401"""
    token = await _register_and_login(async_client, "delna@test.com")
    create_resp = await _create_author(async_client, token, "Del No Auth")
    author_id = create_resp.json()["id"]

    resp = await async_client.delete(f"/authors/{author_id}")
    assert resp.status_code == 401