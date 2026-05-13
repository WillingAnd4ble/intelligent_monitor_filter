"""
Pipeline-mode regression guards.

These tests guarantee:
  * Light mode never calls Marker or run_deep_reader.
  * Light mode writes papers with status='feed' carrying evaluator_user_explanation
    as agent_explanation (NOT the legacy "Not deep-scanned..." fallback).
  * Full mode flips onboarding_completed=True at the end.
  * K+1..N papers in full mode get user_explanation, NOT the legacy fallback.
  * A second simultaneous trigger is dropped when the Redis lock is held.

The pipeline is exercised by calling `_run_pipeline(...)` directly (not via Celery .delay)
with every external surface mocked. Mock targets patch the SOURCE module because the
symbols are imported INSIDE `_run_pipeline` via local `from X import Y`, so they never
exist at `app.worker.celery_app.<name>` for `patch()` to bind to.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _settings_obj(user_id, *, onboarding_completed: bool, deep_scan_limit: int = 2):
    s = MagicMock()
    s.user_id = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    s.categories = ["cs.AI"]
    s.distilled_criteria = ["Multi-agent systems"]
    s.lexical_query = "multi-agent"
    s.filtering_goal = "find multi-agent papers"
    s.goal_embedding = [0.0] * 768
    s.deep_scan_limit = deep_scan_limit
    s.notification_email = None
    s.onboarding_completed = onboarding_completed
    return s


def _candidate(arxiv_id: str):
    return {
        "id": arxiv_id,
        "title": f"Paper {arxiv_id}",
        "abstract": "Some abstract text for testing.",
        "pdf_url": f"http://arxiv.org/pdf/{arxiv_id}",
        "source_url": f"http://arxiv.org/abs/{arxiv_id}",
    }


def _phase1_accept_state(score: float, user_expl: str):
    return {
        "evaluator_decision": "accept",
        "evaluator_score": score,
        "evaluator_reasonbook": "internal reasoning",
        "evaluator_user_explanation": user_expl,
        "critique_decision": True,
        "critique_reasonbook": "",
    }


def _build_session_mock(settings_obj, *, n_candidates: int = 3):
    """An AsyncMock session whose execute() returns settings, then FM, then None dedup checks, then User."""
    session = AsyncMock()
    session.commit = AsyncMock()
    added = []
    session.add = MagicMock(side_effect=added.append)
    session.flush = AsyncMock()
    session.refresh = AsyncMock()

    settings_proxy = MagicMock()
    settings_scalars = MagicMock()
    settings_scalars.first.return_value = settings_obj
    settings_proxy.scalars.return_value = settings_scalars

    fm_proxy = MagicMock()
    fm_scalars = MagicMock()
    fm_scalars.first.return_value = None
    fm_proxy.scalars.return_value = fm_scalars

    none_proxy = MagicMock()
    none_scalars = MagicMock()
    none_scalars.first.return_value = None
    none_proxy.scalars.return_value = none_scalars

    user_obj = MagicMock()
    user_obj.id = settings_obj.user_id
    user_obj.email = "test@example.com"
    user_proxy = MagicMock()
    user_scalars = MagicMock()
    user_scalars.first.return_value = user_obj
    user_proxy.scalars.return_value = user_scalars

    # 1 settings + 1 FM + n_candidates dedup + 1 user-lookup (full mode only)
    queue = [settings_proxy, fm_proxy] + [none_proxy] * n_candidates + [user_proxy] * 4
    session.execute = AsyncMock(side_effect=queue)
    session._added = added
    return session


@pytest.fixture
def mock_pipeline_deps():
    """Patch every external surface inside `_run_pipeline`. Patches at SOURCE modules."""
    patches = []

    p_fetch = patch("app.worker.arxiv_scraper.fetch_arxiv_papers", new=MagicMock(return_value=[]))
    p_ingest = patch("app.worker.arxiv_scraper.ingest_papers", new=AsyncMock(return_value=None))
    p_window = patch(
        "app.worker.arxiv_scraper.default_daily_window_utc",
        new=MagicMock(return_value=(
            __import__("datetime").datetime(2026, 5, 12, 0, 0, 0, tzinfo=__import__("datetime").timezone.utc),
            __import__("datetime").datetime(2026, 5, 12, 23, 59, 59, tzinfo=__import__("datetime").timezone.utc),
        )),
    )
    p_rrf = patch(
        "app.db.retrieval.perform_hybrid_rrf_search",
        new=AsyncMock(return_value=[_candidate("p1"), _candidate("p2"), _candidate("p3")]),
    )

    phase1_mock = MagicMock()
    phase1_mock.ainvoke = AsyncMock(side_effect=[
        _phase1_accept_state(9.0, "User-facing prose for p1."),
        _phase1_accept_state(8.0, "User-facing prose for p2."),
        _phase1_accept_state(7.0, "User-facing prose for p3."),
    ])
    p_phase1 = patch("app.agents.graph.phase1_graph", new=phase1_mock)

    p_marker = patch(
        "app.worker.modal_client.marker_extract_pdf",
        new=AsyncMock(return_value="# extracted markdown"),
    )
    p_dr = patch(
        "app.agents.graph.run_deep_reader",
        new=AsyncMock(return_value={
            "decision": "accept",
            "score": 9.0,
            "explanation": "Deep Reader prose — thorough analysis.",
        }),
    )
    p_notify = patch("app.worker.notifications.notify_top_picks", new=MagicMock())

    lock_mock = MagicMock()
    fake_lock = MagicMock()
    fake_lock.acquire = MagicMock(return_value=True)
    fake_lock.release = MagicMock()
    lock_mock.return_value = fake_lock
    p_lock = patch("app.worker.celery_app._user_pipeline_lock", new=lock_mock)

    for p in (p_fetch, p_ingest, p_window, p_rrf, p_phase1, p_marker, p_dr, p_notify, p_lock):
        p.start()
        patches.append(p)

    refs = {"phase1": phase1_mock, "lock": lock_mock}
    yield refs

    for p in patches:
        p.stop()


@pytest.fixture
def mock_make_session(monkeypatch):
    """Patches `_make_session` in celery_app to yield a controllable session.

    Returns a factory that the test calls with (settings_obj, n_candidates) to install
    the session mock just-in-time. Returns the bound session so tests can inspect _added.
    """
    state = {}

    def _install(settings_obj, *, n_candidates: int = 3):
        session = _build_session_mock(settings_obj, n_candidates=n_candidates)
        engine = MagicMock()
        engine.dispose = AsyncMock()
        SessionLocal = MagicMock()
        SessionLocal.return_value.__aenter__ = AsyncMock(return_value=session)
        SessionLocal.return_value.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr("app.worker.celery_app._make_session", lambda: (engine, SessionLocal))
        state["session"] = session
        state["settings"] = settings_obj
        return session

    _install.state = state
    return _install


def _drive(mode, user_id):
    """Run _run_pipeline synchronously with a fake Celery self."""
    from app.worker.celery_app import _run_pipeline
    fake_self = MagicMock()
    fake_self.update_state = MagicMock()
    _run_pipeline(fake_self, user_id, mode=mode)


# ===== TESTS ================================================================

class TestLightPipeline:

    def test_light_mode_skips_marker_and_deep_reader(self, mock_pipeline_deps, mock_make_session, eager_celery):
        uid = str(uuid.uuid4())
        settings = _settings_obj(uid, onboarding_completed=True)
        mock_make_session(settings, n_candidates=3)

        from app.worker import modal_client, notifications
        from app.agents import graph as graph_mod
        _drive("light", uid)

        assert not modal_client.marker_extract_pdf.called, "Marker must not run in light mode"
        assert not graph_mod.run_deep_reader.called, "Deep Reader must not run in light mode"
        assert not notifications.notify_top_picks.called, "Notifications must not fire in light mode"

    def test_light_mode_writes_user_explanation_to_feed(self, mock_pipeline_deps, mock_make_session, eager_celery):
        uid = str(uuid.uuid4())
        settings = _settings_obj(uid, onboarding_completed=True)
        session = mock_make_session(settings, n_candidates=3)

        _drive("light", uid)

        feed_rows = [obj for obj in session._added if getattr(obj, "status", None) == "feed"]
        assert len(feed_rows) == 3, f"Expected 3 feed rows in light mode, got {len(feed_rows)}"
        for row in feed_rows:
            assert row.agent_explanation, "Feed row must have non-empty agent_explanation"
            assert "Not deep-scanned" not in row.agent_explanation, \
                "Light-mode feed must NOT contain the legacy 'Not deep-scanned' string"
            assert "User-facing prose" in row.agent_explanation, \
                f"Feed row should carry evaluator_user_explanation; got: {row.agent_explanation!r}"

    def test_light_mode_does_not_flip_onboarding(self, mock_pipeline_deps, mock_make_session, eager_celery):
        uid = str(uuid.uuid4())
        settings = _settings_obj(uid, onboarding_completed=False)
        mock_make_session(settings, n_candidates=3)

        _drive("light", uid)
        assert settings.onboarding_completed is False, "Light mode must NEVER flip onboarding_completed"


class TestFullPipeline:

    def test_full_mode_flips_onboarding_completed(self, mock_pipeline_deps, mock_make_session, eager_celery):
        uid = str(uuid.uuid4())
        settings = _settings_obj(uid, onboarding_completed=False, deep_scan_limit=2)
        mock_make_session(settings, n_candidates=3)

        _drive("full", uid)
        assert settings.onboarding_completed is True, "Full mode must flip onboarding_completed at the end"

    def test_full_mode_kplus1_papers_get_user_explanation_not_legacy_string(
        self, mock_pipeline_deps, mock_make_session, eager_celery,
    ):
        uid = str(uuid.uuid4())
        # deep_scan_limit=2, 3 candidates → top 2 go to Marker+DR, 1 falls into K+1..N branch
        settings = _settings_obj(uid, onboarding_completed=True, deep_scan_limit=2)
        session = mock_make_session(settings, n_candidates=3)

        _drive("full", uid)

        feed_rows = [obj for obj in session._added if getattr(obj, "status", None) == "feed"]
        # K+1..N rows are the ones whose explanation is the evaluator prose, NOT Deep Reader prose
        kplus_rows = [r for r in feed_rows if r.agent_explanation and "Deep Reader prose" not in r.agent_explanation]
        assert kplus_rows, "Expected at least one K+1..N paper written to feed with evaluator prose"
        for r in kplus_rows:
            assert "Not deep-scanned" not in (r.agent_explanation or ""), \
                f"K+1..N row must use evaluator_user_explanation, not the legacy fallback. Got: {r.agent_explanation!r}"
            assert "User-facing prose" in r.agent_explanation, \
                f"K+1..N row should carry the evaluator's user_explanation; got: {r.agent_explanation!r}"


class TestSingleFlightLock:

    def test_second_call_drops_silently_when_lock_held(self, mock_pipeline_deps, mock_make_session, eager_celery):
        # Reconfigure the lock to refuse acquisition
        refused_lock = MagicMock()
        refused_lock.acquire = MagicMock(return_value=False)
        refused_lock.release = MagicMock()
        mock_pipeline_deps["lock"].return_value = refused_lock

        uid = str(uuid.uuid4())
        settings = _settings_obj(uid, onboarding_completed=True)
        mock_make_session(settings, n_candidates=3)

        from app.db import retrieval
        from app.agents import graph as graph_mod
        _drive("full", uid)

        assert not retrieval.perform_hybrid_rrf_search.called, \
            "Locked-out run must short-circuit BEFORE the RRF query"
        assert not graph_mod.run_deep_reader.called, "Locked-out run must not reach Deep Reader"
