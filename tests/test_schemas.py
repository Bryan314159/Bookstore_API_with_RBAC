import pytest
from pydantic import ValidationError
from app.schemas.user import (
    UserCreate,
    UserLogin,
    RefreshRequest,
    PasswordChange,
    ForgotPassword,
    ResetPassword,
    UserRoleUpdate,
    UserStatusUpdate,
    TokenResponse,
    UserResponse,
)
from app.schemas.author import AuthorCreate, AuthorUpdate, AuthorResponse
from app.schemas.book import BookCreate, BookUpdate, BookResponse
from app.schemas.audit_log import AuditLogResponse, AuditLogFilter
from app.config import settings


# ==============================
# User Schemas
# ==============================

class TestUserCreate:
    def test_valid_user(self):
        user = UserCreate(email="test@example.com", password="a1234567")
        assert user.email == "test@example.com"
        assert user.password == "a1234567"

    def test_password_too_short(self):
        with pytest.raises(ValidationError) as exc:
            UserCreate(email="test@example.com", password="a1")
        assert "at least" in str(exc.value)

    def test_password_no_letter(self):
        with pytest.raises(ValidationError):
            UserCreate(email="test@example.com", password="12345678")

    def test_password_no_digit(self):
        with pytest.raises(ValidationError):
            UserCreate(email="test@example.com", password="abcdefgh")

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            UserCreate(email="not-an-email", password="a1234567")


class TestPasswordChange:
    def test_valid(self):
        pw = PasswordChange(old_password="old1234", new_password="a1234567")
        assert pw.new_password == "a1234567"

    def test_new_password_weak(self):
        with pytest.raises(ValidationError):
            PasswordChange(old_password="old", new_password="short")


class TestResetPassword:
    def test_valid(self):
        rp = ResetPassword(token="tok", new_password="a1234567")
        assert rp.token == "tok"

    def test_weak_password(self):
        with pytest.raises(ValidationError):
            ResetPassword(token="tok", new_password="weak")


class TestUserRoleUpdate:
    def test_valid_role(self):
        update = UserRoleUpdate(role="admin")
        assert update.role == "admin"

    def test_invalid_role(self):
        with pytest.raises(ValidationError):
            UserRoleUpdate(role="superuser")


class TestUserStatusUpdate:
    def test_valid(self):
        update = UserStatusUpdate(is_active=False)
        assert update.is_active is False


class TestTokenResponse:
    def test_create(self):
        token = TokenResponse(access_token="at", refresh_token="rt")
        assert token.token_type == "bearer"


class TestUserResponse:
    def test_from_orm_compatible(self):
        # 确保 from_attributes 已设置
        assert UserResponse.model_config.get("from_attributes") is True


# ==============================
# Author Schemas
# ==============================

class TestAuthorCreate:
    def test_valid(self):
        author = AuthorCreate(name="J.K. Rowling", bio="British author")
        assert author.name == "J.K. Rowling"

    def test_missing_name(self):
        with pytest.raises(ValidationError):
            AuthorCreate(bio="No name")

    def test_bio_optional(self):
        author = AuthorCreate(name="George Orwell")
        assert author.bio is None


class TestAuthorUpdate:
    def test_valid(self):
        update = AuthorUpdate(name="New Name", bio="New bio")
        assert update.name == "New Name"


class TestAuthorResponse:
    def test_from_attributes(self):
        assert AuthorResponse.model_config.get("from_attributes") is True


# ==============================
# Book Schemas
# ==============================

class TestBookCreate:
    def test_valid(self):
        book = BookCreate(title="1984", author_id=1, published_year=1949)
        assert book.published_year == 1949

    def test_missing_title(self):
        with pytest.raises(ValidationError):
            BookCreate(author_id=1)

    def test_published_year_zero(self):
        with pytest.raises(ValidationError) as exc:
            BookCreate(title="x", author_id=1, published_year=0)
        assert "positive integer" in str(exc.value)

    def test_published_year_negative(self):
        with pytest.raises(ValidationError) as exc:
            BookCreate(title="x", author_id=1, published_year=-5)
        assert "positive integer" in str(exc.value)

    def test_published_year_none_allowed(self):
        book = BookCreate(title="x", author_id=1)
        assert book.published_year is None


class TestBookUpdate:
    def test_valid(self):
        update = BookUpdate(title="New Title", published_year=2020)
        assert update.title == "New Title"

    def test_invalid_year(self):
        with pytest.raises(ValidationError):
            BookUpdate(title="x", published_year=0)


class TestBookResponse:
    def test_from_attributes(self):
        assert BookResponse.model_config.get("from_attributes") is True


# ==============================
# Audit Log Schemas
# ==============================

class TestAuditLogResponse:
    def test_from_attributes(self):
        assert AuditLogResponse.model_config.get("from_attributes") is True

    def test_create_minimal(self):
        log = AuditLogResponse(
            id=1,
            action="CREATE",
            resource_type="Book",
            resource_id=5,
            created_at="2024-01-01T00:00:00Z"
        )
        assert log.user_id is None
        assert log.description is None


class TestAuditLogFilter:
    def test_all_optional(self):
        f = AuditLogFilter()
        assert f.user_id is None
        assert f.action is None
        assert f.start_time is None
        assert f.end_time is None

    def test_with_params(self):
        f = AuditLogFilter(user_id=1, action="DELETE")
        assert f.user_id == 1
        assert f.action == "DELETE"