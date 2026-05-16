"""
Non-eager Celery integration: real Redis broker (via testcontainers) + an in-process worker.

Verifies that:
  1. The Redis-backed `_user_pipeline_lock` actually enforces single-flight per user
     against a real broker (not just a MagicMock).
  2. A Celery task chain (trigger_goal_distiller → run_full_pipeline) routes through
     a real broker and is consumed by a worker.

The spec proposed `subprocess.Popen(["celery", "worker", ...])`. That would fork a
fresh interpreter where `unittest.mock.patch` from this test process is invisible,
so the forked worker would try to call real fetch_arxiv_papers / Modal GPU / Postgres
and crash. Instead we use `celery.contrib.testing.worker.start_worker(...)` which
runs the worker in an in-process thread — patches installed by this test ARE visible
to the worker.

Skipped automatically when Docker isn't available (the `@pytest.mark.integration`
marker also gates this file from the default test run; pass `-m integration` to
include).
"""

import os
import subprocess
import time
import uuid
from contextlib import contextmanager
from unittest.mock import patch, AsyncMock, MagicMock
from app.core import config as cfg
from app.worker.celery_app import celery_app
from app.worker.celery_app import _user_pipeline_lock
from app.worker.celery_app import _user_pipeline_lock
from app.worker.celery_app import (
        celery_app,
        trigger_goal_distiller,
        run_full_pipeline,
    )

import pytest

pytestmark = pytest.mark.integration


def _docker_available() -> bool:
    try:
        r = subprocess.run(["docker", "version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


@pytest.fixture(scope="module")
def redis_broker():
    """A real Redis container; yields the redis:// URL string."""
    if not _docker_available():
        pytest.skip("Docker not available — integration tests require testcontainers")
    from testcontainers.redis import RedisContainer
    with RedisContainer("redis:7-alpine") as redis:
        url = f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0"
        os.environ["REDIS_URL"] = url
        yield url


@pytest.fixture
def redirected_settings(redis_broker, monkeypatch):
    """Point app.core.config.settings.REDIS_URL at the testcontainer."""
    
    monkeypatch.setattr(cfg.settings, "REDIS_URL", redis_broker)
    # The celery_app module captured REDIS_URL at import time — push it onto the
    # Celery app too so freshly created tasks/locks pick it up.
    
    monkeypatch.setattr(celery_app.conf, "broker_url", redis_broker)
    monkeypatch.setattr(celery_app.conf, "result_backend", redis_broker)
    return redis_broker


def test_lock_prevents_concurrent_full_runs(redirected_settings):
    """Two simultaneous _user_pipeline_lock acquisitions for the same user — second is denied."""
    

    uid = str(uuid.uuid4())

    lock_a = _user_pipeline_lock(uid)
    assert lock_a.acquire(blocking=False) is True

    lock_b = _user_pipeline_lock(uid)
    assert lock_b.acquire(blocking=False) is False, \
        "Second acquisition for the same user must be denied while the first is held"

    lock_a.release()

    # After release, the same user_id can be acquired again
    lock_c = _user_pipeline_lock(uid)
    assert lock_c.acquire(blocking=False) is True
    lock_c.release()


def test_different_users_get_independent_locks(redirected_settings):
    """The lock is keyed on user_id — two distinct users may run concurrently."""
   

    uid_a = str(uuid.uuid4())
    uid_b = str(uuid.uuid4())

    lock_a = _user_pipeline_lock(uid_a)
    lock_b = _user_pipeline_lock(uid_b)

    assert lock_a.acquire(blocking=False) is True
    assert lock_b.acquire(blocking=False) is True, \
        "Different user_ids must NOT share the same Redis lock"

    lock_a.release()
    lock_b.release()


@contextmanager
def _in_process_worker(celery_app):
    """Start a Celery worker in an in-process thread so that patches in the test process
    are visible to the worker. Yields the running worker, terminates on exit."""
    from celery.contrib.testing.worker import start_worker
    # perform_ping_check=False avoids requiring celery.ping task; pool="solo" runs one task
    # at a time on the main thread of the worker.
    with start_worker(
        celery_app,
        perform_ping_check=False,
        loglevel="error",
        shutdown_timeout=10,
    ) as w:
        yield w


def test_chain_routes_through_real_broker(redirected_settings):
    """trigger_goal_distiller → run_full_pipeline executes against a real broker.

    Heavy I/O surfaces are patched so the worker can complete without DB/Modal/network.
    What we verify is that the chain dispatches, runs, and produces a result back through
    the result backend — i.e. the broker round-trip is real.
    """
  
    # Mock everything _run_pipeline and trigger_goal_distiller actually touch.
    # All targets are the SOURCE modules because both Celery tasks import locally.
    fake_session = AsyncMock()
    fake_session.commit = AsyncMock()
    fake_session.add = MagicMock()
    none_proxy = MagicMock()
    none_proxy.scalars.return_value = MagicMock(first=MagicMock(return_value=None))
    fake_session.execute = AsyncMock(return_value=none_proxy)

    fake_engine = MagicMock()
    fake_engine.dispose = AsyncMock()
    fake_SL = MagicMock()
    fake_SL.return_value.__aenter__ = AsyncMock(return_value=fake_session)
    fake_SL.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("app.worker.celery_app._make_session", return_value=(fake_engine, fake_SL)), \
         patch("app.worker.arxiv_scraper.fetch_arxiv_papers", new=MagicMock(return_value=[])), \
         patch("app.worker.arxiv_scraper.ingest_papers", new=AsyncMock(return_value=None)), \
         patch("app.db.retrieval.perform_hybrid_rrf_search", new=AsyncMock(return_value=[])):

        with _in_process_worker(celery_app):
            uid = str(uuid.uuid4())
            from celery import chain
            result = chain(
                trigger_goal_distiller.si(uid),
                run_full_pipeline.si(uid),
            ).apply_async()

            # The chain should complete (no settings → pipeline aborts early but cleanly).
            # We just verify the round-trip — the result is None or a counts tuple.
            final = result.get(timeout=30)
            assert final is None or isinstance(final, (list, tuple))
