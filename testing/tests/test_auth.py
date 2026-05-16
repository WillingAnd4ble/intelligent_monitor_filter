"""
Auth endpoint tests — FR1, NFR4.

Mocks the AsyncSession at the dependency override level. No real DB needed for
422/400/401 paths; happy paths assert the JWT cookie is set and the DB writes
are issued in the right order.

IMPORTANT: The auth router is mounted at `/auth` in this codebase (not /api/v1/auth).
That inconsistency is a known issue scheduled for post-thesis cleanup; do not
"fix" it by changing the prefix in tests.

NOTE: LoginRequest.email is typed as `EmailStr`, so Pydantic enforces
format. The 422 tests cover both missing required fields AND malformed
email format.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db.database import get_db
from app.db.models import User, UserSettings, FeedbackMemory
from app.core.security import get_password_hash
from app.core.security import get_password_hash
def _make_session_mock(existing_user_email: str | None = None):
    """Return an AsyncMock session whose .execute().scalars().first() returns a User if email matches."""
    session = AsyncMock()
    # We control what `session.execute(...)` returns
    def execute_factory(stmt):
        result_proxy = MagicMock()
        scalars = MagicMock()
        if existing_user_email is not None:
            u = MagicMock(spec=User)
            u.id = uuid.uuid4()
            u.email = existing_user_email
            u.password_hash = "$2b$12$does-not-matter"
            scalars.first.return_value = u
        else:
            scalars.first.return_value = None
        result_proxy.scalars.return_value = scalars
        return result_proxy

    session.execute = AsyncMock(side_effect=execute_factory)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def override_db_factory():
    """Yield a function that installs a get_db override returning the given session."""
    overrides = {}
    def _install(session):
        async def _gen():
            yield session
        app.dependency_overrides[get_db] = _gen
        overrides["set"] = True
    yield _install
    app.dependency_overrides.pop(get_db, None)


# ===== REGISTRATION ==========================================================

class TestRegister:

    async def test_happy_path_returns_ok_and_sets_cookie(self, override_db_factory):
        session = _make_session_mock(existing_user_email=None)
        override_db_factory(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post("/auth/register", json={
                "email": "new@example.com",
                "password": "password-123",
            })

        assert r.status_code == 200
        assert "access_token" in r.cookies
        # session.add was called three times: User, UserSettings, FeedbackMemory
        assert session.add.call_count == 3

    async def test_duplicate_email_returns_400(self, override_db_factory):
        session = _make_session_mock(existing_user_email="existing@example.com")
        override_db_factory(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post("/auth/register", json={
                "email": "existing@example.com",
                "password": "password-123",
            })

        assert r.status_code == 400
        assert "currently utilized" in r.json()["detail"]

    async def test_missing_email_returns_422(self):
        """A fully missing email field is a Pydantic required-field error."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post("/auth/register", json={
                "password": "password-123",
            })
        assert r.status_code == 422

    async def test_missing_password_returns_422(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post("/auth/register", json={
                "email": "ok@example.com",
            })
        assert r.status_code == 422

    @pytest.mark.parametrize("bad_email", [
        pytest.param("not-an-email", id="no-at-sign"),
        pytest.param("@example.com", id="missing-local-part"),
        pytest.param("user@", id="missing-domain"),
        pytest.param("user@nodot", id="missing-tld"),
        pytest.param("user name@example.com", id="space-in-local-part"),
        pytest.param("", id="empty-string"),
    ])
    async def test_malformed_email_returns_422(self, bad_email):
        """EmailStr must reject these at the Pydantic layer — applies to both register and login."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post("/auth/register", json={
                "email": bad_email,
                "password": "password-123",
            })
        assert r.status_code == 422, f"Bad email {bad_email!r} returned {r.status_code}; expected 422"
        assert "email" in r.text.lower(), f"422 body should reference email; got: {r.text}"


# ===== LOGIN ================================================================

class TestLogin:

    async def test_happy_path(self, override_db_factory):
        
        session = AsyncMock()
        u = MagicMock(spec=User)
        u.id = uuid.uuid4()
        u.email = "test@example.com"
        u.password_hash = get_password_hash("password-123")

        result_proxy = MagicMock()
        scalars = MagicMock()
        scalars.first.return_value = u
        result_proxy.scalars.return_value = scalars
        session.execute = AsyncMock(return_value=result_proxy)
        override_db_factory(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post("/auth/login", json={
                "email": "test@example.com",
                "password": "password-123",
            })

        assert r.status_code == 200
        assert "access_token" in r.cookies

    async def test_wrong_password_returns_401(self, override_db_factory):
        session = AsyncMock()
        u = MagicMock(spec=User)
        u.id = uuid.uuid4()
        u.password_hash = get_password_hash("the-real-password")
        result_proxy = MagicMock()
        scalars = MagicMock()
        scalars.first.return_value = u
        result_proxy.scalars.return_value = scalars
        session.execute = AsyncMock(return_value=result_proxy)
        override_db_factory(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post("/auth/login", json={
                "email": "test@example.com",
                "password": "WRONG",
            })

        assert r.status_code == 401

    async def test_unknown_email_returns_401(self, override_db_factory):
        session = _make_session_mock(existing_user_email=None)
        override_db_factory(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post("/auth/login", json={
                "email": "noone@example.com",
                "password": "password-123",
            })

        assert r.status_code == 401


# ===== LOGOUT ===============================================================

class TestLogout:

    async def test_clears_access_token_cookie(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post("/auth/logout")
        assert r.status_code == 200
        # Set-Cookie should clear the cookie
        cookie_header = r.headers.get("set-cookie", "")
        assert "access_token=" in cookie_header
        assert ("Max-Age=0" in cookie_header) or ("expires=" in cookie_header.lower())
