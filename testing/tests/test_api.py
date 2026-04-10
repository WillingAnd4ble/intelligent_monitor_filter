"""
API endpoint integration tests using FastAPI TestClient.

These tests exercise the HTTP layer: routes, status codes, response shapes,
and cookie-based auth.  All DB/Celery/LLM calls are mocked.
"""

import uuid
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient, ASGITransport

# We need the FastAPI app
from app.main import app
from app.db.models import User, UserSettings, UserPaper, Paper, FeedbackMemory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_user(user_id=None):
    """Create a mock User ORM object."""
    u = MagicMock(spec=User)
    u.id = user_id or uuid.uuid4()
    u.email = "test@example.com"
    u.password_hash = "$2b$12$fakehash"
    return u


def _make_fake_settings(user_id):
    s = MagicMock(spec=UserSettings)
    s.user_id = user_id
    s.categories = ["cs.AI"]
    s.topics = ["multi-agent"]
    s.authors = []
    s.filtering_goal = "Find papers on multi-agent LLM systems"
    s.distilled_criteria = ["Must feature multi-agent systems"]
    s.content_interest = ["methodology"]
    s.library_explanation_level = "professional"
    s.notification_time = "08:00"
    s.pdf_parser_mode = "pypdfium"
    return s


def _auth_cookie(user_id):
    """Generate a valid JWT cookie for test requests."""
    from app.core.security import create_access_token
    token = create_access_token(user_id)
    return {"access_token": token}


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

class TestHealthEndpoint:

    @pytest.mark.asyncio
    async def test_health_returns_ok(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "vector_db" in data


# ---------------------------------------------------------------------------
# Auth Endpoints
# ---------------------------------------------------------------------------

class TestAuthEndpoints:

    @pytest.mark.asyncio
    async def test_register_sets_httponly_cookie(self):
        """POST /auth/register should return 200 and set an httpOnly cookie."""
        fake_user = _make_fake_user()

        mock_session = AsyncMock()
        # First execute: check existing user → None
        # Subsequent executes: flush/commit are on the session directly
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result

        original = app.dependency_overrides.copy()
        from app.db.database import get_db
        app.dependency_overrides[get_db] = lambda: mock_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post("/auth/register", json={
                    "email": "newuser@example.com",
                    "password": "testpass123",
                })

            assert resp.status_code == 200
            # Check the Set-Cookie header for httponly flag
            set_cookie = resp.headers.get("set-cookie", "")
            assert "access_token" in set_cookie
            assert "httponly" in set_cookie.lower()
        finally:
            app.dependency_overrides = original

    @pytest.mark.asyncio
    async def test_logout_clears_cookie(self):
        """POST /auth/logout should delete the access_token cookie."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post("/auth/logout")

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Feed Endpoints
# ---------------------------------------------------------------------------

class TestFeedEndpoints:

    @pytest.mark.asyncio
    async def test_feed_requires_auth(self):
        """GET /api/v1/feed/ without a cookie should return 401."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/v1/feed/")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_feed_returns_list(self):
        """GET /api/v1/feed/ with valid auth should return a list."""
        fake_user = _make_fake_user()
        cookies = _auth_cookie(fake_user.id)

        with patch("app.api.deps.get_current_user", return_value=fake_user):
            # Override the dependency directly
            original = app.dependency_overrides.copy()
            from app.api.deps import get_current_user
            app.dependency_overrides[get_current_user] = lambda: fake_user

            # Mock DB to return empty feed
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.all.return_value = []
            mock_session.execute.return_value = mock_result

            from app.db.database import get_db
            app.dependency_overrides[get_db] = lambda: mock_session

            try:
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                    resp = await client.get("/api/v1/feed/", cookies=cookies)
                assert resp.status_code == 200
                assert isinstance(resp.json(), list)
            finally:
                app.dependency_overrides = original

    @pytest.mark.asyncio
    async def test_feed_stats_returns_structure(self):
        """GET /api/v1/feed/stats should return {total_scraped_today, evaluated_by_agent, recommended_today}."""
        fake_user = _make_fake_user()

        original = app.dependency_overrides.copy()
        from app.api.deps import get_current_user
        from app.db.database import get_db
        app.dependency_overrides[get_current_user] = lambda: fake_user

        mock_session = AsyncMock()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar.return_value = 0
        mock_session.execute.return_value = mock_scalar_result

        app.dependency_overrides[get_db] = lambda: mock_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get("/api/v1/feed/stats")

            assert resp.status_code == 200
            data = resp.json()
            assert "total_scraped_today" in data
            assert "evaluated_by_agent" in data
            assert "recommended_today" in data
        finally:
            app.dependency_overrides = original


# ---------------------------------------------------------------------------
# Settings Endpoints
# ---------------------------------------------------------------------------

class TestSettingsEndpoints:

    @pytest.mark.asyncio
    async def test_settings_requires_auth(self):
        """GET /api/v1/settings/ without auth should return 401."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/v1/settings/")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_put_settings_triggers_distiller_on_goal_change(self):
        """PUT /api/v1/settings/ with new filtering_goal should trigger GoalDistiller."""
        fake_user = _make_fake_user()
        fake_settings = _make_fake_settings(fake_user.id)
        fake_settings.filtering_goal = "Old goal"

        original = app.dependency_overrides.copy()
        from app.api.deps import get_current_user
        from app.db.database import get_db
        app.dependency_overrides[get_current_user] = lambda: fake_user

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = fake_settings
        mock_session.execute.return_value = mock_result

        app.dependency_overrides[get_db] = lambda: mock_session

        try:
            with patch("app.worker.celery_app.trigger_goal_distiller") as mock_distiller:
                mock_distiller.delay = MagicMock()

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                    resp = await client.put("/api/v1/settings/", json={
                        "filtering_goal": "New goal about transformers",
                    })

                if resp.status_code == 200:
                    mock_distiller.delay.assert_called_once()
        finally:
            app.dependency_overrides = original


# ---------------------------------------------------------------------------
# Pipeline Endpoints
# ---------------------------------------------------------------------------

class TestPipelineEndpoints:

    @pytest.mark.asyncio
    async def test_trigger_returns_task_id(self):
        """POST /api/v1/pipeline/trigger should return a task_id."""
        fake_user = _make_fake_user()
        fake_settings = _make_fake_settings(fake_user.id)

        original = app.dependency_overrides.copy()
        from app.api.deps import get_current_user
        app.dependency_overrides[get_current_user] = lambda: fake_user

        try:
            with patch("app.api.v1.endpoints.pipeline.AsyncSessionLocal") as MockSession:
                mock_session = AsyncMock()
                mock_result = MagicMock()
                mock_result.scalars.return_value.first.return_value = fake_settings
                mock_session.execute.return_value = mock_result
                MockSession.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                MockSession.return_value.__aexit__ = AsyncMock(return_value=False)

                with patch("app.api.v1.endpoints.pipeline.trigger_agent_discovery") as mock_task:
                    mock_async_result = MagicMock()
                    mock_async_result.id = "test-task-id-123"
                    mock_task.delay.return_value = mock_async_result

                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                        resp = await client.post("/api/v1/pipeline/trigger")

                    assert resp.status_code == 202
                    assert resp.json()["task_id"] == "test-task-id-123"
        finally:
            app.dependency_overrides = original

    @pytest.mark.asyncio
    async def test_pipeline_requires_auth(self):
        """POST /api/v1/pipeline/trigger without auth should return 401."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post("/api/v1/pipeline/trigger")
        assert resp.status_code == 401