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


async def _create_author(async_client, token, name="Test Author", bio="bio"):
    """创建作者并返回作者 ID"""
    resp = await async_client.post(
        "/authors",
        json={"name": name, "bio": bio},
        headers={"Authorization": f"Bearer {token}"}
    )
    return resp.json()["id"]


async def _create_book(async_client, token, title, author_id, published_year=None):
    """创建图书并返回响应"""
    json_data = {"title": title, "author_id": author_id}
    if published_year is not None:
        json_data["published_year"] = published_year
    return await async_client.post(
        "/books",
        json=json_data,
        headers={"Authorization": f"Bearer {token}"}
    )


# --------------- 公开读取 ---------------
@pytest.mark.asyncio
async def test_get_books_public(async_client: AsyncClient):
    """B2: 无需认证即可获取图书列表"""
    token = await _register_and_login(async_client, "booklist@test.com")
    author_id = await _create_author(async_client, token)
    await _create_book(async_client, token, "Public Book", author_id, 2023)

    resp = await async_client.get("/books")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_books_filter_by_author(async_client: AsyncClient):
    """按 author_id 过滤图书"""
    token = await _register_and_login(async_client, "filter@test.com")
    author_id_a = await _create_author(async_client, token, "Author A")
    author_id_b = await _create_author(async_client, token, "Author B")
    await _create_book(async_client, token, "Book A", author_id_a)
    await _create_book(async_client, token, "Book B", author_id_b)

    resp = await async_client.get("/books", params={"author_id": author_id_a})
    assert resp.status_code == 200
    books = resp.json()
    assert all(book["author_id"] == author_id_a for book in books)


@pytest.mark.asyncio
async def test_get_single_book_public(async_client: AsyncClient):
    """B3: 无需认证获取单本图书"""
    token = await _register_and_login(async_client, "singlebook@test.com")
    author_id = await _create_author(async_client, token)
    create_resp = await _create_book(async_client, token, "Single Book", author_id)
    book_id = create_resp.json()["id"]

    resp = await async_client.get(f"/books/{book_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Single Book"


# --------------- 创建图书 ---------------
@pytest.mark.asyncio
async def test_create_book_requires_auth(async_client: AsyncClient):
    """未登录创建图书返回 401"""
    resp = await async_client.post("/books", json={"title": "No", "author_id": 1})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_book_success(async_client: AsyncClient):
    """B1: 正常创建图书，验证 created_by"""
    token = await _register_and_login(async_client, "bookcreator@test.com")
    author_id = await _create_author(async_client, token)
    resp = await _create_book(async_client, token, "My Book", author_id, 2024)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "My Book"
    assert data["author_id"] == author_id
    assert data["published_year"] == 2024

    me = await async_client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert data["created_by"] == me.json()["id"]


@pytest.mark.asyncio
async def test_create_book_nonexistent_author(async_client: AsyncClient):
    """author_id 不存在应返回错误（如 400 或 404）"""
    token = await _register_and_login(async_client, "badref@test.com")
    resp = await _create_book(async_client, token, "Orphan", 9999)
    assert resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_create_book_published_year_validation(async_client: AsyncClient):
    """published_year 必须为正整数（由 Pydantic 验证，自动返回 422）"""
    token = await _register_and_login(async_client, "year@test.com")
    author_id = await _create_author(async_client, token)
    resp = await _create_book(async_client, token, "Bad Year", author_id, published_year=0)
    assert resp.status_code == 422


# --------------- 更新图书 ---------------
@pytest.mark.asyncio
async def test_update_book_by_owner(async_client: AsyncClient):
    """B4: 创建者可更新自己的图书"""
    token = await _register_and_login(async_client, "owner@test.com")
    author_id = await _create_author(async_client, token)
    create_resp = await _create_book(async_client, token, "Old Title", author_id)
    book_id = create_resp.json()["id"]

    resp = await async_client.put(
        f"/books/{book_id}",
        json={"title": "New Title", "published_year": 2025},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "New Title"


@pytest.mark.asyncio
async def test_update_book_by_other_user_forbidden(async_client: AsyncClient):
    """普通用户不能修改他人的图书"""
    token_a = await _register_and_login(async_client, "a@test.com")
    token_b = await _register_and_login(async_client, "b@test.com")
    author_id = await _create_author(async_client, token_a)
    create_resp = await _create_book(async_client, token_a, "A's Book", author_id)
    book_id = create_resp.json()["id"]

    resp = await async_client.put(
        f"/books/{book_id}",
        json={"title": "Hacked", "published_year": 1999},
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_book_by_admin(async_client: AsyncClient, db_session):
    """管理员可以修改任意图书"""
    admin_token = await _register_and_login(async_client, "admin@test.com")
    await db_session.execute(
        update(User).where(User.email == "admin@test.com").values(role="admin")
    )
    await db_session.commit()
    login_resp = await async_client.post("/auth/login", json={"email": "admin@test.com", "password": "a1234567"})
    admin_token = login_resp.json()["access_token"]

    user_token = await _register_and_login(async_client, "user@test.com")
    author_id = await _create_author(async_client, user_token)
    create_resp = await _create_book(async_client, user_token, "User Book", author_id)
    book_id = create_resp.json()["id"]

    resp = await async_client.put(
        f"/books/{book_id}",
        json={"title": "Admin Edit", "published_year": 2020},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Admin Edit"


@pytest.mark.asyncio
async def test_update_book_requires_auth(async_client: AsyncClient):
    """未登录更新返回 401"""
    token = await _register_and_login(async_client, "unauth@test.com")
    author_id = await _create_author(async_client, token)
    create_resp = await _create_book(async_client, token, "Unauth", author_id)
    book_id = create_resp.json()["id"]

    resp = await async_client.put(
        f"/books/{book_id}",
        json={"title": "x", "published_year": 2020},
    )
    assert resp.status_code == 401


# --------------- 删除图书 ---------------
@pytest.mark.asyncio
async def test_delete_book_by_owner(async_client: AsyncClient):
    """B5: 创建者可删除自己的图书"""
    token = await _register_and_login(async_client, "delowner@test.com")
    author_id = await _create_author(async_client, token)
    create_resp = await _create_book(async_client, token, "To Delete", author_id)
    book_id = create_resp.json()["id"]

    resp = await async_client.delete(
        f"/books/{book_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 204

    # 确认已删除
    get_resp = await async_client.get(f"/books/{book_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_book_by_other_user_forbidden(async_client: AsyncClient):
    """普通用户不能删除他人的图书"""
    token_a = await _register_and_login(async_client, "da@test.com")
    token_b = await _register_and_login(async_client, "db@test.com")
    author_id = await _create_author(async_client, token_a)
    create_resp = await _create_book(async_client, token_a, "A's Book 2", author_id)
    book_id = create_resp.json()["id"]

    resp = await async_client.delete(
        f"/books/{book_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_book_by_admin(async_client: AsyncClient, db_session):
    """管理员可以删除任意图书"""
    admin_token = await _register_and_login(async_client, "adm2@test.com")
    await db_session.execute(
        update(User).where(User.email == "adm2@test.com").values(role="admin")
    )
    await db_session.commit()
    login_resp = await async_client.post("/auth/login", json={"email": "adm2@test.com", "password": "a1234567"})
    admin_token = login_resp.json()["access_token"]

    user_token = await _register_and_login(async_client, "usr2@test.com")
    author_id = await _create_author(async_client, user_token)
    create_resp = await _create_book(async_client, user_token, "Usr Book", author_id)
    book_id = create_resp.json()["id"]

    resp = await async_client.delete(
        f"/books/{book_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_book_requires_auth(async_client: AsyncClient):
    """未登录删除返回 401"""
    token = await _register_and_login(async_client, "delna@test.com")
    author_id = await _create_author(async_client, token)
    create_resp = await _create_book(async_client, token, "Del No Auth", author_id)
    book_id = create_resp.json()["id"]

    resp = await async_client.delete(f"/books/{book_id}")
    assert resp.status_code == 401