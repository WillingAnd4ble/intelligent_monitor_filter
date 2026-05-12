# Thesis Chapter 4 — Finish Design (System Fixes + Tests + Writing)

**Date**: 2026-05-12
**Status**: Approved by user (awaiting written-spec review)
**Branch**: feat/benchmark-harness (current)
**Scope**: Final pre-defense sprint — fix three concrete pipeline issues, write functional test suite for the system flow they touch, and complete the four remaining subsections of Chapter 4 of the thesis.

---

## 1. Context

The thesis project is an agent-based information system that filters and recommends arXiv publications according to a user-defined goal. Backend (FastAPI + LangGraph + Celery + Postgres/pgvector), web UI (Next.js), and a Modal GPU service for SPECTER2 embeddings and Marker PDF extraction are in place. Streamlit benchmark harness lives on this branch.

Thesis writing is ~70% drafted. Chapters 1–3 are complete. Chapter 4 currently exists in the file `Baigiamasis_darbas_final.md` (PDF: `Baigiamasis_darbas_05_09_1800.pdf`) in this shape:

- 4.1 DKM agentų vertinimas — written
- 4.2 Giliojo vertintojo veikimo įvertinimas — only screenshots (no prose)
- 4.3 Sistemos įvertinimas — one sentence about cycle time
- Išvados — written

The thesis advisor's note: 4.2 should not look like Chapter 3 (architectural design) — it should be a **system presentation** chapter, and after it a **testing chapter** with unit tests, automated tests, and tests for form input / registration.

The user has confirmed the target structure:

```
4. Sistemos realizacijos rezultatai ir vertinimas
  4.1  DKM agentų modelių palyginimas              (existing, polish only)
  4.2  Sistemos demonstravimas                     (rewrite from screenshots → walkthrough)
  4.3  Funkciniai testai                           (NEW — replaces "Testavimas")
  4.4  Našumo charakteristikos                     (expand current 4.3 stub)
  4.5  Vertinimo apribojimai ir aprėptis           (user has a strong draft)
```

The user also reported three concrete system issues found by reasoning about the code path:

1. On first run after registration, the feed shows hardcoded text *"Passed abstract screening (score: X/10). Not deep-scanned due to scan limit (10)"* instead of a real semantic explanation.
2. The arXiv scraper was refactored to support `since/until` windows, but `celery_app.py` ignores those parameters and just fetches the last 200 papers. The intended "yesterday / Mon picks Fri+Sat+Sun" logic is missing.
3. The post-RRF cascade flow is not finalised — specifically, the trigger model is muddled (no auto-run after registration, settings save does only the GoalDistiller, scheduler runs the full pipeline, etc.).

The work order was confirmed: **Audit → Fix → Test → Write**. Audit is complete (see §3 below); the rest of this document is the design for Fix, Test, Write.

## 2. Goals and non-goals

**Goals**
- Make first-run UX correct: feed text reflects a real semantic reason, not a technical fallback string.
- Wire the date-windowed arXiv fetch and add a small weekend rule so daily fetches are bounded to "yesterday's submissions".
- Cleanly split the pipeline into a light variant (Phase 1 only) and a full variant (Phase 1 + Phase 2 + notifications) and route triggers correctly.
- Ship a functional test suite that covers auth/registration, settings CRUD/validation, and an end-to-end pipeline flow, in addition to the existing 48 unit tests for agents/retrieval/scraper.
- Finish Chapter 4 (sections 4.2, 4.3, 4.4) of the thesis with prose grounded in the fixed system and the test counts produced by the new suite.

**Non-goals (out of scope for this sprint)**
- Deep Reader effectiveness audit ("does the model actually find the gold paper, is scoring useful, would personalisation help"). Important question — recorded in §4.5 as future work.
- Direct head-to-head benchmark against Scholar Inbox or other live systems. Already addressed in §2.6 of the thesis as an indirect comparison.
- Multi-day evaluation rounds with independent labelers. Discussed in §4.5 as a limitation.
- Frontend polish unrelated to the affected flow (pagination, password-change form, "Explained" badge).
- Merging `feat/benchmark-harness` to `main`.

## 3. Audit findings (concrete code locations)

Files referenced are in `backend/` unless otherwise noted.

**A. Registration creates auth-only state**
`app/api/v1/endpoints/auth.py` (lines 15–51) creates the user row plus blank `UserSettings` and `FeedbackMemory` rows. No pipeline is triggered. This is correct because there are no settings yet — there is nothing to filter against at register time.

**B. Settings save runs GoalDistiller, nothing else**
`app/api/v1/endpoints/settings.py:55-57` calls `trigger_goal_distiller.delay(str(user.id))` after `filtering_goal` is updated. No pipeline is queued. First-time users have to either manually hit `POST /pipeline/trigger` or wait for the hourly Celery Beat scheduler. This is the root of the "I save my goal and nothing happens" complaint.

**C. Hardcoded fallback for papers beyond `deep_scan_limit`**
`app/worker/celery_app.py:275-288` — Phase 1 results are sorted by `evaluator_score` and the top K (K = `deep_scan_limit or 10`) are routed to Marker + Deep Reader. Papers in positions K+1..N are written straight to the feed with:

```python
agent_explanation=f"Passed abstract screening (score: {state.get('evaluator_score', 0):.1f}/10). "
                  f"Not deep-scanned due to scan limit ({deep_scan_limit}).",
```

On a typical first run, RRF returns 30 candidates, ~25 pass Phase 1, and 15+ of those papers land in the feed with this technical message. This is exactly what the user reports.

The fix is cheap: the Evaluator already produces a `reasonbook` string when it accepts a paper. Use it.

**D. arXiv scraper refactored but date params unused**
`app/worker/arxiv_scraper.py` (modified vs `main`) supports `fetch_arxiv_papers(query, since, until, max_results)` and exposes `ARXIV_PAGE_SIZE = 200` / `ARXIV_WINDOW_HARD_CAP = 5000`. But `app/worker/celery_app.py:164` calls `fetch_arxiv_papers(cat_query, max_results=200)` — no `since`, no `until`. The "yesterday only / weekend rule" the user remembers writing is not in the code at all.

**E. Feed display is fine**
`app/api/v1/endpoints/feed.py` returns `agent_explanation`; `web_ui/components/feed/PaperCard.tsx:65-70` renders it under "Why it fits". Garbage in, garbage out — fixing (C) fixes the visible bug.

**F. test_api.py cannot be imported**
The test file exists but fails at collection time with `ModuleNotFoundError: No module named 'bcrypt'`. Probably a missing dependency in the testing venv or a pythonpath issue between `testing/` and `backend/`. Needs a small repro before Sprint 2.

## 4. Architectural design

### 4.1 Pipeline modes

Split today's single Celery task into two:

```
run_light_pipeline(user_id):
    scrape (default daily window) → ingest+embed → RRF top-30
    → Phase 1 (Evaluator + Critique on borderline)
    → write accepted papers to feed with agent_explanation = user_explanation
      (see §4.3 — Evaluator now emits a user-facing field alongside reasonbook)
    → STOP

run_full_pipeline(user_id):
    run_light_pipeline body
    → take top K=deep_scan_limit by evaluator_score
    → parallel Marker + Deep Reader
    → overwrite agent_explanation with Deep Reader explanation for top-K
    → mark top-3 as is_top_pick
    → send notification (email / Slack)
    → on success: set UserSettings.onboarding_completed = True
```

Light pipeline is a strict prefix of full pipeline; refactor by extracting the shared body and adding a `mode: Literal["light", "full"]` parameter to the existing Celery task, then keep one task with internal branching (simpler than two parallel tasks). Public name in `tasks.py` remains; thin wrappers `run_light_pipeline.delay(uid)` and `run_full_pipeline.delay(uid)` for clarity at call sites.

### 4.2 Trigger taxonomy

First-run detection uses a dedicated `onboarding_completed: bool` flag on `UserSettings` (default `False`, flipped to `True` at the end of the first successful full run). Branching on "is `distilled_criteria` empty" is brittle — a failed GoalDistiller leaves the field empty, so a user re-saving would trigger another full pipeline + notification, every time. The dedicated flag is the only reliable signal. Adds one Alembic migration.

| Trigger source | Effect |
|---|---|
| `POST /auth/register` | No pipeline. (No settings yet.) |
| `POST /settings` when `onboarding_completed = False` | After GoalDistiller finishes, run **full** pipeline once. On success, set `onboarding_completed = True`. |
| `POST /settings` when `onboarding_completed = True` (goal change) | After GoalDistiller finishes, run **light** pipeline. No notification. |
| Celery Beat hourly tick, user's `notification_time` matches | Run **full** pipeline. Send notification. |
| `POST /pipeline/trigger` (power-user / ad-hoc) | Run **full** pipeline. Optional `?date=YYYY-MM-DD` to override the daily window. Keep existing behaviour. |

Chain the GoalDistiller and the pipeline run with Celery `chain(..., immutable=True)` so the pipeline only starts after `distilled_criteria` and `goal_embedding` are persisted.

**Race condition.** A user double-clicking Save would queue two chains. Mitigation: wrap pipeline triggers in a per-user Redis lock with a TTL (e.g., 15 min), acquired at the start of `_run_pipeline` and released at end. If a second trigger arrives while the first holds the lock, drop it silently and log. Not thesis-visible, but a real production concern; document in code, mention in §4.5 limitations only if the test we plan to write surfaces it (it might not, since eager mode serialises).

### 4.3 Fallback explanation (Bug #1)

The naive fix — using `reasonbook` directly — leaks an internal samprotavimo žurnalas (often starts with "The paper discusses..." or "Accept because...") into the user-facing feed, while Deep Reader's top-K cards carry a polished 2–3 sentence "Why this matches your interest in X" string. The stylistic gap is visible and ugly.

Fix at the schema layer: extend `EvaluatorOutput` (in `app/agents/schemas.py`) with a second field generated by the same LLM call.

```python
class EvaluatorOutput(BaseModel):
    decision: Literal["accept", "borderline", "reject"]
    score: float
    reasonbook: str          # internal — for Critic, for debugging
    user_explanation: str    # NEW — 2–3 sentences, user-facing, same tone as Deep Reader
```

Update the Evaluator prompt to require both fields. The structured-output contract guarantees the model emits them in one call, so cost stays effectively unchanged (slightly more output tokens).

In the Celery task, for papers in positions K+1..N after Phase 1 sort:

```python
agent_explanation = (
    state.get("user_explanation", "").strip()
    or f"Passed abstract screening (score: {score:.1f}/10)."
)
```

Empty-`user_explanation` fallback keeps the old message as a defensive default. Deep Reader still overwrites `agent_explanation` for top-K papers in `run_full_pipeline`, so for full runs nothing changes downstream and the visible feed is uniformly user-facing prose.

### 4.4 Daily window helper (Bug #2)

New helper in `app/worker/arxiv_scraper.py`:

```python
def default_daily_window_utc(now: datetime | None = None) -> tuple[datetime, datetime]:
    """
    Default (since, until) UTC half-open window for the daily fetch:
      Tue–Fri: yesterday 00:00 → yesterday 23:59:59
      Sat–Mon: Friday 00:00 → Sunday 23:59:59  (covers weekend arXiv quiet period)
    Caller can pass their own since/until to override.
    """
```

The `_run_pipeline(user_id, mode, *, since=None, until=None)` Celery task accepts an optional override; `POST /pipeline/trigger` exposes a `?date=YYYY-MM-DD` query param that builds a one-day window and passes it through. Default daily call from the scheduler uses the helper unchanged.

**Known caveats (called out in §4.5 limitations):**
- No catch-up logic. If Modal or arXiv is down for a day, that day is lost — the next run only fetches its own window. Manual `POST /pipeline/trigger?date=...` is the workaround.
- Window is UTC; `notification_time` is stored as `"HH:MM"` and matched against UTC hours by the scheduler. Users east of UTC see "yesterday" papers that overlap with their local evening of two days ago. Not fixed in this sprint — flagged in 4.5.

Wire `app/worker/celery_app.py:164` to call `fetch_arxiv_papers(cat_query, since=since, until=until, max_results=200)`.

### 4.5 Operational concerns (code-level, not thesis-visible)

**4.5.1 Single-flight per user.** Wrap `_run_pipeline` in a Redis lock keyed `pipeline:user:{user_id}` with 15-minute TTL. If acquisition fails, log and return — do not raise, do not queue a second run. Uses `redis.lock.Lock` (already a dependency via Celery's broker).

**4.5.2 Structured telemetry.** Emit a single JSON log line at task start and end:

```
{"event":"pipeline.start","user_id":"...","mode":"light|full","since":"...","until":"...","ts":...}
{"event":"pipeline.end","user_id":"...","mode":"...","duration_ms":...,"phase1_count":...,"phase2_count":...,"top_pick_count":...,"ts":...}
```

No new DB table for this sprint. For 4.4 timing measurements, the Sprint 3 step that runs the pipeline three times will tee the worker log to a file and grep for these events — sufficient for the median+range numbers we need. If post-thesis we want a UI dashboard, the same log format can be ingested into a `pipeline_runs` table later.

**4.5.3 Light mode + `deep_scan_limit`.** Light mode never enters Phase 2, so `deep_scan_limit` is silently ignored. Document this in the `_run_pipeline` docstring and the `UserSettings.deep_scan_limit` model comment. Test guard in §5.1.

## 5. Test plan (Ch 4.3 content)

Layout under `testing/tests/`. All LLM and Modal/SPECTER2 calls are mocked. DB uses an in-memory aiosqlite with Alembic-applied schema. Celery runs in eager mode.

### 5.1 New / extended test files

| File | Status | Count (target) | Coverage |
|---|---|---|---|
| `test_auth.py` | NEW | ~10 | FR1, NFR4. Register happy path; bad email → 422; weak password → 422; duplicate email → 400; login wrong creds → 401; `/auth/me` with/without cookie; logout clears cookie. |
| `test_api.py` | FIX + EXTEND | ~12 | Resolve `bcrypt` import. Then FR2–FR5: goal save triggers GoalDistiller; bad category → 422; invalid `content_interest` enum → 422; `deep_scan_limit ∉ {5,10,15}` → 422; bad `notification_time` → 422; bad `library_explanation_level` → 422; settings GET defaults. |
| `test_pipeline_modes.py` | NEW | ~7 | First-run save (`onboarding_completed=False`) → full pipeline queued + flag flipped to True; goal change save (`onboarding_completed=True`) → light pipeline; scheduler tick → full; feed rows for non-deep-scanned papers carry `user_explanation` (not the old hardcoded message); accept/reject UserPaper transitions; **`test_light_pipeline_skips_phase2`** — assert Marker + Deep Reader are never invoked in light mode regardless of `deep_scan_limit`; **`test_double_save_single_flight`** — two simultaneous saves trigger only one pipeline run (Redis lock). |
| `test_scraper.py` | EXTEND | ~3 added | `default_daily_window_utc` for Mon → Fri 00:00..Sun 23:59; Tue–Fri → yesterday-only; `fetch_arxiv_papers` honours since/until override. Use `freezegun`. |
| `test_celery_integration.py` | NEW (marked `@pytest.mark.integration`) | ~2 | Non-eager mode. Spins up a real Redis broker via `testcontainers-redis` + a real Celery worker subprocess; verifies `chain(goal_distiller, run_full_pipeline)` actually executes end-to-end with real task routing. Skipped when Docker unavailable (`pytest -m "not integration"`). |

Approximate new test count: **~32**.

### 5.2 Documented existing tests

These already exist and will be tabulated in the thesis without modification:

| File | Count | Coverage |
|---|---|---|
| `test_agents.py` | ~28 | GoalDistiller, Evaluator, Critique, PDF extractor (deprecated node — keep tests, mark legacy), Section classifier, Explainer, Ranker, routing logic. |
| `test_retrieval.py` | ~12 | RRF formula properties, hybrid search behaviour, SPECTER2 mock shape. |
| `test_scraper.py` (pre-extension) | ~9 | arXiv XML parse, rate-limit throttle, ingest_papers skip-existing. |
| `benchmark/tests/` | ~18 | Benchmark harness internals (cache, metrics, paths, pricing, runner, schemas). |

**Total after sprint**: ~85 tests. Thesis 4.3 will quote actual numbers from `pytest --collect-only` after Sprint 2.

### 5.3 Required fixtures

In `testing/tests/conftest.py`:

- `eager_celery` — set `task_always_eager=True`, `task_eager_propagates=True` for the test session.
- `mock_specter2_modal` — patch `app.worker.modal_client.specter2_embed_batch` to return random 768-d vectors derived from a hash of `(title + abstract)`.
- `mock_marker_modal` — patch the Marker call to return a short canned markdown.
- `test_user_cookie` — registers a user via the TestClient, captures the JWT cookie, exposes it as a fixture.
- `seeded_papers` — inserts a small set of arXiv papers with deterministic embeddings, used by retrieval and pipeline tests.

### 5.4 Acceptance for Sprint 2

- `pytest testing/tests/ -m "not integration" -q` reports 0 failures across the ~85 tests.
- If Docker is available on the dev machine, `pytest testing/tests/ -m integration -q` also passes (2 tests). If not, skip is acceptable and noted in 4.3 prose.
- The new `test_pipeline_modes.py::test_feed_uses_user_explanation` is the regression guard for Bug #1.
- `test_light_pipeline_skips_phase2` guards against future drift where someone re-introduces Phase 2 calls in light mode.

## 6. Writing plan (Ch 4.2, 4.3, 4.4, 4.5 prose targets)

| Subsection | Current state | Target | What it needs |
|---|---|---|---|
| 4 intro | User has a strong draft | ~200 words | Final polish only, after the rest is done. |
| 4.1 | Drafted | Light edit only | Keep, ensure framing matches the new intro. |
| 4.2 Sistemos demonstravimas | Screenshots only | ~1200–1500 words | Three flows: (A) register → first-run full pipeline, (B) goal change → light pipeline, (C) scheduled notification → full pipeline + email. New screenshots **after** Sprint 1, so the feed cards show `reasonbook` instead of the old fallback. Include one library explanation example at each of the three levels (professional / student / simplified). |
| 4.3 Funkciniai testai | Empty | ~1000–1200 words | Four subgroups (auth, settings, pipeline-modes, existing agents/retrieval/scraper) as a table with FR/NFR mapping. 1–2 code snippets with prose. Quote real `pytest` counts. |
| 4.4 Našumo charakteristikos | One sentence | ~800–1000 words | Real timings, **N=3 runs each for light and full**, report median + min/max per stage and overall. Stages: scrape, ingest+embed, RRF, Phase 1, Marker per paper, Deep Reader per paper, end-to-end. Warm Modal containers before the runs to reduce cold-start bias; explicitly state warm vs cold. Discuss what drives the variance (cold start, OpenAI tail latency). Data source: pipeline.start / pipeline.end structured logs from §4.5.2. |
| 4.5 Apribojimai | Strong draft (~700 words) | Light edit | Update the six blocks so they reference the light/full pipeline split and the test coverage table. Keep the future-work pointer to the Deep Reader effectiveness audit. |

## 7. Execution order

### Sprint 1 — Architecture + bug fixes (~2 days)
1. Reproduce `test_api.py` import failure; pin `bcrypt` in `testing/requirements.txt` or fix sys.path.
2. Alembic migration: add `onboarding_completed: bool` to `UserSettings` (default `False`).
3. `app/agents/schemas.py`: extend `EvaluatorOutput` with `user_explanation: str`. Update Evaluator prompt in `app/agents/graph.py` to produce both fields.
4. `arxiv_scraper.py`: add `default_daily_window_utc(now)` with the Mon-includes-Fri-to-Sun rule.
5. `celery_app.py`: refactor into `_run_pipeline(user_id, mode, *, since=None, until=None)`; thin wrappers `run_light_pipeline`, `run_full_pipeline`. Acquire per-user Redis lock at entry; flip `onboarding_completed = True` on successful full-mode completion.
6. `celery_app.py:164`: pass `since`/`until` from the helper (or override).
7. `celery_app.py:285-288`: switch the non-deep-scanned fallback to `state.get("user_explanation", "").strip() or <old message>`.
8. `settings.py`: branch on pre-save `user_settings.onboarding_completed` to chain `trigger_goal_distiller` → either `run_full_pipeline` (first run) or `run_light_pipeline` (goal change).
9. `pipeline.py`: accept optional `?date=YYYY-MM-DD`, validate, build a one-day window, pass to `_run_pipeline`.
10. Add structured logging at task start and end (§4.5.2).
11. Manual smoke: register a fresh user → set goal → confirm full pipeline ran, feed shows polished `user_explanation`, `onboarding_completed=True`; change goal → confirm light pipeline (Phase 1 only, no notification).

### Sprint 2 — Tests (~1–2 days)
12. Update `conftest.py` with the five fixtures (`eager_celery`, `mock_specter2_modal`, `mock_marker_modal`, `test_user_cookie`, `seeded_papers`).
13. Add `test_auth.py`.
14. Repair and extend `test_api.py`.
15. Add `test_pipeline_modes.py` — `test_feed_uses_user_explanation` and `test_light_pipeline_skips_phase2` first.
16. Extend `test_scraper.py` with the window-logic tests using `freezegun`.
17. Add `test_celery_integration.py` (testcontainers-redis, marked `@pytest.mark.integration`).
18. `pytest testing/tests/ -m "not integration" -q` clean. If Docker available, `-m integration` also clean. Record final counts.

### Sprint 3 — Writing (~2–3 days)
19. **Run pipeline N=3 times each in light and full mode** on a recent date, grep `pipeline.start`/`pipeline.end` events → median + min/max per stage → 4.4 data. Warm Modal containers first.
20. Capture new screenshots for 4.2 after Sprint 1 (feed with `user_explanation`, library explanation at three levels).
21. Draft 4.3 using real test counts and FR/NFR coverage table.
22. Draft 4.2 with the three flows; embed screenshots.
23. Draft 4.4 with measured numbers, explicitly state median + range, warm-start.
24. Polish 4.5 to reference light/full split + new caveats (no catch-up, UTC vs local, deep_scan_limit ignored in light).
25. Rewrite Ch 4 intro and harmonise 4.1.

## 8. Risks and mitigations

- **Pipeline split regressions.** The current Celery task is well-trodden code. Mitigated by adding `test_feed_uses_user_explanation`, `test_light_pipeline_skips_phase2`, and the first-run/goal-change pipeline mode tests **before** the writing sprint, so any drift fails fast.
- **Mocked-Celery test confidence.** Eager mode masks task-routing bugs. Mitigated by the new `test_celery_integration.py` (testcontainers + real Redis). If Docker isn't on the dev box at write-time, fall back to the Sprint 1 step 11 manual smoke and note the gap in 4.3.
- **Cycle-time variance.** Modal cold starts and OpenAI tail latencies can blow out 4.4 numbers. Mitigated by N=3 runs with warm containers (Sprint 3 step 19) and reporting median + range, not a single number. Cold-start is documented as a variance source in 4.4 and 4.5.
- **Schema migration risk.** Adding `onboarding_completed` to a live DB. Existing users have to be backfilled — they have already onboarded, so set `True` for any user where a paper with status `accepted` or `rejected` exists, else `False`. Include this backfill in the Alembic upgrade `op.execute(...)`.
- **EvaluatorOutput schema change.** Adding `user_explanation` could break the existing test_agents.py mocks. Sprint 2 step 14 must update the `DistilledCriteriaOutput`/`EvaluatorOutput` fakes in `test_agents.py` accordingly.
- **Writing slipping into scope creep.** Deep Reader effectiveness questions are interesting and will tempt rewrites. They are explicitly future work in 4.5; do not let them migrate into 4.2 or 4.4.

## 9. Out of scope (explicit)

- Deep Reader internal effectiveness audit (scoring usefulness, personalisation).
- Independent labelers / multi-day evaluation runs.
- Direct head-to-head Scholar Inbox comparison (already handled indirectly in §2.6).
- Frontend cleanup unrelated to the affected flow.
- Merging the benchmark harness branch to `main`.
- Power-user "manual Deep Reader run" mode — `POST /pipeline/trigger` already covers it for thesis purposes.
