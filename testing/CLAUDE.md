# CLAUDE.md — Testing & Benchmark Engine

## Project Overview
This is the testing arm of an undergrad thesis project: an agent-based arXiv publication monitoring, filtering, and recommendation system. Your role is exclusively building the **pytest suite** and **Streamlit benchmarking tool**. Do not modify FastAPI routes, LangGraph nodes, or frontend code.

## Directory Layout
```
testing/              <--- YOU WORK HERE
├── CLAUDE.md
├── tests/                          # Pytest output goes here
├── benchmark/                      # Streamlit benchmarking tool goes here
├── evaluation_dataset.json         # Static ground-truth fixture (~100 labeled papers)
├── UNIT_TESTING_SPECIFICATION.md   # Exact test names and assertions
├── EVALUATION_BENCHMARK_SPECIFICATION.md  # 4 experiments, metrics, charts
├── API_SPECIFICATION.md            # All endpoint contracts
└── AGENT_ARCHITECTURE_SPECIFICATION.md    # Agent nodes, state, routing
```

## Hard Constraints
- **NEVER** call real Claude/Anthropic/OpenAI API in any test — mock ALL LLM calls
- **NEVER** write to the production PostgreSQL database — use pytest fixtures with SQLite
- **NEVER** import Modal.com in benchmark tool — dataset is pre-extracted JSON
- All async tests use `pytest-asyncio` with `asyncio_mode = "auto"`
- Mock target: patch at the **point of import**, not the source module

## What to Read First
1. `AGENT_ARCHITECTURE_SPECIFICATION.md` — Pydantic contracts and node I/O
2. `UNIT_TESTING_SPECIFICATION.md` — exact test names and assertions required
3. `API_SPECIFICATION.md` — endpoint shapes for TestClient tests
4. `EVALUATION_BENCHMARK_SPECIFICATION.md` — experiment configs and metrics

## Backend Reference (Read-Only)
The implemented backend lives at `../backend/` — read it to understand actual import paths and function signatures before writing mocks. **Do not modify anything there.**

Key backend files you'll need to import from or mock:
```
backend/app/agents/schemas.py       # AgentState TypedDict, EvaluatorOutput, CritiqueOutput, ExplainerOutput, RankerOutput, MemoryOutput, SectionOutput
backend/app/agents/graph.py         # LangGraph workflow: node_evaluator, node_critique, node_pdf_extractor, node_section_classifier, node_explainer, node_ranker
backend/app/agents/distiller.py     # GoalDistiller (uses ChatAnthropic claude-3-haiku)
backend/app/db/models.py            # SQLAlchemy models: User, UserSettings, Paper, UserPaper, FeedbackMemory, PaperExplanation
backend/app/db/retrieval.py         # perform_hybrid_rrf_search() — RRF combining pgvector + tsvector
backend/app/db/database.py          # AsyncSessionLocal, get_db
backend/app/api/v1/endpoints/       # auth.py, settings.py, feed.py, library.py, pipeline.py
backend/app/api/deps.py             # get_current_user (JWT cookie extraction)
backend/app/worker/celery_app.py    # Celery tasks: trigger_agent_discovery, trigger_goal_distiller, run_memory_summarizer (stub)
backend/app/worker/arxiv_scraper.py # fetch_arxiv_papers, ingest_papers, generate_mock_specter2_embedding
backend/app/core/config.py          # Pydantic Settings
backend/app/core/security.py        # JWT creation/decode, bcrypt
backend/app/schemas/api_schemas.py  # Pydantic request/response schemas
```

## Backend Implementation Status (What You're Testing Against)

### Working — Test Normally
- **Auth**: POST /auth/register, /login, /logout — JWT httpOnly cookies, bcrypt
- **Settings**: GET/PUT /api/v1/settings — full UserSettings CRUD
- **Feed**: GET /api/v1/feed — returns UserPaper records with status='feed'
- **Library**: GET /api/v1/library — returns UserPaper records with status='accepted'
- **Pipeline trigger**: POST /api/v1/pipeline/trigger — dispatches Celery task
- **GoalDistiller**: Converts filtering_goal → 3-7 boolean criteria (uses ChatAnthropic)
- **LangGraph nodes**: evaluator, critique, explainer, ranker (use ChatOpenAI gpt-4o-mini)
- **ArXiv scraper**: XML parsing from arXiv API, paper ingestion
- **RRF search**: Hybrid SQL query combining cosine similarity + ts_rank

### Mocked/Stubbed in Backend — Test the Interface, Not the Implementation
- **PDF extractor** (`node_pdf_extractor`): Returns `raw_abstract` directly — mocked, no actual PDF parsing
- **Section classifier** (`node_section_classifier`): Passthrough — returns `extracted_pdf_text` unchanged
- **MemorySummarizer** (`run_memory_summarizer`): Function body is `pass` — completely empty
- **SPECTER2 embeddings**: `generate_mock_specter2_embedding()` returns random 768-dim vectors
- **Feed stats**: `get_feed_stats()` returns hardcoded numbers (2500, 42, 3)

### NOT Implemented in Backend — Test Stubs or Skip
- `POST /api/v1/feed/{user_paper_id}/accept` — endpoint does not exist yet
- `POST /api/v1/feed/{user_paper_id}/reject` — endpoint does not exist yet
- `POST /api/v1/library/{user_paper_id}/explain` — endpoint does not exist yet
- `DELETE /api/v1/library/{user_paper_id}` — endpoint does not exist yet
- `GET /api/v1/pipeline/{task_id}/status` — endpoint does not exist yet
- Celery Beat scheduler (no automatic daily runs)
- Email/Slack notifications (FR17-FR18)
- Settings PUT → GoalDistiller auto-trigger (has TODO comment)

## Required Test Suite (from UNIT_TESTING_SPECIFICATION.md)

### FR Smoke Tests (18 tests)
| Test | What It Validates |
|------|-------------------|
| FR1: test_arxiv_scrape | ArXiv XML fetch returns valid Paper objects |
| FR2: test_hybrid_retrieval | BM25 + pgvector RRF fusion returns ranked results |
| FR3: test_user_auth_flow | Register → login → get cookie → access protected route |
| FR4: test_settings_filters | PUT settings persists categories/topics/goal |
| FR5: test_distillation_trigger | GoalDistiller converts goal to criteria list |
| FR6: test_feed_generation | Pipeline produces UserPaper records with status='feed' |
| FR7: test_library_accept | Accept action moves paper to library (endpoint missing — stub test) |
| FR8: test_library_reject | Reject action stores comment + triggers summarizer (endpoint missing — stub test) |
| FR9: test_memory_summary | MemorySummarizer consolidates feedback (function is `pass` — mock test) |
| FR10: test_pdf_local_ocr | Local pypdfium extraction (mocked in backend) |
| FR11: test_pdf_modal_ocr | Modal.com GPU extraction (not integrated — mock test) |
| FR12: test_section_classifier | Regex + LLM section extraction (passthrough in backend — mock test) |
| FR13: test_evaluator_validation | Evaluator returns accept/borderline/reject with reasonbook |
| FR14: test_critique_override | Critique overrides borderline decisions |
| FR15: test_nested_explanations | Multi-level explanations with caching (endpoint missing — stub test) |
| FR16: test_dashboard_stats | Feed stats endpoint returns correct structure |
| FR17: test_daily_email | Email notification dispatch (not implemented — mock test) |
| FR18: test_slack_webhook | Slack webhook dispatch (not implemented — mock test) |

### Node Boundary Tests
- `test_node_goal_distiller` — Mock ChatAnthropic, verify criteria list output
- `test_node_evaluator_validity` — Mock ChatOpenAI, verify EvaluatorOutput schema
- `test_node_critique_override` — Mock ChatOpenAI, verify boolean + reasonbook
- `test_fallback_modal_extractor` — Verify fallback chain: Modal → pypdfium → abstract-only

## Benchmark Pipeline (from EVALUATION_BENCHMARK_SPECIFICATION.md)

### Tool: `benchmark/benchmark_pipeline.py` (Streamlit)
Loads `evaluation_dataset.json` (pre-extracted text, NOT raw PDFs), runs papers through the agent pipeline with mocked LLMs, and charts metrics.

### 4 Thesis Experiments
1. **Pre-Filter Retrieval Efficacy** — BM25 alone vs SPECTER2 alone vs RRF hybrid. Metrics: Precision, Recall, F1.
2. **Multi-Agent Efficacy** — Evaluator-only vs Evaluator+Critique. Metrics: F1, token cost.
3. **Longitudinal Feedback Shift** — MemorySummarizer effect over simulated cycles. Metrics: F1 drift.
4. **Context Size Economic Decay** — Cost vs F1 tradeoff at varying token limits. Metrics: F1, API cost.

### Metrics
- Precision, Recall, F1-Score (against ground-truth labels)
- Per-stage latency (ms)
- API token cost: input tokens × $0.000003, output tokens × $0.000015 (Claude Sonnet pricing)

## Conventions
- Pydantic models: import from `backend/app/agents/schemas.py` — never redefine
- API base URL: `http://testserver` via FastAPI TestClient
- Test DB: SQLite async (aiosqlite), isolated per test session
- LLM mocks: Return valid Pydantic model instances matching schema contracts
- Celery mocks: Use `unittest.mock.patch` on task `.delay()` calls
- Fixtures: Place shared fixtures in `tests/conftest.py`

## What Needs to Be Created (Nothing Exists Yet)
```
testing/
├── tests/
│   ├── conftest.py              # Fixtures: test DB, mock user, mock papers, LLM patches
│   ├── test_agents.py           # Node boundary tests (distiller, evaluator, critique, fallback)
│   ├── test_api.py              # FR1-FR18 endpoint tests via TestClient
│   └── test_db.py               # Retrieval/RRF query tests
├── benchmark/
│   ├── benchmark_pipeline.py    # Streamlit app for 4 experiments
│   └── charts/                  # Output directory for experiment visualizations
├── evaluation_dataset.json      # ~100 papers with ground-truth relevant/not-relevant labels
├── pytest.ini                   # asyncio_mode = "auto", paths
└── requirements.txt             # pytest, pytest-asyncio, aiosqlite, httpx, streamlit, matplotlib
```
