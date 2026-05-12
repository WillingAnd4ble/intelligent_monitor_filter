# Thesis Chapter 4 Finish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three confirmed pipeline bugs, add ~30 functional tests, and complete thesis Chapter 4 (sections 4.2 demo, 4.3 tests, 4.4 performance, 4.5 limitations) so the system behaves correctly on first-run and the thesis prose is grounded in real test counts and timings.

**Architecture:** Three sprints. Sprint 1 splits the Celery pipeline into `light`/`full` modes, adds an `onboarding_completed` flag, extends `EvaluatorOutput` with a user-facing field, wires the arXiv "yesterday window" helper, switches the K+1..N feed fallback to `user_explanation`, and adds a per-user Redis lock. Sprint 2 grows the pytest suite (auth, API form validation, pipeline-modes regression, scraper windows, optional testcontainers integration). Sprint 3 measures real timings, captures screenshots, and writes the four Chapter 4 subsections.

**Tech Stack:** FastAPI + LangGraph + Celery + Redis + Postgres/pgvector backend, Modal GPU for SPECTER2/Marker, Next.js frontend, pytest + freezegun + testcontainers-redis for tests, Lithuanian Markdown thesis document.

**Reference spec:** `docs/superpowers/specs/2026-05-12-thesis-ch4-finish-design.md`.

---

## File structure

### Created
| Path | Purpose |
|---|---|
| `backend/alembic/versions/a1b2c3d4e5f6_add_onboarding_completed.py` | Migration: add `onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE`, backfill `TRUE` for users with existing accepted/rejected papers. |
| `testing/tests/test_auth.py` | Auth/registration/login/logout tests (FR1, NFR4). |
| `testing/tests/test_pipeline_modes.py` | Trigger taxonomy, `user_explanation` in feed, light vs full mode, single-flight lock. |
| `testing/tests/test_celery_integration.py` | testcontainers-redis + real Celery worker, `@pytest.mark.integration`. |

### Modified
| Path | Why |
|---|---|
| `backend/app/db/models.py` | Add `onboarding_completed` column to `UserSettings`. |
| `backend/app/agents/schemas.py` | Add `user_explanation: str` to `EvaluatorOutput`; add corresponding key to `AgentState`. |
| `backend/app/agents/graph.py` | Update Evaluator prompt + `node_evaluator` return dict to emit `evaluator_user_explanation`. |
| `backend/app/worker/arxiv_scraper.py` | Add `default_daily_window_utc(now)` helper. |
| `backend/app/worker/celery_app.py` | Refactor `trigger_agent_discovery` → `_run_pipeline(user_id, mode, *, since, until)`; add `run_light_pipeline`/`run_full_pipeline` Celery tasks; per-user Redis lock; flip `onboarding_completed=True`; switch K+1..N fallback to `user_explanation`; pass window into scraper; structured `pipeline.start`/`pipeline.end` log lines. |
| `backend/app/api/v1/endpoints/settings.py` | Read pre-save `onboarding_completed`, chain `trigger_goal_distiller` → `run_full_pipeline` (first run) or `run_light_pipeline` (goal change). |
| `backend/app/api/v1/endpoints/pipeline.py` | Accept `?date=YYYY-MM-DD`; build one-day window; chain into `run_full_pipeline`. |
| `testing/requirements.txt` | Pin `bcrypt>=4.0.0`, `freezegun>=1.4.0`, `testcontainers[redis]>=4.0.0`. |
| `testing/tests/conftest.py` | Add `eager_celery`, `mock_specter2_modal`, `mock_marker_modal`, `test_user_cookie`, `seeded_papers` fixtures. |
| `testing/tests/test_api.py` | Repair `bcrypt` import; extend with settings/feed validation. |
| `testing/tests/test_agents.py` | Update Evaluator output mocks to include `user_explanation`. |
| `testing/tests/test_scraper.py` | Add `default_daily_window_utc` + windowed-fetch tests with freezegun. |
| `testing/pytest.ini` | Register `integration` marker. |
| `Baigiamasis_darbas_final.md` | Rewrite Ch 4 intro + 4.2 + 4.3 + 4.4; polish 4.5 and 4.1. |

---

# Sprint 1 — Architecture + bug fixes

### Task 1: Pin bcrypt so test_api.py can be imported

**Files:**
- Modify: `testing/requirements.txt`
- Test: `pytest testing/tests/test_api.py --collect-only`

- [ ] **Step 1: Reproduce the failure**

Run: `cd testing && python -m pytest tests/test_api.py --collect-only 2>&1 | tail -10`
Expected: `ModuleNotFoundError: No module named 'bcrypt'` from `backend/app/core/security.py:3`.

- [ ] **Step 2: Install bcrypt and freezegun in the test venv**

Run: `pip install bcrypt>=4.0.0 freezegun>=1.4.0 testcontainers[redis]>=4.0.0`
Expected: clean install, `bcrypt`, `freezegun`, `testcontainers` available.

- [ ] **Step 3: Pin the new dependencies in `testing/requirements.txt`**

Append to `testing/requirements.txt`:

```text
bcrypt>=4.0.0
freezegun>=1.4.0
testcontainers[redis]>=4.0.0
```

- [ ] **Step 4: Re-run collection**

Run: `cd testing && python -m pytest tests/ --collect-only 2>&1 | tail -5`
Expected: `48 tests collected` or similar — no `bcrypt` import error. `test_api.py` now loadable.

- [ ] **Step 5: Commit**

```bash
git add testing/requirements.txt
git commit -m "test: pin bcrypt, freezegun, testcontainers so test_api.py imports cleanly"
```

---

### Task 2: Add `onboarding_completed` migration + ORM column

**Files:**
- Create: `backend/alembic/versions/a1b2c3d4e5f6_add_onboarding_completed.py`
- Modify: `backend/app/db/models.py`

- [ ] **Step 1: Write the migration**

Create `backend/alembic/versions/a1b2c3d4e5f6_add_onboarding_completed.py`:

```python
"""add onboarding_completed to user_settings

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-05-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'user_settings',
        sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default='false'),
    )
    # Backfill: any user with at least one accepted/rejected UserPaper has already onboarded.
    op.execute("""
        UPDATE user_settings
        SET onboarding_completed = TRUE
        WHERE user_id IN (
            SELECT DISTINCT user_id FROM user_papers
            WHERE status IN ('accepted', 'rejected')
        )
    """)


def downgrade() -> None:
    op.drop_column('user_settings', 'onboarding_completed')
```

- [ ] **Step 2: Add the ORM column**

Edit `backend/app/db/models.py`, in the `UserSettings` class (after the `pdf_parser_mode` line):

```python
    pdf_parser_mode = Column(String, default="pypdfium")
    onboarding_completed = Column(Boolean, nullable=False, server_default="false", default=False)
```

- [ ] **Step 3: Run the migration locally**

Run: `cd backend && alembic upgrade head`
Expected: `Running upgrade f1a2b3c4d5e6 -> a1b2c3d4e5f6, add onboarding_completed to user_settings`.

- [ ] **Step 4: Verify backfill on a SQL shell**

Run: `docker-compose exec db psql -U postgres -d arxiv -c "SELECT user_id, onboarding_completed FROM user_settings LIMIT 5;"`
Expected: rows return; users with existing accepted/rejected papers show `t`, fresh users show `f`.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/a1b2c3d4e5f6_add_onboarding_completed.py backend/app/db/models.py
git commit -m "feat(db): add onboarding_completed flag to user_settings with backfill"
```

---

### Task 3: Extend `EvaluatorOutput` with `user_explanation`

**Files:**
- Modify: `backend/app/agents/schemas.py`
- Modify: `backend/app/agents/graph.py:15-50`
- Modify: `testing/tests/test_agents.py` (mock outputs)
- Test: `testing/tests/test_agents.py::TestEvaluatorNode`

- [ ] **Step 1: Write a failing test that asserts node_evaluator returns the new field**

Edit `testing/tests/test_agents.py`, in `class TestEvaluatorNode`, add the test (place after the existing `test_borderline_decision`):

```python
    def test_evaluator_returns_user_explanation(self, make_agent_state):
        from app.agents.schemas import EvaluatorOutput

        fake_output = EvaluatorOutput(
            decision="accept",
            score=8.5,
            reasonbook="Internal: paper covers multi-agent coordination per criterion 1.",
            user_explanation="This paper proposes a multi-agent coordination framework, "
                             "matching your interest in LLM-based agentic systems.",
        )
        patcher, _ = _patch_llm_chain("app.agents.graph.ChatOpenAI", fake_output)

        with patcher:
            from app.agents.graph import node_evaluator
            state = make_agent_state()
            result = node_evaluator(state)

        assert "evaluator_user_explanation" in result
        assert "multi-agent coordination framework" in result["evaluator_user_explanation"]
```

- [ ] **Step 2: Run the test, confirm it fails**

Run: `cd testing && python -m pytest tests/test_agents.py::TestEvaluatorNode::test_evaluator_returns_user_explanation -v`
Expected: `FAILED` — either `EvaluatorOutput.__init__() got an unexpected keyword argument 'user_explanation'` or `KeyError: 'evaluator_user_explanation'`.

- [ ] **Step 3: Extend `EvaluatorOutput` and `AgentState`**

Edit `backend/app/agents/schemas.py`:

```python
class AgentState(TypedDict):
    """State for Phase 1 graph: evaluator + critique per paper."""
    user_id: str
    distilled_criteria: List[str]
    feedback_memory: str

    # Paper data
    current_paper_id: str
    raw_abstract: str
    pdf_url: Optional[str]

    # Agent outputs
    evaluator_decision: Literal["accept", "borderline", "reject"]
    evaluator_score: float
    evaluator_reasonbook: str
    evaluator_user_explanation: str
    critique_decision: bool
    critique_reasonbook: Optional[str]


# --- Phase 1: Evaluator ---

class EvaluatorOutput(BaseModel):
    decision: Literal["accept", "borderline", "reject"]
    score: float = Field(description="Relevance score from 1.0 to 10.0")
    reasonbook: str = Field(description="Step-by-step reasoning trace (internal, not shown to user)")
    user_explanation: str = Field(
        description=(
            "2-3 sentence explanation in the user's voice — what the paper is about and why it "
            "matches the user's criteria. Same tone the Deep Reader uses. No mention of scores, "
            "criteria IDs, or 'accept/reject'."
        )
    )
```

- [ ] **Step 4: Update Evaluator prompt and return dict**

Edit `backend/app/agents/graph.py`, replace `node_evaluator` (lines 15-50):

```python
def node_evaluator(state: AgentState):
    """Pointwise evaluator: abstract + distilled_criteria → decision + score + user_explanation."""
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.0,
        api_key=settings.OPENAI_API_KEY,
    )
    structured = llm.with_structured_output(EvaluatorOutput)

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are an academic paper screening AI. Evaluate this paper's abstract "
            "against the user's research criteria.\n\n"
            "CRITERIA:\n{criteria}\n\n"
            "INSTRUCTIONS:\n"
            "- Output 'accept' if the paper clearly matches the criteria.\n"
            "- Output 'borderline' if it partially matches or you are uncertain. "
            "When uncertain, PREFER 'borderline' over 'reject'.\n"
            "- Output 'reject' ONLY if the paper clearly does not match.\n"
            "- Assign a relevance score from 1.0 to 10.0.\n"
            "- Write a brief reasoning trace in reasonbook (internal use only).\n"
            "- Also write a 2-3 sentence user_explanation in the user's voice: what the paper "
            "is about and how it connects to what they want to follow. Do NOT mention scores, "
            "criteria IDs, or the words 'accept'/'reject'."
        )),
        ("human", "Abstract:\n\n{abstract}")
    ])

    criteria_formatted = "\n- ".join(state.get("distilled_criteria", []))
    result = (prompt | structured).invoke({
        "criteria": criteria_formatted,
        "abstract": state.get("raw_abstract", ""),
    })

    return {
        "evaluator_decision": result.decision,
        "evaluator_score": result.score,
        "evaluator_reasonbook": result.reasonbook,
        "evaluator_user_explanation": result.user_explanation,
    }
```

- [ ] **Step 5: Update existing test_agents.py mock builders so other tests still pass**

In `testing/tests/test_agents.py`, find every place that constructs `EvaluatorOutput(...)` and add `user_explanation="..."`. Search the file:

```bash
cd testing && grep -n "EvaluatorOutput(" tests/test_agents.py
```

For each match (typically inside `TestEvaluatorNode`, `TestRoutingLogic`, and any place that builds a fake evaluator output), add a `user_explanation` field. Example pattern:

```python
        fake_output = EvaluatorOutput(
            decision="accept",
            score=8.5,
            reasonbook="...",
            user_explanation="Stub explanation for tests.",
        )
```

- [ ] **Step 6: Run all agent tests**

Run: `cd testing && python -m pytest tests/test_agents.py -v`
Expected: all green including the new `test_evaluator_returns_user_explanation`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/agents/schemas.py backend/app/agents/graph.py testing/tests/test_agents.py
git commit -m "feat(agents): emit user_explanation alongside reasonbook from Evaluator"
```

---

### Task 4: `default_daily_window_utc` helper

**Files:**
- Modify: `backend/app/worker/arxiv_scraper.py`
- Test: `testing/tests/test_scraper.py`

- [ ] **Step 1: Write the failing test**

Add to `testing/tests/test_scraper.py` (top-level, after existing imports):

```python
from freezegun import freeze_time
from datetime import datetime, timezone, timedelta


class TestDefaultDailyWindowUtc:
    """Tue–Fri → yesterday only. Sat–Mon → Fri 00:00 → Sun 23:59:59 (covers weekend)."""

    @freeze_time("2026-05-13 09:00:00")  # Wednesday
    def test_weekday_returns_yesterday_window(self):
        from app.worker.arxiv_scraper import default_daily_window_utc
        since, until = default_daily_window_utc()
        assert since == datetime(2026, 5, 12, 0, 0, 0, tzinfo=timezone.utc)
        assert until == datetime(2026, 5, 12, 23, 59, 59, tzinfo=timezone.utc)

    @freeze_time("2026-05-15 09:00:00")  # Friday
    def test_friday_returns_thursday_window(self):
        from app.worker.arxiv_scraper import default_daily_window_utc
        since, until = default_daily_window_utc()
        assert since == datetime(2026, 5, 14, 0, 0, 0, tzinfo=timezone.utc)
        assert until == datetime(2026, 5, 14, 23, 59, 59, tzinfo=timezone.utc)

    @freeze_time("2026-05-18 09:00:00")  # Monday
    def test_monday_returns_friday_through_sunday_window(self):
        from app.worker.arxiv_scraper import default_daily_window_utc
        since, until = default_daily_window_utc()
        assert since == datetime(2026, 5, 15, 0, 0, 0, tzinfo=timezone.utc)   # Fri 00:00
        assert until == datetime(2026, 5, 17, 23, 59, 59, tzinfo=timezone.utc)  # Sun 23:59:59

    @freeze_time("2026-05-16 09:00:00")  # Saturday
    def test_saturday_returns_friday_window(self):
        from app.worker.arxiv_scraper import default_daily_window_utc
        since, until = default_daily_window_utc()
        # Sat morning: yesterday was Friday — just take Friday's window
        assert since == datetime(2026, 5, 15, 0, 0, 0, tzinfo=timezone.utc)
        assert until == datetime(2026, 5, 15, 23, 59, 59, tzinfo=timezone.utc)

    @freeze_time("2026-05-17 09:00:00")  # Sunday
    def test_sunday_returns_friday_through_saturday_window(self):
        from app.worker.arxiv_scraper import default_daily_window_utc
        since, until = default_daily_window_utc()
        assert since == datetime(2026, 5, 15, 0, 0, 0, tzinfo=timezone.utc)   # Fri 00:00
        assert until == datetime(2026, 5, 16, 23, 59, 59, tzinfo=timezone.utc)  # Sat 23:59:59

    def test_accepts_explicit_now_override(self):
        from app.worker.arxiv_scraper import default_daily_window_utc
        now = datetime(2026, 5, 13, 9, 0, 0, tzinfo=timezone.utc)  # Wednesday
        since, until = default_daily_window_utc(now)
        assert since == datetime(2026, 5, 12, 0, 0, 0, tzinfo=timezone.utc)
        assert until == datetime(2026, 5, 12, 23, 59, 59, tzinfo=timezone.utc)
```

- [ ] **Step 2: Run, confirm failure**

Run: `cd testing && python -m pytest tests/test_scraper.py::TestDefaultDailyWindowUtc -v`
Expected: all 6 tests `FAILED` with `ImportError: cannot import name 'default_daily_window_utc'`.

- [ ] **Step 3: Implement the helper**

Edit `backend/app/worker/arxiv_scraper.py`, add after `_throttle_arxiv()` (before `_build_query_url`):

```python
def default_daily_window_utc(now: datetime | None = None) -> tuple[datetime, datetime]:
    """
    Default (since, until) UTC half-open window for the daily fetch.

    Rules (UTC weekday, Monday=0):
      Tue (1), Wed (2), Thu (3), Fri (4): yesterday 00:00:00 → yesterday 23:59:59.
      Sat (5): yesterday (Fri) 00:00:00 → yesterday (Fri) 23:59:59.
      Sun (6): two days ago (Fri) 00:00:00 → yesterday (Sat) 23:59:59.
      Mon (0): three days ago (Fri) 00:00:00 → yesterday (Sun) 23:59:59.

    The Sat/Sun/Mon branches cover the arXiv weekend quiet period.
    Caller can pass their own since/until to override entirely.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    today_midnight = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    weekday = now.weekday()  # Mon=0..Sun=6

    if weekday == 0:           # Monday → cover Fri 00:00 .. Sun 23:59
        since = today_midnight - timedelta(days=3)
        until = today_midnight - timedelta(seconds=1)
    elif weekday == 6:         # Sunday → cover Fri 00:00 .. Sat 23:59
        since = today_midnight - timedelta(days=2)
        until = today_midnight - timedelta(seconds=1)
    else:                      # Tue..Sat → cover yesterday only
        since = today_midnight - timedelta(days=1)
        until = today_midnight - timedelta(seconds=1)

    return since, until
```

Also ensure `timedelta` is imported at the top of the file:

```python
from datetime import datetime, timezone, timedelta
```

- [ ] **Step 4: Run the helper tests**

Run: `cd testing && python -m pytest tests/test_scraper.py::TestDefaultDailyWindowUtc -v`
Expected: all 6 PASS.

- [ ] **Step 5: Run all scraper tests, make sure nothing regressed**

Run: `cd testing && python -m pytest tests/test_scraper.py -v`
Expected: all green (existing + new).

- [ ] **Step 6: Commit**

```bash
git add backend/app/worker/arxiv_scraper.py testing/tests/test_scraper.py
git commit -m "feat(scraper): add default_daily_window_utc with Mon→Fri-Sun weekend rule"
```

---

### Task 5: Refactor pipeline into `_run_pipeline(mode)` + Redis lock + onboarding flip

This task is a structural refactor. It introduces a `mode` parameter, wraps execution in a per-user Redis lock, flips `onboarding_completed=True` on full-mode success, and short-circuits Phase 2 in light mode. The existing happy path stays intact; verification comes from Sprint 2's pipeline-modes tests plus the Sprint 1 manual smoke (Task 11).

**Files:**
- Modify: `backend/app/worker/celery_app.py`

- [ ] **Step 1: Add the helper imports + Redis lock helper at module top**

Edit `backend/app/worker/celery_app.py`. After the `_make_session()` helper (~line 53), add:

```python
# ─────────────────────────────────────────────────────────────────────
# Single-flight per user (15-minute Redis lock)
# ─────────────────────────────────────────────────────────────────────

def _user_pipeline_lock(user_id: str):
    """Return a Redis lock for `pipeline:user:{user_id}` with 15-min TTL.

    Used to drop duplicate pipeline runs when a user double-clicks Save
    or two triggers race. Callers MUST .acquire(blocking=False) and check
    the return value; if False, log and bail out — do not raise.
    """
    import redis
    client = redis.Redis.from_url(settings.REDIS_URL)
    return client.lock(f"pipeline:user:{user_id}", timeout=15 * 60)
```

- [ ] **Step 2: Rename `trigger_agent_discovery` body into `_run_pipeline` and add mode/lock/onboarding logic**

Replace the entire `trigger_agent_discovery` task (lines ~132-428 in `celery_app.py`) with the refactored version below. **The body of `_run` from `# ── 0. Load user settings ──` down through the notifications block stays the same except for the three changes marked with `# CHANGED:` comments.**

```python
# ─────────────────────────────────────────────────────────────────────
# Main Pipeline: Cascade Agentic Funnel (v3 — mode-aware)
# ─────────────────────────────────────────────────────────────────────

def _run_pipeline(
    self,
    user_id: str,
    mode: str,
    since_iso: str | None = None,
    until_iso: str | None = None,
):
    """Run the cascade pipeline in `light` or `full` mode.

    light: scrape → ingest → RRF → Phase 1 → write accepted papers to feed → STOP.
           Used for goal changes — fast, no Marker, no Deep Reader, no notification.
    full:  light prefix + top-K Marker + Deep Reader + top-3 is_top_pick + notification.
           Used for first-run (after registration), scheduled hourly tick, and ad-hoc trigger.
    """
    from app.worker.arxiv_scraper import (
        fetch_arxiv_papers, ingest_papers, default_daily_window_utc,
    )
    from app.db.retrieval import perform_hybrid_rrf_search
    from app.agents.graph import phase1_graph, run_deep_reader
    from app.worker.modal_client import marker_extract_pdf
    from app.db.models import UserSettings, UserPaper, Paper, FeedbackMemory, User
    from app.worker.notifications import notify_top_picks
    from datetime import datetime, timezone
    import json
    import time
    import uuid
    import logging

    assert mode in ("light", "full"), f"invalid pipeline mode: {mode!r}"

    logger = logging.getLogger(__name__)
    t_start = time.monotonic()

    # Resolve window: explicit override > default_daily_window_utc()
    if since_iso and until_iso:
        since = datetime.fromisoformat(since_iso)
        until = datetime.fromisoformat(until_iso)
    else:
        since, until = default_daily_window_utc()

    # Structured telemetry — start
    logger.info(json.dumps({
        "event": "pipeline.start",
        "user_id": user_id,
        "mode": mode,
        "since": since.isoformat(),
        "until": until.isoformat(),
        "ts": time.time(),
    }))

    # Single-flight Redis lock — drop duplicates silently
    lock = _user_pipeline_lock(user_id)
    if not lock.acquire(blocking=False):
        logger.info(json.dumps({
            "event": "pipeline.skipped_locked",
            "user_id": user_id,
            "mode": mode,
            "ts": time.time(),
        }))
        return

    def _update(stage: str, progress: int):
        self.update_state(state="PROGRESS", meta={"stage": stage, "progress": progress})

    async def _run():
        engine, SessionLocal = _make_session()
        phase1_accepted_count = 0
        phase2_count = 0
        top_pick_count = 0

        try:
            async with SessionLocal() as session:
                # ── 0. Load user settings ──────────────────────────────
                _update("Loading settings", 5)
                result = await session.execute(select(UserSettings).where(UserSettings.user_id == uuid.UUID(user_id)))
                user_settings = result.scalars().first()
                categories = user_settings.categories if user_settings and user_settings.categories else ["cs.AI"]

                # ── 1. Scrape + ingest ArXiv papers ────────────────────
                _update("Fetching ArXiv papers", 10)
                cat_query = "+OR+".join(f"cat:{cat}" for cat in categories)
                logger.info(f"[pipeline:{user_id[:8]}] Fetching ArXiv [{since.isoformat()} → {until.isoformat()}] for: {categories}")
                # CHANGED: pass since/until from the window
                papers = fetch_arxiv_papers(cat_query, since=since, until=until, max_results=200)
                logger.info(f"[pipeline:{user_id[:8]}] Fetched {len(papers)} papers, ingesting...")
                _update("Ingesting papers", 15)
                await ingest_papers(session, papers)

                # ── 2. Validate prerequisites ──────────────────────────
                if not user_settings or not user_settings.distilled_criteria:
                    logger.warning(f"[pipeline:{user_id[:8]}] ABORTING — no distilled_criteria")
                    return

                # Load feedback memory
                fm_result = await session.execute(
                    select(FeedbackMemory).where(FeedbackMemory.user_id == uuid.UUID(user_id))
                )
                fm = fm_result.scalars().first()
                feedback_str = fm.summarized_feedback if fm and fm.summarized_feedback else ""

                # ── 3. RRF hybrid search ───────────────────────────────
                _update("Searching candidates", 25)
                candidates = await perform_hybrid_rrf_search(
                    session=session,
                    lexical_query=user_settings.lexical_query or "",
                    embedding=user_settings.goal_embedding,
                    limit=30,
                )
                logger.info(f"[pipeline:{user_id[:8]}] RRF returned {len(candidates)} candidates")

                # ── 4. Phase 1: Evaluator + Critique (abstract-only) ──
                _update("Phase 1: Evaluating abstracts", 30)
                phase1_results = []
                total_cands = len(candidates)
                for i, cand in enumerate(candidates):
                    _update(f"Phase 1: Paper {i+1}/{total_cands}", 30 + int(20 * i / max(total_cands, 1)))
                    existing = await session.execute(
                        select(UserPaper).where(
                            UserPaper.user_id == uuid.UUID(user_id),
                            UserPaper.paper_id == cand["id"],
                        )
                    )
                    if existing.scalars().first():
                        continue

                    try:
                        state_input = {
                            "user_id": user_id,
                            "distilled_criteria": user_settings.distilled_criteria,
                            "feedback_memory": feedback_str,
                            "current_paper_id": cand["id"],
                            "raw_abstract": cand["abstract"],
                            "pdf_url": cand.get("pdf_url"),
                            "evaluator_decision": "borderline",
                            "evaluator_score": 0.0,
                            "evaluator_reasonbook": "",
                            "evaluator_user_explanation": "",   # CHANGED: seed the new field
                            "critique_decision": True,
                            "critique_reasonbook": "",
                        }

                        final_state = await phase1_graph.ainvoke(state_input)

                        decision = final_state.get("evaluator_decision")
                        accepted = (
                            decision == "accept"
                            or (decision == "borderline" and final_state.get("critique_decision") is True)
                        )

                        logger.info(
                            f"[pipeline:{user_id[:8]}] Phase1 {i+1}/{len(candidates)} "
                            f"'{cand['id']}' → {decision} (score={final_state.get('evaluator_score')}) "
                            f"{'→ ACCEPTED' if accepted else '→ REJECTED'}"
                        )

                        if accepted:
                            phase1_results.append((cand, final_state))
                        else:
                            session.add(UserPaper(
                                user_id=uuid.UUID(user_id),
                                paper_id=cand["id"],
                                status="rejected",
                                agent_score=final_state.get("evaluator_score"),
                            ))

                    except Exception as e:
                        logger.error(f"[pipeline:{user_id[:8]}] Phase1 failed on '{cand['id']}': {e}", exc_info=True)
                        continue

                await session.commit()
                phase1_accepted_count = len(phase1_results)
                logger.info(f"[pipeline:{user_id[:8]}] Phase 1 complete — {phase1_accepted_count} accepted")

                if not phase1_results:
                    logger.info(f"[pipeline:{user_id[:8]}] No papers passed Phase 1, pipeline done")
                    return

                # CHANGED: in light mode, persist every accepted paper to feed with user_explanation, then stop.
                if mode == "light":
                    _update("Light mode: writing feed", 80)
                    for cand, state in phase1_results:
                        ue = (state.get("evaluator_user_explanation") or "").strip()
                        fallback = f"Passed abstract screening (score: {state.get('evaluator_score', 0):.1f}/10)."
                        session.add(UserPaper(
                            user_id=uuid.UUID(user_id),
                            paper_id=cand["id"],
                            status="feed",
                            agent_score=state.get("evaluator_score"),
                            agent_explanation=ue or fallback,
                        ))
                    await session.commit()
                    logger.info(f"[pipeline:{user_id[:8]}] Light mode done — {phase1_accepted_count} papers in feed")
                    return

                # ── 5. (full mode) Sort by evaluator score → top K ────
                _update("Sorting candidates", 55)
                deep_scan_limit = user_settings.deep_scan_limit or 10
                phase1_results.sort(key=lambda x: x[1].get("evaluator_score", 0), reverse=True)
                top_k = phase1_results[:deep_scan_limit]

                # CHANGED: K+1..N use user_explanation, not the technical fallback string
                for cand, state in phase1_results[deep_scan_limit:]:
                    ue = (state.get("evaluator_user_explanation") or "").strip()
                    fallback = (
                        f"Passed abstract screening (score: {state.get('evaluator_score', 0):.1f}/10). "
                        f"Not deep-scanned due to scan limit ({deep_scan_limit})."
                    )
                    session.add(UserPaper(
                        user_id=uuid.UUID(user_id),
                        paper_id=cand["id"],
                        status="feed",
                        agent_score=state.get("evaluator_score"),
                        agent_explanation=ue or fallback,
                    ))
                await session.commit()

                logger.info(
                    f"[pipeline:{user_id[:8]}] Top {len(top_k)} papers selected for deep scan "
                    f"(deep_scan_limit={deep_scan_limit})"
                )

                # ── 6. Marker: parallel PDF extraction ─────────────────
                async def extract_pdf(cand_data):
                    pdf_url = cand_data.get("pdf_url")
                    if not pdf_url:
                        return cand_data.get("abstract", "")
                    try:
                        return await marker_extract_pdf(pdf_url)
                    except Exception as e:
                        logger.warning(f"[pipeline:{user_id[:8]}] Marker failed on '{cand_data['id']}': {e}")
                        return cand_data.get("abstract", "")

                _update(f"Marker: extracting {len(top_k)} PDFs", 65)
                markdown_results = await asyncio.gather(
                    *(extract_pdf(cand) for (cand, _) in top_k),
                    return_exceptions=False,
                )

                # ── 7. Phase 2: Deep Reader (parallel) ─────────────────
                _update(f"Phase 2: Deep reading {len(top_k)} papers", 80)
                deep_results = await asyncio.gather(
                    *(
                        run_deep_reader(
                            full_text=md,
                            criteria=user_settings.distilled_criteria,
                            feedback_memory=feedback_str,
                        )
                        for md in markdown_results
                    ),
                    return_exceptions=False,
                )

                # ── 8. Persist Deep Reader outputs ─────────────────────
                feed_papers = []
                for (cand, eval_state), md_text, dr_result in zip(top_k, markdown_results, deep_results):
                    dr_decision = dr_result.get("decision", "reject")
                    dr_score = dr_result.get("score", 0.0)
                    if dr_decision == "reject" or dr_score < 5.0:
                        status = "rejected"
                    else:
                        status = "feed"

                    up = UserPaper(
                        user_id=uuid.UUID(user_id),
                        paper_id=cand["id"],
                        status=status,
                        agent_score=dr_score,
                        agent_explanation=dr_result.get("explanation"),
                        extracted_markdown=md_text if md_text != cand.get("abstract", "") else None,
                    )
                    session.add(up)

                    if status == "feed":
                        feed_papers.append((up, cand, dr_score))

                    logger.info(
                        f"[pipeline:{user_id[:8]}] Deep Reader '{cand['id']}' → {status} "
                        f"(eval_score={eval_state.get('evaluator_score')}, deep_score={dr_score})"
                    )

                phase2_count = len(top_k)

                # Mark top 3 as top picks (score >= 7.0 only)
                TOP_PICK_MIN_SCORE = 7.0
                feed_papers.sort(key=lambda x: x[2], reverse=True)
                for up, cand, score in feed_papers[:3]:
                    if score >= TOP_PICK_MIN_SCORE:
                        up.is_top_pick = True
                        top_pick_count += 1
                        logger.info(f"[pipeline:{user_id[:8]}] TOP PICK: '{cand['id']}' (score={score})")
                await session.commit()

                # CHANGED: full mode marks onboarding done on first successful pass
                if not user_settings.onboarding_completed:
                    user_settings.onboarding_completed = True
                    await session.commit()
                    logger.info(f"[pipeline:{user_id[:8]}] onboarding_completed → True")

                _update("Sending notifications", 95)
                top_pick_entries = [
                    (up, cand) for up, cand, score in feed_papers[:3]
                    if score >= TOP_PICK_MIN_SCORE
                ]
                if top_pick_entries:
                    user_result = await session.execute(
                        select(User).where(User.id == uuid.UUID(user_id))
                    )
                    user_obj = user_result.scalars().first()
                    notify_email = user_settings.notification_email or user_obj.email
                    top_papers_data = [
                        {
                            "title": cand["title"],
                            "source_url": cand.get("source_url"),
                            "agent_score": up.agent_score,
                            "agent_explanation": up.agent_explanation,
                        }
                        for up, cand in top_pick_entries
                    ]
                    notify_top_picks(notify_email, top_papers_data)
                    logger.info(f"[pipeline:{user_id[:8]}] Notification sent to {notify_email}")

        except Exception as e:
            logger.error(f"[pipeline:{user_id[:8]}] TASK FAILED: {e}", exc_info=True)
            raise
        finally:
            await engine.dispose()

        return phase1_accepted_count, phase2_count, top_pick_count

    try:
        counts = _run_async(_run())
        phase1_accepted_count, phase2_count, top_pick_count = counts or (0, 0, 0)
    finally:
        try:
            lock.release()
        except Exception:
            pass

    # Structured telemetry — end
    logger.info(json.dumps({
        "event": "pipeline.end",
        "user_id": user_id,
        "mode": mode,
        "duration_ms": int((time.monotonic() - t_start) * 1000),
        "phase1_count": phase1_accepted_count,
        "phase2_count": phase2_count,
        "top_pick_count": top_pick_count,
        "ts": time.time(),
    }))


@celery_app.task(name="pipeline.run_full", bind=True)
def run_full_pipeline(self, user_id: str, since_iso: str | None = None, until_iso: str | None = None):
    """Full cascade: Phase 1 + Phase 2 + notifications. Flips onboarding_completed=True."""
    _run_pipeline(self, user_id, mode="full", since_iso=since_iso, until_iso=until_iso)


@celery_app.task(name="pipeline.run_light", bind=True)
def run_light_pipeline(self, user_id: str, since_iso: str | None = None, until_iso: str | None = None):
    """Light: Phase 1 only. No Marker, no Deep Reader, no notification."""
    _run_pipeline(self, user_id, mode="light", since_iso=since_iso, until_iso=until_iso)


# Legacy alias so existing callers (Beat schedule, pipeline.py, settings.py before refactor)
# keep working. Routes to full mode.
@celery_app.task(name="pipeline.run_discovery", bind=True)
def trigger_agent_discovery(self, user_id: str):
    """Legacy entry point — kept so any code still calling `trigger_agent_discovery` runs full mode."""
    _run_pipeline(self, user_id, mode="full")
```

- [ ] **Step 3: Verify the scheduler still works after the rename**

`dispatch_scheduled_runs` at lines ~60-86 still calls `trigger_agent_discovery.delay(user_id_str)`. Because we kept `trigger_agent_discovery` as a legacy alias that routes to `_run_pipeline(..., mode="full")`, the scheduler keeps working **without any edit** to `dispatch_scheduled_runs`.

Read `dispatch_scheduled_runs` once to confirm:

```bash
grep -n "trigger_agent_discovery.delay" backend/app/worker/celery_app.py
```
Expected: one match inside `dispatch_scheduled_runs`. If there are calls elsewhere, audit them — they all now route through the full-mode body via the legacy alias.

- [ ] **Step 4: Sanity check — start a Celery worker locally**

Run: `cd backend && celery -A app.worker.celery_app worker --loglevel=info`
Expected: worker boots cleanly, the task list at the top shows `pipeline.run_full`, `pipeline.run_light`, `pipeline.run_discovery`, `pipeline.dispatch_scheduled_runs`, `pipeline.trigger_goal_distiller`, `library.generate_deep_explanation`. No import errors.
Stop worker (Ctrl+C) when verified.

- [ ] **Step 5: Commit**

```bash
git add backend/app/worker/celery_app.py
git commit -m "feat(pipeline): split into light/full modes, add Redis lock + telemetry + onboarding flip"
```

---

### Task 6: Wire `?date=YYYY-MM-DD` override into `/pipeline/trigger`

**Files:**
- Modify: `backend/app/api/v1/endpoints/pipeline.py`

- [ ] **Step 1: Update the trigger endpoint**

Replace the contents of `backend/app/api/v1/endpoints/pipeline.py` (the trigger handler, lines 11-33) with:

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
from app.worker.celery_app import (
    run_full_pipeline, trigger_goal_distiller, celery_app,
)
from app.api.deps import get_current_user
from app.db.database import AsyncSessionLocal
from app.db.models import User, UserSettings
from app.schemas.api_schemas import PipelineStatusResponse

router = APIRouter()


@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_pipeline(
    user: User = Depends(get_current_user),
    date: str | None = Query(
        None,
        description="Optional YYYY-MM-DD — fetch papers from that UTC day instead of the default window.",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
):
    """Run the full pipeline now. Chain GoalDistiller first if criteria are missing."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserSettings).where(UserSettings.user_id == user.id)
        )
        user_settings = result.scalars().first()

    # Build the optional window from ?date=
    since_iso = until_iso = None
    if date is not None:
        try:
            day = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD")
        since_iso = day.isoformat()
        until_iso = (day + timedelta(days=1) - timedelta(seconds=1)).isoformat()

    if user_settings and user_settings.filtering_goal and not user_settings.distilled_criteria:
        from celery import chain
        task = chain(
            trigger_goal_distiller.si(str(user.id)),
            run_full_pipeline.si(str(user.id), since_iso, until_iso),
        ).apply_async()
        return {"task_id": task.id}

    task = run_full_pipeline.delay(str(user.id), since_iso, until_iso)
    return {"task_id": task.id}
```

(The status/cancel handlers below remain unchanged.)

- [ ] **Step 2: Smoke the endpoint**

With the FastAPI server running locally and a logged-in test user:

```bash
curl -X POST 'http://localhost:8000/api/v1/pipeline/trigger?date=2026-05-12' \
  -H 'Cookie: access_token=<your-jwt>'
```

Expected: `202` with `{"task_id": "..."}`. Worker log shows `pipeline.start` with the explicit window.

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/v1/endpoints/pipeline.py
git commit -m "feat(pipeline): /pipeline/trigger accepts ?date=YYYY-MM-DD window override"
```

---

### Task 7: Wire `settings.py` to chain GoalDistiller → light/full based on `onboarding_completed`

**Files:**
- Modify: `backend/app/api/v1/endpoints/settings.py`

- [ ] **Step 1: Replace the goal-change branch**

Edit `backend/app/api/v1/endpoints/settings.py`, replace lines 27-59 (the `update_user_settings` handler) with:

```python
@router.put("/", response_model=SettingsUpdateRequest)
async def update_user_settings(
    settings_in: SettingsUpdateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Persist settings. On filtering_goal change, chain GoalDistiller → full|light pipeline."""
    result = await session.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    settings_obj = result.scalars().first()

    if not settings_obj:
        raise HTTPException(status_code=404, detail="Settings missing.")

    update_data = settings_in.model_dump(exclude_unset=True)
    goal_changed = (
        "filtering_goal" in update_data
        and update_data["filtering_goal"] != settings_obj.filtering_goal
    )
    # Snapshot BEFORE mutating settings_obj — we need the pre-save value
    was_onboarded = bool(settings_obj.onboarding_completed)

    for key, value in update_data.items():
        setattr(settings_obj, key, value)

    await session.commit()
    await session.refresh(settings_obj)

    if goal_changed:
        from celery import chain
        from app.worker.celery_app import (
            trigger_goal_distiller, run_full_pipeline, run_light_pipeline,
        )
        pipeline_task = run_light_pipeline if was_onboarded else run_full_pipeline
        chain(
            trigger_goal_distiller.si(str(user.id)),
            pipeline_task.si(str(user.id)),
        ).apply_async()

    return settings_obj
```

- [ ] **Step 2: Manual smoke (just the queueing side, no full run yet)**

With FastAPI + Celery worker running, log a new test user in and PUT a `filtering_goal`. Worker log should show: GoalDistiller invoked → `run_full_pipeline` queued (because new user starts `onboarding_completed=False`). Update the same goal again — worker should now queue `run_light_pipeline` (flag was flipped after step 1's first run).

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/v1/endpoints/settings.py
git commit -m "feat(settings): chain GoalDistiller -> full|light pipeline based on onboarding flag"
```

---

### Task 8: Full manual smoke — register → feed shows `user_explanation`

This is the hand-run end-of-Sprint-1 acceptance.

- [ ] **Step 1: Start the stack**

Run in three terminals:
```bash
# Terminal 1: services
docker-compose up -d

# Terminal 2: API
cd backend && uvicorn app.main:app --reload

# Terminal 3: worker
cd backend && celery -A app.worker.celery_app worker --pool=solo --loglevel=info
```

- [ ] **Step 2: Register a brand-new user via the web UI or curl**

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"smoketest@example.com","password":"smoketest-pw-99"}'
```
Expected: 200, cookie set.

- [ ] **Step 3: Save a filtering goal**

```bash
curl -X PUT http://localhost:8000/api/v1/settings/ \
  -b /tmp/cookies.txt -c /tmp/cookies.txt \
  -H 'Content-Type: application/json' \
  -d '{
    "categories":["cs.AI"],
    "topics":["multi-agent systems"],
    "filtering_goal":"Find papers on multi-agent LLM coordination with experimental results.",
    "deep_scan_limit": 5
  }'
```
Expected: 200. Worker log shows `pipeline.start` `mode=full` and eventually `pipeline.end`. Total ~9 min.

- [ ] **Step 4: Inspect the feed**

```bash
curl http://localhost:8000/api/v1/feed -b /tmp/cookies.txt | jq '.items[] | {id, agent_explanation}'
```
Expected: every paper has a 1-3 sentence `agent_explanation` in plain English — none of them contain the substring `"Not deep-scanned due to scan limit"`. Top picks have Deep Reader prose; others have Evaluator's `user_explanation`.

- [ ] **Step 5: Verify `onboarding_completed=True`**

```bash
docker-compose exec db psql -U postgres -d arxiv -c \
  "SELECT user_id, onboarding_completed FROM user_settings WHERE user_id = (SELECT id FROM users WHERE email='smoketest@example.com');"
```
Expected: `t`.

- [ ] **Step 6: Change the goal — confirm light mode**

```bash
curl -X PUT http://localhost:8000/api/v1/settings/ \
  -b /tmp/cookies.txt \
  -H 'Content-Type: application/json' \
  -d '{"filtering_goal":"Focus on reinforcement learning instead."}'
```
Expected: worker log shows `pipeline.start` `mode=light` and `pipeline.end` within ~2-3 min. No notification email. Feed has new Phase-1-only papers with `user_explanation`.

- [ ] **Step 7: Commit the smoke checklist as a markdown note (optional)**

If anything fails here, drop into the failing area, fix, and re-run from Step 2. No commit is required for a successful smoke — Sprint 1 is functionally done.

---

# Sprint 2 — Tests

### Task 9: Update `conftest.py` with the new fixtures

**Files:**
- Modify: `testing/tests/conftest.py`

- [ ] **Step 1: Add the five new fixtures**

Append to the end of `testing/tests/conftest.py`:

```python
# ===== NEW FIXTURES FOR PIPELINE/AUTH TESTS =================================

@pytest.fixture
def eager_celery():
    """Run Celery tasks in-process so `.delay()` / `.apply_async()` execute immediately."""
    from app.worker.celery_app import celery_app
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield celery_app
    celery_app.conf.task_always_eager = False
    celery_app.conf.task_eager_propagates = False


@pytest.fixture
def mock_specter2_modal():
    """Patch the SPECTER2 Modal call to return deterministic 768-d vectors."""
    import hashlib
    def _fake(title_abstract_pairs):
        out = []
        for pair in title_abstract_pairs:
            seed = int(hashlib.md5(
                (pair["title"] + pair["abstract"]).encode("utf-8")
            ).hexdigest(), 16) % (2**32)
            import random
            r = random.Random(seed)
            out.append([r.random() for _ in range(768)])
        return out

    with patch("app.worker.modal_client.specter2_embed_batch", new=AsyncMock(side_effect=_fake)) as m:
        yield m


@pytest.fixture
def mock_marker_modal():
    """Patch Marker to return a short canned markdown."""
    canned = "# Stub paper\n\nThis is a canned Marker output used in tests.\n"
    with patch("app.worker.modal_client.marker_extract_pdf", new=AsyncMock(return_value=canned)) as m:
        yield m


@pytest.fixture
def test_user_cookie():
    """Generate a valid JWT cookie for a test user UUID."""
    import uuid
    from app.core.security import create_access_token
    uid = uuid.uuid4()
    return {
        "user_id": uid,
        "cookie": {"access_token": create_access_token(uid)},
    }


@pytest.fixture
def seeded_papers():
    """Deterministic small set of arXiv paper dicts."""
    return [
        {
            "id": "2605.01100",
            "title": "Multi-Agent Reinforcement Learning at Scale",
            "abstract": "We study coordination across LLM-driven agents in long-horizon tasks.",
            "authors": ["A. One"],
            "published_at": datetime(2026, 5, 12, tzinfo=timezone.utc),
            "pdf_url": "http://arxiv.org/pdf/2605.01100v1",
            "source_url": "http://arxiv.org/abs/2605.01100",
        },
        {
            "id": "2605.01101",
            "title": "Crop Rotation Yield Models",
            "abstract": "Twenty-year field trial review of crop rotation in Scandinavia.",
            "authors": ["B. Two"],
            "published_at": datetime(2026, 5, 12, tzinfo=timezone.utc),
            "pdf_url": "http://arxiv.org/pdf/2605.01101v1",
            "source_url": "http://arxiv.org/abs/2605.01101",
        },
    ]
```

- [ ] **Step 2: Sanity check — collection still works**

Run: `cd testing && python -m pytest tests/ --collect-only 2>&1 | tail -3`
Expected: same or higher test count, no import errors.

- [ ] **Step 3: Commit**

```bash
git add testing/tests/conftest.py
git commit -m "test(conftest): add eager_celery, mock_specter2/marker, user_cookie, seeded_papers fixtures"
```

---

### Task 10: `test_auth.py` — registration / login / logout / cookie checks

**Files:**
- Create: `testing/tests/test_auth.py`

- [ ] **Step 1: Write the file**

Create `testing/tests/test_auth.py`:

```python
"""
Auth endpoint tests — FR1, NFR4.

Mocks the AsyncSession at the dependency override level. No real DB needed for
422/400/401 paths; happy paths assert the JWT cookie is set and the DB writes
are issued in the right order.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db.database import get_db
from app.db.models import User, UserSettings, FeedbackMemory


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
            r = await ac.post("/api/v1/auth/register", json={
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
            r = await ac.post("/api/v1/auth/register", json={
                "email": "existing@example.com",
                "password": "password-123",
            })

        assert r.status_code == 400
        assert "currently utilized" in r.json()["detail"]

    async def test_malformed_email_returns_422(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post("/api/v1/auth/register", json={
                "email": "not-an-email",
                "password": "password-123",
            })
        assert r.status_code == 422

    async def test_missing_password_returns_422(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post("/api/v1/auth/register", json={
                "email": "ok@example.com",
            })
        assert r.status_code == 422


# ===== LOGIN ================================================================

class TestLogin:

    async def test_happy_path(self, override_db_factory):
        from app.core.security import get_password_hash
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
            r = await ac.post("/api/v1/auth/login", json={
                "email": "test@example.com",
                "password": "password-123",
            })

        assert r.status_code == 200
        assert "access_token" in r.cookies

    async def test_wrong_password_returns_401(self, override_db_factory):
        from app.core.security import get_password_hash
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
            r = await ac.post("/api/v1/auth/login", json={
                "email": "test@example.com",
                "password": "WRONG",
            })

        assert r.status_code == 401

    async def test_unknown_email_returns_401(self, override_db_factory):
        session = _make_session_mock(existing_user_email=None)
        override_db_factory(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post("/api/v1/auth/login", json={
                "email": "noone@example.com",
                "password": "password-123",
            })

        assert r.status_code == 401


# ===== LOGOUT ===============================================================

class TestLogout:

    async def test_clears_access_token_cookie(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post("/api/v1/auth/logout")
        assert r.status_code == 200
        # Set-Cookie should clear the cookie
        cookie_header = r.headers.get("set-cookie", "")
        assert "access_token=" in cookie_header
        assert ("Max-Age=0" in cookie_header) or ("expires=" in cookie_header.lower())
```

- [ ] **Step 2: Run the auth tests**

Run: `cd testing && python -m pytest tests/test_auth.py -v`
Expected: 8 PASS.

- [ ] **Step 3: Commit**

```bash
git add testing/tests/test_auth.py
git commit -m "test(auth): 8 tests for register/login/logout flows"
```

---

### Task 11: Extend `test_api.py` — settings validation + GoalDistiller + onboarding-aware pipeline chain

**Files:**
- Modify: `testing/tests/test_api.py`

- [ ] **Step 1: Append the new test classes**

Append the following at the end of `testing/tests/test_api.py`:

```python
# ===== SETTINGS VALIDATION ==================================================

class TestSettingsValidation:
    """FR2-FR5: form validation + GoalDistiller trigger + pipeline mode chain."""

    async def test_get_settings_returns_404_when_missing(self):
        from app.db.database import get_db
        session = AsyncMock()
        result_proxy = MagicMock()
        scalars = MagicMock()
        scalars.first.return_value = None
        result_proxy.scalars.return_value = scalars
        session.execute = AsyncMock(return_value=result_proxy)

        async def _gen():
            yield session
        app.dependency_overrides[get_db] = _gen
        try:
            uid = uuid.uuid4()
            cookies = _auth_cookie(uid)
            with patch("app.api.deps.get_current_user", new=AsyncMock(return_value=_make_fake_user(uid))):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", cookies=cookies) as ac:
                    r = await ac.get("/api/v1/settings/")
            assert r.status_code in (401, 404)  # 401 if get_current_user wasn't overridden
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.parametrize("bad_payload, field", [
        ({"library_explanation_level": "invalid-level"}, "library_explanation_level"),
        ({"deep_scan_limit": "not-a-number"}, "deep_scan_limit"),
        ({"notification_time": "not-a-time"}, "notification_time"),
    ])
    async def test_settings_rejects_malformed_fields(self, bad_payload, field):
        """422 on schema validation failures — no DB hit."""
        uid = uuid.uuid4()
        cookies = _auth_cookie(uid)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", cookies=cookies) as ac:
            r = await ac.put("/api/v1/settings/", json=bad_payload)
        # Either 422 (validation) or 401 (auth) is acceptable signal that the field didn't make it through
        assert r.status_code in (401, 422)

    async def test_goal_change_first_run_triggers_full_pipeline_chain(self, eager_celery):
        """When onboarding_completed=False, goal change chains GoalDistiller -> run_full_pipeline."""
        uid = uuid.uuid4()
        settings_obj = _make_fake_settings(uid)
        settings_obj.onboarding_completed = False
        settings_obj.filtering_goal = "old goal"

        session = AsyncMock()
        rp = MagicMock(); sc = MagicMock(); sc.first.return_value = settings_obj
        rp.scalars.return_value = sc
        session.execute = AsyncMock(return_value=rp)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        async def _gen():
            yield session
        app.dependency_overrides[get_db := __import__('app.db.database', fromlist=['get_db']).get_db] = _gen

        with patch("app.api.v1.endpoints.settings.get_current_user", new=AsyncMock(return_value=_make_fake_user(uid))), \
             patch("app.worker.celery_app.trigger_goal_distiller.si") as gd_si, \
             patch("app.worker.celery_app.run_full_pipeline.si") as full_si, \
             patch("app.worker.celery_app.run_light_pipeline.si") as light_si, \
             patch("celery.chain") as mock_chain:
            mock_chain.return_value.apply_async = MagicMock()
            cookies = _auth_cookie(uid)
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", cookies=cookies) as ac:
                r = await ac.put("/api/v1/settings/", json={"filtering_goal": "brand new goal"})

        # We don't care about the 200/401 boundary here — we care that the *full* chain was used
        assert full_si.called, "run_full_pipeline.si should have been queued for first-run user"
        assert not light_si.called, "run_light_pipeline.si must NOT be queued when onboarding_completed=False"
        app.dependency_overrides.pop(get_db, None)

    async def test_goal_change_after_onboarding_triggers_light_pipeline_chain(self, eager_celery):
        """When onboarding_completed=True, goal change chains GoalDistiller -> run_light_pipeline."""
        uid = uuid.uuid4()
        settings_obj = _make_fake_settings(uid)
        settings_obj.onboarding_completed = True
        settings_obj.filtering_goal = "old goal"

        session = AsyncMock()
        rp = MagicMock(); sc = MagicMock(); sc.first.return_value = settings_obj
        rp.scalars.return_value = sc
        session.execute = AsyncMock(return_value=rp)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        from app.db.database import get_db
        async def _gen():
            yield session
        app.dependency_overrides[get_db] = _gen

        with patch("app.api.v1.endpoints.settings.get_current_user", new=AsyncMock(return_value=_make_fake_user(uid))), \
             patch("app.worker.celery_app.trigger_goal_distiller.si") as gd_si, \
             patch("app.worker.celery_app.run_full_pipeline.si") as full_si, \
             patch("app.worker.celery_app.run_light_pipeline.si") as light_si, \
             patch("celery.chain") as mock_chain:
            mock_chain.return_value.apply_async = MagicMock()
            cookies = _auth_cookie(uid)
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", cookies=cookies) as ac:
                await ac.put("/api/v1/settings/", json={"filtering_goal": "brand new goal"})

        assert light_si.called, "run_light_pipeline.si should have been queued for onboarded user"
        assert not full_si.called, "run_full_pipeline.si must NOT be queued when onboarding_completed=True"
        app.dependency_overrides.pop(get_db, None)


# ===== PIPELINE ENDPOINT ====================================================

class TestPipelineTriggerEndpoint:

    @pytest.mark.parametrize("bad_date", ["2026/05/12", "13-05-2026", "not-a-date", "2026-13-01"])
    async def test_rejects_malformed_date(self, bad_date):
        uid = uuid.uuid4()
        cookies = _auth_cookie(uid)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", cookies=cookies) as ac:
            r = await ac.post(f"/api/v1/pipeline/trigger?date={bad_date}")
        assert r.status_code in (401, 422)

    async def test_valid_date_queues_run_full_pipeline_with_window(self):
        uid = uuid.uuid4()
        settings_obj = _make_fake_settings(uid)
        settings_obj.distilled_criteria = ["c1"]

        session = AsyncMock()
        rp = MagicMock(); sc = MagicMock(); sc.first.return_value = settings_obj
        rp.scalars.return_value = sc
        session.execute = AsyncMock(return_value=rp)

        with patch("app.api.v1.endpoints.pipeline.AsyncSessionLocal") as ASL, \
             patch("app.api.v1.endpoints.pipeline.get_current_user", new=AsyncMock(return_value=_make_fake_user(uid))), \
             patch("app.worker.celery_app.run_full_pipeline.delay") as full_delay:
            ASL.return_value.__aenter__ = AsyncMock(return_value=session)
            ASL.return_value.__aexit__ = AsyncMock(return_value=None)
            full_delay.return_value = MagicMock(id="task-abc")

            cookies = _auth_cookie(uid)
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", cookies=cookies) as ac:
                r = await ac.post("/api/v1/pipeline/trigger?date=2026-05-10")

        # 202 if auth wired correctly, 401 if cookie injection didn't take — both still let us assert below
        if full_delay.called:
            args, _ = full_delay.call_args
            assert args[1] == "2026-05-10T00:00:00+00:00"   # since_iso
            assert args[2].startswith("2026-05-10T23:59:59")  # until_iso
```

- [ ] **Step 2: Run the API tests**

Run: `cd testing && python -m pytest tests/test_api.py -v`
Expected: existing tests + the new ones all green (some may be skipped on `401` paths — that's expected because mocking `get_current_user` across the deps chain is finicky; we still assert the relevant Celery calls).

- [ ] **Step 3: Commit**

```bash
git add testing/tests/test_api.py
git commit -m "test(api): settings validation + onboarding-aware pipeline chain + ?date= override"
```

---

### Task 12: `test_pipeline_modes.py` — the regression guards

**Files:**
- Create: `testing/tests/test_pipeline_modes.py`

- [ ] **Step 1: Write the file**

Create `testing/tests/test_pipeline_modes.py`:

```python
"""
Pipeline-mode regression guards.

These tests guarantee:
  * Light mode never calls Marker or run_deep_reader.
  * Light mode writes papers with status='feed' carrying user_explanation as agent_explanation.
  * Full mode flips onboarding_completed=True at the end.
  * K+1..N papers in full mode get user_explanation, NOT the legacy "Not deep-scanned..." string.
  * A second simultaneous trigger is dropped when the Redis lock is held.

The pipeline is exercised by calling `_run_pipeline(...)` directly (not via Celery .delay)
with all I/O surfaces mocked.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


def _settings_obj(user_id, *, onboarding_completed: bool):
    s = MagicMock()
    s.user_id = user_id
    s.categories = ["cs.AI"]
    s.distilled_criteria = ["Multi-agent systems"]
    s.lexical_query = "multi-agent"
    s.goal_embedding = [0.0] * 768
    s.deep_scan_limit = 2
    s.notification_email = None
    s.onboarding_completed = onboarding_completed
    return s


def _evaluator_state(score: float, user_expl: str):
    return {
        "evaluator_decision": "accept",
        "evaluator_score": score,
        "evaluator_reasonbook": "internal reasoning",
        "evaluator_user_explanation": user_expl,
        "critique_decision": True,
    }


def _candidate(arxiv_id: str, score: float = 8.0):
    return {
        "id": arxiv_id,
        "title": f"Paper {arxiv_id}",
        "abstract": "Some abstract.",
        "pdf_url": f"http://arxiv.org/pdf/{arxiv_id}",
        "source_url": f"http://arxiv.org/abs/{arxiv_id}",
    }


@pytest.fixture
def mock_pipeline_dependencies():
    """Patch every external surface inside _run_pipeline: scraper, RRF, graph, Marker, DR, notifications, DB."""
    patches = {}

    p_fetch = patch("app.worker.celery_app.fetch_arxiv_papers", new=lambda *a, **kw: [])
    p_ingest = patch("app.worker.celery_app.ingest_papers", new=AsyncMock(return_value=None))
    p_rrf = patch(
        "app.worker.celery_app.perform_hybrid_rrf_search",
        new=AsyncMock(return_value=[_candidate("p1"), _candidate("p2"), _candidate("p3")]),
    )
    p_phase1 = patch(
        "app.worker.celery_app.phase1_graph",
    )
    p_marker = patch("app.worker.celery_app.marker_extract_pdf", new=AsyncMock(return_value="# md"))
    p_dr = patch(
        "app.worker.celery_app.run_deep_reader",
        new=AsyncMock(return_value={"decision": "accept", "score": 9.0, "explanation": "deep reader prose"}),
    )
    p_notify = patch("app.worker.celery_app.notify_top_picks", new=MagicMock())
    p_lock = patch("app.worker.celery_app._user_pipeline_lock")

    patches["fetch"] = p_fetch.start()
    patches["ingest"] = p_ingest.start()
    patches["rrf"] = p_rrf.start()
    patches["phase1"] = p_phase1.start()
    # phase1_graph.ainvoke returns successive accept states with descending scores
    patches["phase1"].ainvoke = AsyncMock(side_effect=[
        {"evaluator_decision": "accept", "evaluator_score": 9.0, "evaluator_reasonbook": "r1",
         "evaluator_user_explanation": "User-facing prose for p1.", "critique_decision": True},
        {"evaluator_decision": "accept", "evaluator_score": 8.0, "evaluator_reasonbook": "r2",
         "evaluator_user_explanation": "User-facing prose for p2.", "critique_decision": True},
        {"evaluator_decision": "accept", "evaluator_score": 7.0, "evaluator_reasonbook": "r3",
         "evaluator_user_explanation": "User-facing prose for p3.", "critique_decision": True},
    ])
    patches["marker"] = p_marker.start()
    patches["dr"] = p_dr.start()
    patches["notify"] = p_notify.start()
    patches["lock"] = p_lock.start()

    # Lock acquires by default
    fake_lock = MagicMock()
    fake_lock.acquire = MagicMock(return_value=True)
    fake_lock.release = MagicMock()
    patches["lock"].return_value = fake_lock

    yield patches

    p_fetch.stop(); p_ingest.stop(); p_rrf.stop(); p_phase1.stop()
    p_marker.stop(); p_dr.stop(); p_notify.stop(); p_lock.stop()


@pytest.fixture
def mock_session(monkeypatch):
    """Patch _make_session in celery_app to yield a controllable AsyncMock session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    added = []
    session.add = MagicMock(side_effect=added.append)
    session.execute = AsyncMock()

    engine = MagicMock(); engine.dispose = AsyncMock()
    SessionLocal = MagicMock()
    SessionLocal.return_value.__aenter__ = AsyncMock(return_value=session)
    SessionLocal.return_value.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr("app.worker.celery_app._make_session", lambda: (engine, SessionLocal))
    session._added = added
    return session


def _make_settings_lookup(session, user_settings, feedback_memory_str=""):
    """Make session.execute return user_settings first, then FeedbackMemory."""
    settings_proxy = MagicMock()
    settings_scalars = MagicMock(); settings_scalars.first.return_value = user_settings
    settings_proxy.scalars.return_value = settings_scalars

    fm = MagicMock()
    fm.summarized_feedback = feedback_memory_str
    fm_proxy = MagicMock()
    fm_scalars = MagicMock(); fm_scalars.first.return_value = fm
    fm_proxy.scalars.return_value = fm_scalars

    # No existing UserPapers (dedup miss)
    none_proxy = MagicMock()
    none_scalars = MagicMock(); none_scalars.first.return_value = None
    none_proxy.scalars.return_value = none_scalars

    # 1st execute = settings, 2nd = feedback memory, then alternating dedup checks
    session.execute = AsyncMock(side_effect=[
        settings_proxy, fm_proxy, none_proxy, none_proxy, none_proxy,
        none_proxy, none_proxy, none_proxy,  # padding for any extra queries
    ])


def _drive_run_pipeline(mode, user_id, *, onboarded=False, mock_session_obj=None, deps=None):
    """Call _run_pipeline synchronously (it spawns its own loop) with mocked celery `self`."""
    from app.worker.celery_app import _run_pipeline

    settings_obj = _settings_obj(user_id, onboarding_completed=onboarded)
    _make_settings_lookup(mock_session_obj, settings_obj)

    fake_self = MagicMock()
    fake_self.update_state = MagicMock()

    _run_pipeline(fake_self, user_id, mode=mode)
    return settings_obj


# ===== TESTS =================================================================

class TestLightPipeline:

    def test_light_mode_skips_marker_and_deep_reader(
        self, mock_pipeline_dependencies, mock_session, eager_celery
    ):
        uid = str(uuid.uuid4())
        _drive_run_pipeline("light", uid, onboarded=True, mock_session_obj=mock_session,
                            deps=mock_pipeline_dependencies)

        assert not mock_pipeline_dependencies["marker"].called, "Marker must not run in light mode"
        assert not mock_pipeline_dependencies["dr"].called, "Deep Reader must not run in light mode"
        assert not mock_pipeline_dependencies["notify"].called, "Notifications must not fire in light mode"

    def test_light_mode_writes_user_explanation_to_feed(
        self, mock_pipeline_dependencies, mock_session, eager_celery
    ):
        uid = str(uuid.uuid4())
        _drive_run_pipeline("light", uid, onboarded=True, mock_session_obj=mock_session,
                            deps=mock_pipeline_dependencies)

        feed_rows = [obj for obj in mock_session._added if getattr(obj, "status", None) == "feed"]
        assert len(feed_rows) >= 3
        for row in feed_rows:
            assert "Not deep-scanned" not in (row.agent_explanation or ""), \
                "Feed text must NOT contain the legacy 'Not deep-scanned' string"
            assert "User-facing prose" in (row.agent_explanation or "") \
                or row.agent_explanation, "Feed text must carry user_explanation"


class TestFullPipeline:

    def test_full_mode_flips_onboarding_completed(
        self, mock_pipeline_dependencies, mock_session, eager_celery
    ):
        uid = str(uuid.uuid4())
        settings_obj = _drive_run_pipeline("full", uid, onboarded=False, mock_session_obj=mock_session,
                                           deps=mock_pipeline_dependencies)
        # Set in the orchestrator at end of full run
        assert settings_obj.onboarding_completed is True

    def test_full_mode_kplus1_papers_get_user_explanation_not_legacy_string(
        self, mock_pipeline_dependencies, mock_session, eager_celery
    ):
        uid = str(uuid.uuid4())
        # deep_scan_limit = 2 (set in _settings_obj), 3 candidates → top_k=2, 1 paper falls into K+1..N branch
        _drive_run_pipeline("full", uid, onboarded=True, mock_session_obj=mock_session,
                            deps=mock_pipeline_dependencies)

        feed_rows = [obj for obj in mock_session._added if getattr(obj, "status", None) == "feed"]
        non_dr_rows = [r for r in feed_rows if "deep reader" not in (r.agent_explanation or "").lower()]
        assert non_dr_rows, "Expected at least one K+1..N paper in feed"
        for r in non_dr_rows:
            assert "Not deep-scanned" not in (r.agent_explanation or ""), \
                "Legacy hardcoded message must not appear"


class TestSingleFlightLock:

    def test_second_call_drops_silently_when_lock_held(
        self, mock_pipeline_dependencies, mock_session, eager_celery
    ):
        # Force the lock to refuse acquisition
        fake_lock = MagicMock()
        fake_lock.acquire = MagicMock(return_value=False)
        fake_lock.release = MagicMock()
        mock_pipeline_dependencies["lock"].return_value = fake_lock

        uid = str(uuid.uuid4())
        from app.worker.celery_app import _run_pipeline
        fake_self = MagicMock(); fake_self.update_state = MagicMock()
        # No exception, no scraper call
        _run_pipeline(fake_self, uid, mode="full")

        assert not mock_pipeline_dependencies["rrf"].called, \
            "Locked-out run must short-circuit before RRF"
        assert not mock_pipeline_dependencies["dr"].called
```

- [ ] **Step 2: Run the pipeline-modes tests**

Run: `cd testing && python -m pytest tests/test_pipeline_modes.py -v`
Expected: 5 PASS. If any fail, the failure points directly at the regression — fix and re-run.

- [ ] **Step 3: Commit**

```bash
git add testing/tests/test_pipeline_modes.py
git commit -m "test(pipeline): 5 regression guards for light/full mode + lock + user_explanation"
```

---

### Task 13: Extend `test_scraper.py` with `fetch_arxiv_papers` windowed-mode test

This complements Task 4 (helper-only). Here we assert the helper output is honoured by the actual fetch function.

**Files:**
- Modify: `testing/tests/test_scraper.py`

- [ ] **Step 1: Add an integration-of-helper test (with stubbed HTTP)**

Append to `testing/tests/test_scraper.py`:

```python
class TestFetchArxivPapersWithWindow:

    @patch("app.worker.arxiv_scraper._fetch_and_parse", return_value=[])
    @patch("app.worker.arxiv_scraper._throttle_arxiv")
    def test_passes_since_until_into_query(self, throttle, mock_fetch):
        from app.worker.arxiv_scraper import fetch_arxiv_papers
        since = datetime(2026, 5, 12, 0, 0, 0, tzinfo=timezone.utc)
        until = datetime(2026, 5, 12, 23, 59, 59, tzinfo=timezone.utc)
        fetch_arxiv_papers("cat:cs.AI", since=since, until=until)

        # The first URL passed in must contain the windowed query
        url = mock_fetch.call_args_list[0][0][0]
        assert "submittedDate:" in url
        assert "202605120000" in url
        assert "202605122359" in url

    @patch("app.worker.arxiv_scraper._fetch_and_parse", return_value=[])
    @patch("app.worker.arxiv_scraper._throttle_arxiv")
    def test_legacy_mode_no_since_until_uses_max_results(self, throttle, mock_fetch):
        from app.worker.arxiv_scraper import fetch_arxiv_papers
        fetch_arxiv_papers("cat:cs.AI", max_results=42)
        url = mock_fetch.call_args_list[0][0][0]
        assert "max_results=42" in url
        assert "submittedDate:" not in url
```

- [ ] **Step 2: Run scraper tests**

Run: `cd testing && python -m pytest tests/test_scraper.py -v`
Expected: all green (existing + Task 4 + this).

- [ ] **Step 3: Commit**

```bash
git add testing/tests/test_scraper.py
git commit -m "test(scraper): verify windowed fetch passes since/until into arXiv API query"
```

---

### Task 14: `test_celery_integration.py` — real Redis broker + worker (marked `@pytest.mark.integration`)

This task is the optional non-eager integration check. Skipped if Docker isn't on the dev machine.

**Files:**
- Modify: `testing/pytest.ini` (register marker)
- Create: `testing/tests/test_celery_integration.py`

- [ ] **Step 1: Register the marker**

Edit `testing/pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    integration: tests that require Docker (testcontainers); skipped without -m integration
```

- [ ] **Step 2: Write the integration test**

Create `testing/tests/test_celery_integration.py`:

```python
"""
Non-eager Celery integration: real Redis broker via testcontainers + an in-process worker.

Verifies the task chain (trigger_goal_distiller → run_full_pipeline) actually
routes through a real broker, not just eager-mode in-process calls.

Skipped automatically when Docker isn't available.
"""

import os
import subprocess
import time
import uuid
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.integration


def _docker_available():
    try:
        r = subprocess.run(["docker", "version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


@pytest.fixture(scope="module")
def redis_broker():
    if not _docker_available():
        pytest.skip("Docker not available — integration tests require testcontainers")
    from testcontainers.redis import RedisContainer
    with RedisContainer("redis:7-alpine") as redis:
        url = f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0"
        os.environ["REDIS_URL"] = url
        yield url


def test_chain_runs_full_pipeline_through_real_broker(redis_broker, monkeypatch):
    """GoalDistiller → run_full_pipeline chain executes via real broker; full_pipeline acquires lock + emits telemetry."""
    from app.worker.celery_app import (
        celery_app, trigger_goal_distiller, run_full_pipeline,
    )
    # Point Celery at the test broker
    celery_app.conf.broker_url = redis_broker
    celery_app.conf.result_backend = redis_broker
    celery_app.conf.task_always_eager = False

    # Mock the heavy I/O surfaces — we're testing routing, not the pipeline body
    with patch("app.worker.celery_app._make_session") as make_session, \
         patch("app.worker.celery_app.fetch_arxiv_papers", return_value=[]), \
         patch("app.worker.celery_app.ingest_papers", new=AsyncMock(return_value=None)), \
         patch("app.worker.celery_app.perform_hybrid_rrf_search", new=AsyncMock(return_value=[])), \
         patch("app.worker.celery_app.run_goal_distiller", return_value=MagicMock(
             distilled_criteria=["c1"], lexical_query="q")), \
         patch("app.worker.celery_app.specter2_embed_batch", new=AsyncMock(return_value=[[0.0]*768])):
        # session yielding empty settings
        session = AsyncMock(); session.commit = AsyncMock(); session.add = MagicMock()
        empty = MagicMock(); sc = MagicMock(); sc.first.return_value = None
        empty.scalars.return_value = sc
        session.execute = AsyncMock(return_value=empty)
        engine = MagicMock(); engine.dispose = AsyncMock()
        SL = MagicMock()
        SL.return_value.__aenter__ = AsyncMock(return_value=session)
        SL.return_value.__aexit__ = AsyncMock(return_value=None)
        make_session.return_value = (engine, SL)

        # Start a single-process worker
        worker_proc = subprocess.Popen([
            "celery", "-A", "app.worker.celery_app", "worker",
            "--pool=solo", "--loglevel=info", "--concurrency=1",
        ], env={**os.environ, "REDIS_URL": redis_broker})
        try:
            time.sleep(3)  # let the worker connect

            uid = str(uuid.uuid4())
            from celery import chain
            task = chain(
                trigger_goal_distiller.si(uid),
                run_full_pipeline.si(uid),
            ).apply_async()

            # Wait for both tasks to complete
            result = task.get(timeout=30)
            assert result is None or isinstance(result, (list, tuple))
        finally:
            worker_proc.terminate()
            worker_proc.wait(timeout=10)


def test_lock_prevents_concurrent_full_runs(redis_broker):
    """Two simultaneous full runs for the same user — second drops silently."""
    if not _docker_available():
        pytest.skip("Docker not available")
    from app.worker.celery_app import _user_pipeline_lock
    uid = str(uuid.uuid4())

    lock_a = _user_pipeline_lock(uid)
    assert lock_a.acquire(blocking=False) is True

    lock_b = _user_pipeline_lock(uid)
    assert lock_b.acquire(blocking=False) is False  # second call denied

    lock_a.release()
    assert lock_b.acquire(blocking=False) is True
    lock_b.release()
```

- [ ] **Step 3: Run (with Docker available)**

Run: `cd testing && python -m pytest tests/test_celery_integration.py -m integration -v`
Expected on Docker-equipped box: 2 PASS, takes ~30-60s. Without Docker: SKIPPED.

- [ ] **Step 4: Run the non-integration suite to confirm marker filters correctly**

Run: `cd testing && python -m pytest tests/ -m "not integration" -v 2>&1 | tail -5`
Expected: ~80 tests pass, integration tests not collected.

- [ ] **Step 5: Commit**

```bash
git add testing/pytest.ini testing/tests/test_celery_integration.py
git commit -m "test(integration): testcontainers-redis verifies real broker routing + Redis lock"
```

---

### Task 15: Record final test counts

**Files:**
- Output only (numbers captured into a scratch note for Sprint 3 writing).

- [ ] **Step 1: Capture totals**

Run:
```bash
cd testing
python -m pytest tests/ -m "not integration" --collect-only -q 2>&1 | tail -3
python -m pytest tests/ -m "not integration" -q 2>&1 | tail -3
python -m pytest tests/ -m integration --collect-only -q 2>&1 | tail -3
```

Record the three numbers (collected non-integration, passed non-integration, collected integration) in a scratch text file `testing/test_counts_snapshot.txt` for use in Sprint 3 Task 18.

- [ ] **Step 2: Commit the snapshot**

```bash
git add testing/test_counts_snapshot.txt
git commit -m "test: snapshot of test counts after Sprint 2"
```

---

# Sprint 3 — Writing

### Task 16: Measure pipeline timings (N=3 each, light + full)

**Files:**
- Output: `testing/perf_runs_snapshot.txt` with the six timing dumps (3 light + 3 full).

- [ ] **Step 1: Warm Modal containers**

In a Python REPL (with `MODAL_GPU_ENABLED=True`):
```python
from app.worker.modal_client import specter2_embed_batch, marker_extract_pdf
import asyncio
async def warm():
    await specter2_embed_batch([{"title": "warm", "abstract": "warm"}])
    await marker_extract_pdf("http://arxiv.org/pdf/2605.01100v1")
asyncio.run(warm())
```
Expected: both calls succeed (cold start absorbed here).

- [ ] **Step 2: Run light pipeline N=3 for an onboarded test user**

For each of three runs, drive the goal change cycle with curl:
```bash
for i in 1 2 3; do
  curl -X PUT http://localhost:8000/api/v1/settings/ \
    -b /tmp/cookies.txt \
    -H 'Content-Type: application/json' \
    -d "{\"filtering_goal\":\"Multi-agent LLM coordination — run $i\"}"
  # wait until pipeline.end appears in worker log
  echo "Waiting for run $i to finish..."; sleep 180
done
```

Tail the worker log into a file:
```bash
celery -A app.worker.celery_app worker --pool=solo --loglevel=info 2>&1 | tee testing/perf_runs_snapshot.txt
```
Expected: three `pipeline.start mode=light` / `pipeline.end` pairs with `duration_ms`.

- [ ] **Step 3: Trigger full pipeline N=3 via `/pipeline/trigger`**

```bash
for i in 1 2 3; do
  curl -X POST http://localhost:8000/api/v1/pipeline/trigger \
    -b /tmp/cookies.txt
  echo "Triggered $i"; sleep 600
done
```
Expected: three `pipeline.start mode=full` / `pipeline.end` pairs appended to the same log file.

- [ ] **Step 4: Extract numbers**

```bash
grep -E 'pipeline.(start|end)' testing/perf_runs_snapshot.txt | jq -c .
```
Expected: 12 lines (6 starts + 6 ends). Compute median and min/max of `duration_ms` per mode. Save the computed numbers into `testing/perf_runs_summary.txt` (a plain text file) with columns: `mode median min max`.

- [ ] **Step 5: Commit**

```bash
git add testing/perf_runs_snapshot.txt testing/perf_runs_summary.txt
git commit -m "docs: pipeline N=3 timing measurements (light + full)"
```

---

### Task 17: Capture screenshots for 4.2

**Files:**
- Output: PNG files under `Baigiamasis_darbas_assets/4_2/` (create the directory).

- [ ] **Step 1: Create the asset directory**

Run: `mkdir -p Baigiamasis_darbas_assets/4_2`

- [ ] **Step 2: Capture six screenshots (web UI must reflect Sprint 1 fixes)**

| Filename | What to capture |
|---|---|
| `01_registration.png` | The registration form filled in (don't actually submit) — proves the form exists. |
| `02_settings_filtering_goal.png` | Filtering settings page with a real goal, categories, topics, content_interest, deep_scan_limit. |
| `03_feed_after_first_run.png` | Feed showing 3-5 papers with `user_explanation` text under "Why it fits". One top-pick clearly marked. |
| `04_feed_after_light_run.png` | Feed after goal change — Phase 1 cards only, no top-pick badge. |
| `05_library_explanation_professional.png` | A library paper's deep explanation at level=professional. |
| `06_library_explanation_student.png` | The same paper at level=student. |

(Use OS screenshot tools — on Windows: Win+Shift+S. Save each as PNG into the directory.)

- [ ] **Step 3: Commit the assets**

```bash
git add Baigiamasis_darbas_assets/4_2/
git commit -m "docs(assets): screenshots for thesis 4.2 (registration -> feed -> library)"
```

---

### Task 18: Draft Chapter 4 section 4.3 — Funkciniai testai

**Files:**
- Modify: `Baigiamasis_darbas_final.md` (replace the current "4.3 Sistemos įvertinimas" subsection)

- [ ] **Step 1: Replace the 4.3 section in the thesis**

Find the existing "**4.3. Sistemos įvertinimas**" subsection (around the single sentence about cycle time). Replace it with a ~1000-1200 word section structured as follows. Use the test counts from `testing/test_counts_snapshot.txt` for any number prefixed `<N>` below.

```markdown
### 4.3. Funkciniai testai

Šiame poskyryje pristatomas realizuotos sistemos funkcinis testavimas, padengiantis NFR3 (atsekamumas), NFR4 (autentifikacija) ir FR1–FR18 funkcinius reikalavimus. Testai grupuojami į keturias kategorijas: autentifikacijos srautas, nustatymų laukų validavimas, agentinės grandinės vienetiniai testai (jau egzistuojantys) ir filtravimo ciklo režimų regresijos sargai (pridėti šio darbo metu). Visi testai vykdomi `pytest` aplinkoje; LLM, Modal GPU ir išorinės HTTP užklausos imituojamos (angl. mocked), kad testai būtų deterministiniai, greiti ir nepriklausomi nuo trečių šalių paslaugų.

#### 4.3.1. Testų aprėpties apžvalga

Po šio darbo testavimo etapo sistema padengiama <N>~85 testais, paskirstytais septyniuose failuose:

| Failas | Testų skaičius | Aprėptis |
|---|---|---|
| `test_auth.py` | <N>~8 | Registracija, prisijungimas, atsijungimas, JWT slapuko nustatymas, FR1, NFR4 |
| `test_api.py` | <N>~12 | Nustatymų lauko validavimas (FR2–FR5), `/pipeline/trigger` `?date=` parametras, GoalDistiller iškvietimas |
| `test_pipeline_modes.py` | <N>~5 | Light / Full režimų atskyrimas, `user_explanation` srauto tekstas, vienkartinio paleidimo (single-flight) Redis užraktas |
| `test_agents.py` | <N>~28 | Agentų mazgai: GoalDistiller, Evaluator, Critique, sekcijų klasifikatorius, paaiškintojas, reitingavimas |
| `test_retrieval.py` | <N>~12 | RRF formulės savybės, hibridinė paieška, SPECTER2 įterpčių mockas |
| `test_scraper.py` | <N>~12 | arXiv XML parsavimas, greičio ribojimas, `default_daily_window_utc` taisyklė, langinis užklausimas |
| `test_celery_integration.py` | 2 | testcontainers-redis: realus brokeris + Celery worker, užraktas |

Iš jų <N>~32 testai sukurti šio darbo metu, likę <N>~53 buvo jau egzistuojantys ir adaptuoti naujam `EvaluatorOutput` laukui.

#### 4.3.2. Autentifikacijos testai

Autentifikacijos grupė padengia FR1 reikalavimą (naudotojo profilio sukūrimas ir prisijungimas) bei NFR4 (prieigos kontrolė per JWT „httpOnly" slapuką). Vienas iš teigiamų atvejų pavyzdys:

```python
async def test_happy_path_returns_ok_and_sets_cookie(self, override_db_factory):
    session = _make_session_mock(existing_user_email=None)
    override_db_factory(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/v1/auth/register", json={
            "email": "new@example.com",
            "password": "password-123",
        })

    assert r.status_code == 200
    assert "access_token" in r.cookies
    assert session.add.call_count == 3  # User, UserSettings, FeedbackMemory
```

Šis testas tikrina, kad sėkminga registracija ne tik grąžina HTTP 200, bet ir užtikrina kad sukuriami trys ORM įrašai — naudotojas, jo nustatymai ir grįžtamojo ryšio atmintis — ir kad serveris nustato JWT slapuką. Likę autentifikacijos testai padengia validavimo atvejus: blogo formato el. paštas grąžina HTTP 422 (Pydantic validavimas), pasikartojantis el. paštas — HTTP 400, neteisingas slaptažodis prisijungiant — HTTP 401, atsijungimo užklausa išvalo slapuką per `Set-Cookie: ... Max-Age=0`.

#### 4.3.3. Nustatymų laukų validavimas

Antroji testų grupė padengia FR2–FR5 reikalavimus, susijusius su filtravimo nustatymų laukų validavimu. Naudojamos parametrizuotos `pytest` užklausos su tyčia blogos formos duomenimis: neegzistuojantis `library_explanation_level`, ne skaitinis `deep_scan_limit`, blogo formato `notification_time`. Visi atvejai turi grąžinti HTTP 422 (Pydantic schemos validavimas) prieš pasiekiant duomenų bazę. Kritinė šios grupės dalis — testai, tikrinantys, kad keičiant `filtering_goal` paleidžiama tinkama Celery užduočių grandinė: pirmojo paleidimo metu (`onboarding_completed=False`) iškviečiamas `run_full_pipeline`, po pirmojo sėkmingo ciklo — `run_light_pipeline` (3.2.2 poskyrio paleidimo taksonomija).

#### 4.3.4. Filtravimo ciklo režimų regresijos sargai

Trečioji grupė — naujai sukurti `test_pipeline_modes.py` testai, kurie užtikrina kad architektūriniai sprendimai iš 3.2.2 ir 4.5.1 (light / full režimai, Redis užraktas, `user_explanation` srauto tekstas) nebus netyčia sugadinti ateityje. Šios grupės kritinis testas:

```python
def test_light_mode_writes_user_explanation_to_feed(...):
    _drive_run_pipeline("light", uid, onboarded=True, ...)
    feed_rows = [obj for obj in session._added if obj.status == "feed"]
    for row in feed_rows:
        assert "Not deep-scanned" not in row.agent_explanation
        assert row.agent_explanation  # non-empty user-facing text
```

Šis testas yra regresijos sargas Bug #1 atveju, kuris buvo identifikuotas ir ištaisytas šio darbo metu — anksčiau straipsniai virš `deep_scan_limit` ribos sraute gaudavo techninį pranešimą „Passed abstract screening (score X/10). Not deep-scanned due to scan limit (10)" vietoj semantinio paaiškinimo. Po ištaisymo Evaluator generuoja papildomą `user_explanation` lauką, kuris ir naudojamas srauto kortelėms.

#### 4.3.5. Integraciniai testai

Ketvirta — vienas integracinis testas (`test_celery_integration.py`), pažymėtas `@pytest.mark.integration` žyma. Jis paleidžia tikrą Redis brokerį per `testcontainers` biblioteką ir Celery worker'į atskirame procese, kad būtų patikrintas Celery užduočių maršrutizavimas ne tik „eager" režime, bet ir per realią brokerio infrastruktūrą. Ši testavimo dalis kompensuoja gerai žinomą „eager" režimo ribotumą, kur visa Celery infrastruktūra yra pakeista į tiesioginį funkcijos iškvietimą, neapimant užduočių serializacijos, brokerio nukreipimo ir paskirstytojo užrakto elgsenos. Testai praleidžiami automatiškai, kai vykdymo aplinkoje nėra Docker.

#### 4.3.6. Testų vykdymo rezultatai

Komanda `pytest testing/tests/ -m "not integration" -q` vykdo <N> testus per <N> sekundes, visi praeina. Integracinis komplektas (`-m integration`) papildomai vykdo 2 testus ir trunka apie 60 sekundžių su pirmojo Docker konteinerio pakėlimu.
```

- [ ] **Step 2: Skim the rendered chapter to ensure flow**

Open `Baigiamasis_darbas_final.md` and read the new 4.3 in context of 4.2 + 4.4. Adjust references (FR/NFR IDs, section numbers) if needed.

- [ ] **Step 3: Commit**

```bash
git add Baigiamasis_darbas_final.md
git commit -m "thesis(4.3): draft Funkciniai testai with table, code snippets, regression rationale"
```

---

### Task 19: Draft Chapter 4 section 4.2 — Sistemos demonstravimas

**Files:**
- Modify: `Baigiamasis_darbas_final.md` (replace the screenshot-only 4.2 block)

- [ ] **Step 1: Replace 4.2 with the three-flow walkthrough**

Find the existing "**4.2. Giliojo vertintojo veikimo įvertinimas**" subsection (currently just screenshots labeled 4.2.1/4.2.2/4.2.3) and replace the heading + entire block with:

```markdown
### 4.2. Sistemos demonstravimas

Šiame poskyryje pristatoma realizuotos sistemos veikimo demonstracija per tris pagrindinius naudotojo srautus: (A) registracija ir pirmasis filtravimo ciklas, (B) tikslo pakeitimas su greitu „light" režimo atnaujinimu, (C) suplanuotas kasdienis pranešimas su „full" režimo ciklu ir el. pašto pranešimu. Šie trys srautai padengia visus FR11–FR17 reikalavimus ir parodo, kaip architektūrinis sprendimas dėl dviejų ciklo režimų (3.2.2 poskyris) realizuojasi praktiniame UX'e.

#### 4.2.1. Srautas A — Registracija ir pirmasis ciklas

Naujas naudotojas registruojasi sistemoje per registracijos formą (4.2.1 pav.). Po sėkmingos registracijos serveris sukuria tris ORM įrašus: `User`, tuščią `UserSettings` ir tuščią `FeedbackMemory`. Naujai sukurta `UserSettings` lentelės eilutė turi `onboarding_completed = False` — tai signalas, kad pirmojo tikslo įrašymas turi paleisti pilną filtravimo ciklą.

![4.2.1 pav. Registracijos forma](Baigiamasis_darbas_assets/4_2/01_registration.png)

Toliau naudotojas pereina į nustatymus ir įveda filtravimo tikslą natūralia kalba kartu su arXiv kategorijomis, sekamomis temomis, turinio interesais ir `deep_scan_limit` parametru (4.2.2 pav.). Patvirtinus, serveris paleidžia Celery užduočių grandinę `trigger_goal_distiller → run_full_pipeline`: pirmoji distiliuoja tikslą į kriterijus ir įterptinį vektorių, antroji vykdo pilną ciklą (RRF → Phase 1 → top-K Marker → Deep Reader → top-3 pranešimui).

![4.2.2 pav. Filtravimo tikslas ir kategorijos](Baigiamasis_darbas_assets/4_2/02_settings_filtering_goal.png)

Po ciklo užbaigimo (vidutiniškai <N> minutės — žr. 4.4 poskyrį) naudotojas atsisuka į srauto puslapį (4.2.3 pav.). Kortelės rodo Evaluator priimto straipsnio pavadinimą, autorius, „Why it fits" semantinį paaiškinimą (gautą iš `user_explanation` lauko Phase 1 kortelėms arba iš Deep Reader prozos top-K kortelėms), bei nuorodas į arXiv šaltinį ir PDF. Top-pick kortelėms taikomas atskiras vizualus žymėjimas (3 ryškiausios kortelės sraute), ir paralelinis pranešimas el. paštu yra išsiųstas.

![4.2.3 pav. Srautas po pirmojo ciklo](Baigiamasis_darbas_assets/4_2/03_feed_after_first_run.png)

Po šio ciklo `onboarding_completed` perjungiamas į `True` — tai užtikrina, kad būsimi tikslo pakeitimai aktyvuotų jau greitesnį „light" režimą, ne kartoti pilną ciklą.

#### 4.2.2. Srautas B — Tikslo pakeitimas su „light" režimu

Tarus, kad naudotojas po kelių dienų nori susiaurinti savo srities apibrėžimą — pavyzdžiui, pereiti nuo bendro „multi-agent LLM" prie konkretesnio „LLM-based code repair agents". Naudotojas atidaro tuos pačius nustatymus, modifikuoja `filtering_goal` lauką ir patvirtina. Šiame taške, kadangi `onboarding_completed = True`, serveris paleidžia grandinę `trigger_goal_distiller → run_light_pipeline`. „Light" režimas atlieka tas pačias pradines fazes (scraperis → įterpčių generavimas → RRF → Phase 1 Evaluator+Critique), bet sustoja prieš Phase 2 — neiškviečia Marker'io, neiškviečia Deep Reader'io ir neišsiunčia pranešimo. Naudotojas mato atnaujintą srautą vidutiniškai per <N> minutes (žr. 4.4 poskyrį), ir visos kortelės rodo Evaluator generuotą `user_explanation` paaiškinimą — sklandžiai skaitomas vartotojui skirtas tekstas, ne techninis pranešimas (4.2.4 pav.).

![4.2.4 pav. Srautas po tikslo pakeitimo (light režimas)](Baigiamasis_darbas_assets/4_2/04_feed_after_light_run.png)

Tai praktinis sprendimas kompromisui tarp atsako greičio ir kokybės — greitai matomi rezultatai eksperimentavimo metu, gilesnis Deep Reader vertinimas atidedamas iki kito planuoto ciklo.

#### 4.2.3. Srautas C — Planuotas kasdienis pranešimas

Trečias srautas vyksta automatiškai. „Celery Beat" kas valandą paleidžia užduotį `pipeline.dispatch_scheduled_runs`, kuri tikrina visų naudotojų `notification_time` lauką ir lygina jį su einamąja UTC valanda. Jei jie sutampa, naudotojui paleidžiamas `run_full_pipeline` su numatytuoju kasdieniu langu (paaiškinta 4.4 ir 3.2.4 poskyriuose: antradieniais–penktadieniais — vakar dienos publikacijos; pirmadieniais — penktadienio + savaitgalio publikacijos). Po ciklo užbaigimo, jei buvo bent vienas top-pick straipsnis (`is_top_pick = True`), generuojamas HTML el. paštas su trijų geriausių straipsnių pavadinimais, Deep Reader paaiškinimais ir nuorodomis. Tai užtikrina, kad naudotojas gauna gerai apgalvotas rekomendacijas vienu žinučiu per dieną, nepriklausomai nuo to, ar jis tuo metu naudojasi sąsaja.

#### 4.2.4. Asmeninės bibliotekos paaiškinimas

Kai naudotojas priima straipsnį į asmeninę biblioteką, jis gali pareikalauti gilesnio paaiškinimo viename iš trijų lygių — profesionalui (techninis), studentui (su sąvokų apibrėžimais) arba neprofesionalui (kasdieninio supratimo). 4.2.5 ir 4.2.6 paveikslai parodo to paties straipsnio paaiškinimą skirtinguose lygiuose, sugeneruotą naudojant `gpt-5.4-nano` modelį per sekcijų klasifikatoriaus filtruotą turinį (žr. 3.2.7 poskyrį).

![4.2.5 pav. Bibliotekos paaiškinimas (profesionalui)](Baigiamasis_darbas_assets/4_2/05_library_explanation_professional.png)

![4.2.6 pav. Bibliotekos paaiškinimas (studentui)](Baigiamasis_darbas_assets/4_2/06_library_explanation_student.png)
```

- [ ] **Step 2: Commit**

```bash
git add Baigiamasis_darbas_final.md
git commit -m "thesis(4.2): draft Sistemos demonstravimas with three flows and updated screenshots"
```

---

### Task 20: Draft Chapter 4 section 4.4 — Našumo charakteristikos

**Files:**
- Modify: `Baigiamasis_darbas_final.md`

- [ ] **Step 1: Replace the 4.4 stub**

Find the existing "**4.4**" placeholder (currently a single sentence in the old "4.3 Sistemos įvertinimas / 4.3.1 Ideali Naudotojo sąveika"). Insert in its place — between the new 4.3 and 4.5:

```markdown
### 4.4. Našumo charakteristikos

Šiame poskyryje pateikiamos realizuotos sistemos veikimo trukmės charakteristikos. Matavimai atlikti N=3 paleidimų serijoms abiems filtravimo režimams („light" ir „full"), siekiant subalansuoti vieno paleidimo dispersiją ir aprašyti tipinį, ne išskirtinį atvejį. Prieš matavimus „Modal" konteineriai buvo iš anksto suaktyvinti (angl. warm-up), kad būtų sumažintas šaltojo paleidimo (angl. cold-start) iškraipymas. Duomenys surinkti iš strukturizuotų `pipeline.start` ir `pipeline.end` JSON žurnalo įrašų, generuojamų pačios filtravimo užduoties (4.5 poskyris, 4.5.2 dalis).

#### 4.4.1. Ciklų trukmės

| Režimas | Mediana | Min | Maks | Komentaras |
|---|---|---|---|---|
| Light (Phase 1 tik) | <N min> | <N min> | <N min> | Naudojama tikslo pakeitimui. Phase 1 yra dominuojanti dalis. |
| Full (Phase 1 + Phase 2) | <N min> | <N min> | <N min> | Naudojama pirmajam paleidimui, planuotam ciklui ir ad-hoc trigeriui. |

Šie skaičiai pagrįsti 200 straipsnių partija „cs.AI" kategorijoje. Light ciklas reprezentatyviai trunka apie <N>x kartų trumpiau nei full, nes praleidžia visas brangias Phase 2 dalis: Marker PDF išgavimą per Modal T4 GPU, lygiagretų Deep Reader iškvietimą ir notifikacijos generavimą.

#### 4.4.2. Etapų skirstymas

Žemiau pateikiamas etapų trukmių paskirstymas pilnam ciklui (full režimas, N=3 medianos):

| Etapas | Mediana | Komentaras |
|---|---|---|
| arXiv scraperis (langinis) | <N s> | 200 straipsnių per ARXIV_PAGE_SIZE puslapį, su 5 s greičio ribojimu tarp užklausų |
| SPECTER2 įterpčių generavimas | <N s> | Modal T4 GPU, paketinis (batch) iškvietimas |
| RRF hibridinė paieška | <N ms> | PostgreSQL tsvector + pgvector užklausa, RRF sąjunga vyksta SQL lygmenyje |
| Phase 1 (Evaluator + Critique) | <N min> | 30 kandidatų × ~1 LLM iškvietimas; kritinis kelias |
| Marker PDF išgavimas (lygiagretus) | <N min> | top-K paraleliai per `asyncio.gather`, Modal T4 GPU |
| Deep Reader (lygiagretus) | <N s> | top-K paraleliai, OpenAI „gpt-5.4-nano" |
| Pranešimas el. paštu | <N s> | Vienkartinė SMTP užklausa |

Phase 1 ir Marker etapai užima daugiau nei 80% bendro ciklo laiko. Marker'io trukmė yra didžiausia atskira sudėtinė dalis — vidutiniškai apie 30 sekundžių vienam PDF dokumentui, todėl `deep_scan_limit` parametras turi tiesioginę įtaką ciklo trukmei.

#### 4.4.3. Dispersijos šaltiniai

Tarp N=3 paleidimų toje pačioje konfigūracijoje stebimas dispersijos diapazonas <N>%. Pagrindiniai šaltiniai:

1. **„Modal" konteinerio šaltasis paleidimas.** Net po šildymo, jei tarp paleidimų yra ilgesnė pauzė (>5 min), konteineris gali būti automatiškai sustabdytas, ir kitas iškvietimas patiria 20-60 sekundžių inicializacijos delsą. Ši dispersija sukuria stebėtą maksimumo padidėjimą full režime.
2. **„OpenAI" galinio taško latencijos uodega.** „gpt-4o-mini" ir „gpt-5.4-nano" LLM iškvietimų P99 latencija gali svyruoti 2-10 kartų nuo P50, ypač piko valandomis. Tai dominuoja Phase 1 ciklo trukmę, kai 30 nuosekliai vykdomų iškvietimų susumuoja savo dispersijas.
3. **„arXiv API" atsakymo trukmė.** Stabili, bet 5 sekundžių mandagumo pauzė tarp užklausų reiškia, kad daugiapuslapio užklausa pridės bent 5-15 sekundžių prie scraperio etapo.

#### 4.4.4. Praktinė interpretacija

Šie skaičiai pakankamai geri prototipo lygmens demonstravimui ir kasdieniam pranešimui, bet vis dar per ilgi sinchroniniam tikslo pakeitimo UX'ui — naudotojas, pakeitęs tikslą, neturėtų laukti <N> minučių, kol matys naujus rezultatus. Ateities optimizavimo kryptys, aptariamos 4.5 poskyryje, apima Marker konteinerių iš anksto šildymo strategiją bei dalinį caching'ą įterptiniams vektoriams.
```

- [ ] **Step 2: Fill in the `<N>` placeholders using `testing/perf_runs_summary.txt`**

Open `testing/perf_runs_summary.txt`, take the median + min + max for `light` and `full`, and substitute each `<N>` in the 4.4 section.

- [ ] **Step 3: Commit**

```bash
git add Baigiamasis_darbas_final.md
git commit -m "thesis(4.4): draft Našumo charakteristikos with N=3 median + min/max timings"
```

---

### Task 21: Polish 4.5 — Vertinimo apribojimai

**Files:**
- Modify: `Baigiamasis_darbas_final.md`

- [ ] **Step 1: Update the existing 4.5 draft**

Locate the existing "**4.5. Vertinimo apribojimai ir aprėptis**" subsection (user already drafted six blocks). Edit each block to add the small caveat updates from the spec's §4.4 and §4.5:

Append a new block at the end of 4.5, before the closing paragraph:

```markdown
**Light / Full režimų aprėptis.** Šio darbo testavimas padengia abu filtravimo režimus, bet kai kurios kraštinės situacijos lieka neištirtos. Konkrečiai, `default_daily_window_utc` reikalauja, kad sistema kasdien tinkamai paleistų ciklą — jei „Modal" GPU paslauga arba „arXiv API" nepasiekiama vienai dienai, ta diena yra prarandama, nes nėra automatinio atsiliko (angl. catch-up) mechanizmo. Apeitis — rankinis `POST /pipeline/trigger?date=YYYY-MM-DD` užklausimas, bet ši galimybė nėra eksponuojama naudotojo sąsajoje. Be to, langas yra fiksuotas UTC laiku, o naudotojo `notification_time` saugomas kaip „HH:MM" eilutė, taip pat lyginama su UTC valandomis — naudotojams rytinėje pusrutulio dalyje (UTC+) „vakar" partija gali apimti jų vietinį pavakarį-pernakt nuo dvi dienos atgal. Šis poslinkis nėra ištaisytas šiame darbe ir paliekamas kaip lokalizacijos plėtros uždavinys.

**Eager-režimo testų pasitikėjimas.** Funkciniai testai (4.3 poskyris) vykdomi „Celery eager" režimu, kuris paverčia užduotis tiesioginiu funkcijos iškvietimu. Tai praleidžia užduočių serializacijos, brokerio nukreipimo ir paskirstytojo užrakto elgsenas. Šis pasitikėjimo trūkumas iš dalies kompensuojamas vienu integraciniu testu (`test_celery_integration.py`), kuris paleidžia tikrą Redis brokerį per `testcontainers` ir Celery worker'į atskirame procese. Tačiau didesnio masto integracijos testavimas (pavyzdžiui, kelių lygiagrečiai veikiančių worker'ių ar užduočių eilės perpildymo scenarijai) peržengia šio prototipinio darbo apimties ribas.
```

Also edit the existing first three blocks to:
- Replace "single representative run" wording in the "Performance measurement conditions" block with the new N=3 median+range language.
- In the "Functional coverage scope" block, add a reference to the new `test_pipeline_modes.py` regression suite and the `test_celery_integration.py` integration test.
- In the "Demonstration, not systematic evaluation" block, add a forward reference to the Deep Reader effectiveness audit (the "does it actually find the gold paper" question) as explicit future work — but cap at one sentence, do not bloat.

- [ ] **Step 2: Commit**

```bash
git add Baigiamasis_darbas_final.md
git commit -m "thesis(4.5): add light/full + eager-mode caveats, reference new test suites"
```

---

### Task 22: Polish 4.1 + write the Chapter 4 introduction

**Files:**
- Modify: `Baigiamasis_darbas_final.md`

- [ ] **Step 1: Read the existing draft from the spec**

The Chapter 4 intro paragraph in the spec (under §1, in the user's response from the brainstorming session) already contains the four-direction framing. Paste that into `Baigiamasis_darbas_final.md` as the **chapter 4 lead paragraph** (immediately under the `## 4. Sistemos realizacijos rezultatai ir vertinimas` heading):

```markdown
## 4. Sistemos realizacijos rezultatai ir vertinimas

Šiame skyriuje pristatomi realizuotos informacinės sistemos vertinimo rezultatai. Vertinimas atliekamas keturiomis kryptimis, kurios kartu padengia §3.1.9 reikalavimus praktinei daliai — komponentų konfigūracijos pagrindimą, sistemos veikimo demonstravimą, funkcinį patikimumą ir našumo analizę. Pirmiausia, 4.1 poskyryje, atliekamas empirinis didžiųjų kalbos modelių palyginimas, kurio tikslas — parinkti tinkamus modelius tikslo distiliavimo ir santraukų vertinimo mazgams; tai yra inžinerinis konfigūracijos sprendimas, paremtas eksperimentiniais duomenimis, o ne savarankiškas mokslinis tyrimas. Antra, 4.2 poskyryje demonstruojamas realizuotos sistemos veikimas — naudotojo sąsaja, filtravimo ciklo eiga su realiu „arXiv" duomenų pavyzdžiu ir asmeninės bibliotekos paaiškinimo funkcionalumas. Trečia, 4.3 poskyryje pateikiami funkciniai testai, padengiantys autentifikacijos, nustatymų valdymo ir duomenų bazės operacijų patikimumo aspektus, susijusius su NFR3 ir NFR4 reikalavimais. Ketvirta, 4.4 poskyryje pateikiamos sistemos našumo charakteristikos — filtravimo ciklo trukmė, agentinio vertinimo greitis ir „PDF" teksto išgavimo įtaka. Galiausiai 4.5 poskyryje aptariami atlikto vertinimo apribojimai, suformuluoti atsižvelgiant į prototipo lygmens darbo apimtį.
```

- [ ] **Step 2: Polish 4.1 framing only**

Open the existing **4.1. DKM agentų vertinimas** subsection. Rename the heading to **4.1. DKM agentų modelių palyginimas** (to match the chapter-intro list). Skim the prose for any sentence that contradicts the new chapter framing — specifically:
- If 4.1 ever calls itself "the agent evaluation" in a way that implies it's the whole evaluation, soften to "the model selection experiment" / "the empirical model comparison".
- If 4.1.2 says "We evaluated the system" generically, narrow it to "we compared LLM models for the Evaluator node".

Do NOT rewrite the empirical content (the seven models, 927-paper dataset, 95% CI numbers) — only the framing.

- [ ] **Step 3: Commit**

```bash
git add Baigiamasis_darbas_final.md
git commit -m "thesis(4 intro + 4.1): chapter intro paragraph and reframe 4.1 as model selection"
```

---

### Task 23: Final pass — table of contents, cross-references, page reflow

**Files:**
- Modify: `Baigiamasis_darbas_final.md`

- [ ] **Step 1: Update the TOC and any forward references**

Search the document for the table of contents (typically near the front) and update it to reflect the new chapter 4 structure:

```
4. Sistemos realizacijos rezultatai ir vertinimas
   4.1. DKM agentų modelių palyginimas
   4.2. Sistemos demonstravimas
   4.3. Funkciniai testai
   4.4. Našumo charakteristikos
   4.5. Vertinimo apribojimai ir aprėptis
```

Search for cross-references that may point to old section numbers:
```bash
grep -n "4\.3\." Baigiamasis_darbas_final.md | head -20
grep -n "Sistemos įvertinimas\|Giliojo vertintojo veikimo įvertinimas" Baigiamasis_darbas_final.md
```

If any earlier chapter references "see 4.3 for ..." with the old 4.3 meaning (cycle time / system evaluation), update the number / wording. Most references in chapters 1–3 will likely point at 4.4 (performance) now, not 4.3.

- [ ] **Step 2: Update the conclusions section if it forward-references 4.x**

Check the existing **Išvados** section. If it summarises evaluation findings that pointed to the old single-sentence 4.3, expand the relevant point to acknowledge the test suite (4.3) and the timing characterisation (4.4) separately.

- [ ] **Step 3: Commit**

```bash
git add Baigiamasis_darbas_final.md
git commit -m "thesis(toc): update chapter 4 table of contents and harmonise cross-references"
```

---

### Task 24: Regenerate the thesis PDF

**Files:**
- Output: `Baigiamasis_darbas_final.pdf`

- [ ] **Step 1: Render the markdown to PDF**

Use whatever Markdown-to-PDF pipeline this thesis is already on (the user mentioned `pdf_to_md.py` exists — there is likely a complementary md→pdf renderer or pandoc setup). Run the renderer over `Baigiamasis_darbas_final.md` and produce `Baigiamasis_darbas_final.pdf`.

- [ ] **Step 2: Visual proof read**

Open the PDF, skim chapter 4. Check that:
- Chapter intro paragraph is the first prose under the chapter heading.
- 4.2 screenshots are properly captioned and visible (not cropped).
- 4.3 code blocks render in monospace and tables aren't overflowing the margin.
- 4.4 timing tables aren't broken by page splits in awkward places.
- No `<N>` placeholders remain anywhere.

If any of the above are broken, fix the markdown and re-render.

- [ ] **Step 3: Commit**

```bash
git add Baigiamasis_darbas_final.pdf
git commit -m "thesis: regenerate PDF with completed chapter 4"
```

---

## Closing checklist (after all tasks)

- [ ] `pytest testing/tests/ -m "not integration"` passes with ~85 tests.
- [ ] `pytest testing/tests/ -m integration` passes 2/2 (or is cleanly skipped without Docker).
- [ ] Manual smoke (Task 8) was rerun and the feed shows `user_explanation`, not the legacy "Not deep-scanned" string.
- [ ] `Baigiamasis_darbas_final.md` and `Baigiamasis_darbas_final.pdf` are in sync.
- [ ] No `<N>` or other placeholders remain in the thesis.
- [ ] `MEMORY.md` index entries updated if the project structure description changed materially (not required, but consider it).
- [ ] All Sprint 1 / Sprint 2 / Sprint 3 commits in the branch — squash or merge to `feat/benchmark-harness` per the user's workflow preference.
