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
    """A real Redis container; yields the redis:// URL string.

    Implementation notes:
      - We use the generic `DockerContainer` + explicit `wait_for_logs` instead
        of `testcontainers.redis.RedisContainer`. RedisContainer internally
        applies an `@wait_container_is_ready` decorator at import time, which
        testcontainers itself has deprecated; importing it emits a
        DeprecationWarning every run. Going through the generic API bypasses
        the deprecated module entirely (no warning) and is the migration path
        the library recommends.
      - Teardown ordering matters: we close Celery's connection pool BEFORE
        the container stops. Otherwise the in-process Celery client (singleton,
        alive for the whole pytest session) notices the broker died and
        triggers its default reconnect-retry loop, spamming the terminal with
        20× `Connection to Redis lost: Retry (N/20)` lines for ~1-2 minutes
        after the tests have already PASSED. The conf overrides disable the
        retry loop; `gc.collect()` forces pending AsyncResult.__del__ to run
        while the broker is alive; `celery_app.close()` releases pool
        connections cleanly.
    """
    if not _docker_available():
        pytest.skip("Docker not available — integration tests require testcontainers")

    from testcontainers.core.container import DockerContainer
    # Newer testcontainers exposes wait strategies under .wait_strategies;
    # older versions under .waiting_utils. Try both, prefer the newer.
    try:
        from testcontainers.core.wait_strategies import LogMessageWaitStrategy
    except ImportError:
        from testcontainers.core.waiting_utils import LogMessageWaitStrategy

    # Disable broker reconnect storms during teardown.
    celery_app.conf.broker_connection_retry = False
    celery_app.conf.broker_connection_retry_on_startup = False
    celery_app.conf.broker_connection_max_retries = 0

    container = (
        DockerContainer("redis:7-alpine")
        .with_exposed_ports(6379)
        .waiting_for(LogMessageWaitStrategy("Ready to accept connections"))
    )
    container.start()
    try:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        url = f"redis://{host}:{port}/0"
        os.environ["REDIS_URL"] = url
        try:
            yield url
        finally:
            # Force any pending AsyncResult.__del__ to run NOW, while the
            # broker is still alive. Without this, the chain-test AsyncResults
            # are garbage-collected at process shutdown — by which time the
            # broker is dead, and their __del__ raises ConnectionRefusedError
            # trying to unsubscribe from the pubsub channel.
            import gc
            gc.collect()
            # Close Celery's connection pool while the broker is still alive,
            # so we don't trigger reconnect attempts when the container stops.
            try:
                celery_app.close()
            except Exception:
                pass
    finally:
        container.stop()


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
    What we verify:
      1. The chain dispatches, both tasks are consumed by the worker, and results
         flow back through the result backend (the broker round-trip is real).
      2. BOTH chain steps actually executed — not just the final one. This catches
         a class of regressions where the first task silently failed or the chain
         linking broke, leaving the second task as a no-op while the test stayed
         green on the loose `final is None or isinstance(...)` check.

    The two-step verification uses Celery's own result tracking — the AsyncResult
    returned from chain().apply_async() corresponds to the last task; its `.parent`
    attribute is the AsyncResult of the previous task. If both .successful() are
    True, both tasks reached completion via the broker.
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

            # 1. Round-trip: the chain should complete. With no settings, the
            # pipeline aborts cleanly — result is None or a counts tuple.
            final = result.get(timeout=30)
            assert final is None or isinstance(final, (list, tuple)), (
                f"Unexpected final result type: {type(final).__name__} = {final!r}"
            )

            # 2. BOTH chain steps executed. result.parent is the AsyncResult of
            # the first task (trigger_goal_distiller); result itself is for the
            # second task (run_full_pipeline). Without these checks, the test
            # would stay green even if the first task silently failed or the
            # chain only had one task.
            assert result.parent is not None, (
                "chain().apply_async() returned an AsyncResult without a parent — "
                "the chain was not built with two linked tasks"
            )

            parent_value = result.parent.get(timeout=5)
            assert result.parent.successful(), (
                f"First chain step (trigger_goal_distiller) did not succeed: "
                f"state={result.parent.state}, value={parent_value!r}"
            )
            assert result.successful(), (
                f"Second chain step (run_full_pipeline) did not succeed: "
                f"state={result.state}, value={final!r}"
            )

            # Defense in depth — explicitly drop the AsyncResults so their
            # __del__ runs (or becomes a no-op) here, while the broker is
            # alive, not at process shutdown when Redis is dead.
            try:
                if result.parent is not None:
                    result.parent.forget()
                result.forget()
            except Exception:
                pass
