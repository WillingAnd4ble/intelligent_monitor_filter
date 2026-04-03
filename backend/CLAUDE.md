# Backend — Agent-based arXiv Filtering System

## What This Is
FastAPI backend for an undergrad thesis project: a multi-agent LLM system that monitors arXiv, filters publications based on user-defined goals, and delivers personalized recommendations. This is the API server, agent pipeline, and data layer.

## Tech Stack
- **Framework**: FastAPI (async) with Uvicorn
- **Database**: PostgreSQL 15 + pgvector extension (via docker-compose, port 5433)
- **ORM**: SQLAlchemy 2.x async (asyncpg driver)
- **Migrations**: Alembic (async)
- **Task Queue**: Celery with Redis broker/backend (port 6379)
- **Agents**: LangGraph + LangChain (claude-3-haiku for distiller, gpt-4o-mini for evaluator/critique/explainer/ranker)
- **Auth**: JWT (HS256) in httpOnly cookies, bcrypt password hashing
- **Frontend**: Next.js on localhost:3000 (CORS configured for it)

## How to Run
```bash
docker-compose up -d                    # Start Postgres + Redis
alembic upgrade head                    # Run migrations
uvicorn app.main:app --reload           # Start API server (port 8000)
celery -A app.worker.celery_app worker  # Start Celery worker (separate terminal)
```

## Project Structure
```
backend/
├── app/
│   ├── main.py                         # FastAPI app, CORS, router mounts
│   ├── core/
│   │   ├── config.py                   # Pydantic Settings (.env reader)
│   │   └── security.py                 # JWT create/decode, bcrypt hash/verify
│   ├── db/
│   │   ├── database.py                 # AsyncSession factory, engine
│   │   ├── models.py                   # 7 ORM models (User, UserSettings, Paper, UserPaper, FeedbackMemory, PaperExplanation)
│   │   └── retrieval.py                # Hybrid RRF search (pgvector cosine + tsvector lexical)
│   ├── api/
│   │   ├── deps.py                     # get_current_user dependency (cookie JWT extraction)
│   │   └── v1/endpoints/
│   │       ├── auth.py                 # POST /auth/register, /login, /logout
│   │       ├── settings.py             # GET/PUT /api/v1/settings
│   │       ├── feed.py                 # GET /api/v1/feed, /feed/stats
│   │       ├── library.py              # GET /api/v1/library
│   │       └── pipeline.py             # POST /api/v1/pipeline/trigger, GET /status, POST /cancel
│   ├── agents/
│   │   ├── schemas.py                  # AgentState TypedDict, Pydantic output models
│   │   ├── graph.py                    # LangGraph 6-node workflow (evaluator → critique → pdf_extractor → section_classifier → explainer → ranker)
│   │   └── distiller.py                # GoalDistiller — converts filtering_goal to 3-7 boolean criteria
│   ├── worker/
│   │   ├── celery_app.py               # Celery tasks + Beat scheduler: dispatch_scheduled_runs, trigger_agent_discovery, trigger_goal_distiller, run_memory_summarizer
│   │   ├── arxiv_scraper.py            # ArXiv XML API fetcher + paper ingestion (rate-limited, TSVECTOR population)
│   │   ├── notifications.py            # Email (SMTP) + Slack webhook dispatch for top-ranked papers
│   │   └── modal_client.py             # Modal GPU wrapper (SPECTER2 + Marker PDF)
│   └── schemas/
│       └── api_schemas.py              # Pydantic request/response schemas
├── alembic/                            # Migration versions (0001_pgvector, create_tables)
├── docker-compose.yml                  # Postgres 15 + pgvector, Redis 7
├── requirements.txt
├── .env                                # Local config (DO NOT commit — contains API keys)
├── seed_criteria.py                    # Manual data seeder for testing
├── fix_db.py                           # One-off fix for TSVECTOR column
├── test_endpoint.py, test_req.py       # Quick HTTP smoke tests
└── verify_papers.py                    # DB query to check paper state
```

## Functional Requirements Map (FR1-FR18)
The thesis defines 18 functional requirements. Here's backend coverage:
- **FR1-FR5** (User settings): Implemented via settings endpoints + UserSettings model
- **FR6-FR7** (Data collection): ArXiv scraper works, dedup by paper ID. Categories hardcoded to cs.AI — needs to use UserSettings.categories
- **FR8** (3-stage filtering): Stage 1 (category/keyword) partial, Stage 2 (BM25 + SPECTER2) has RRF query but mock embeddings, Stage 3 (LLM agents) implemented
- **FR9** (Structured evaluation output): AgentState captures decision, score, explanation
- **FR10** (Top picks for notifications): Ranker node scores 0-10, notifications dispatch via email/Slack for score >= 7.0
- **FR11-FR12** (Feed page): GET /feed endpoint works
- **FR13-FR14** (Accept/reject with feedback): **NOT IMPLEMENTED** — endpoints missing
- **FR15-FR16** (Library + explanations): GET /library works, explain endpoint missing
- **FR17-FR18** (Notifications): Celery Beat dispatches hourly, email (SMTP) + Slack webhook for top picks

## Database Models (app/db/models.py)
| Model | Purpose | Key Fields |
|-------|---------|------------|
| User | Auth | email, password_hash |
| UserSettings | Filtering config | categories, topics, authors, filtering_goal, distilled_criteria, library_explanation_level |
| Paper | ArXiv publications | title, abstract, authors (JSON), embedding (Vector(768)), search_vector (TSVECTOR) |
| UserPaper | User↔Paper junction | status (feed/accepted/rejected), agent_score, agent_explanation, user_comment |
| FeedbackMemory | Rejection summaries | summarized_feedback, rejection_count |
| PaperExplanation | Cached explanations | level (professional/student/kid), explanation text |

## Agent Pipeline (LangGraph)
The pipeline is defined in `app/agents/graph.py` as a StateGraph:
```
                    ┌─ accept ─→ pdf_extractor → section_classifier → explainer → ranker → END
evaluator (LLM) ───┤─ borderline ─→ critique (LLM) ──┬─ True → pdf_extractor → ...
                    └─ reject ─→ END                   └─ False → END
```

**Working nodes**: evaluator, critique, explainer, ranker (all call LLM)
**Mocked nodes**: pdf_extractor (returns abstract as-is), section_classifier (passthrough)

## What Is Working
- Auth flow (register/login/logout with JWT cookies)
- Database schema + migrations + async ORM
- User settings CRUD
- ArXiv XML parsing + paper ingestion (SPECTER2 via Modal, mock fallback) + TSVECTOR population
- ArXiv rate limiting (3.1s minimum between API requests)
- LangGraph evaluator/critique/explainer/ranker (real LLM calls)
- GoalDistiller (translates goal → criteria via Claude Haiku)
- Hybrid RRF query structure (semantic + BM25 lexical via populated TSVECTOR)
- Celery task dispatch for pipeline trigger + Beat scheduler (hourly dispatch per user notification_time)
- Notifications: email (SMTP) + Slack webhook for top-ranked papers (score >= 7.0)
- UserPaper dedup check prevents duplicate entries on pipeline re-runs
- MemorySummarizer Celery task (Claude Haiku) — consolidates rejection feedback

## What Is NOT Working / Stubbed
1. **SPECTER2 embeddings** — Mock fallback returns random vectors when `MODAL_GPU_ENABLED=False`. Real SPECTER2 requires Modal deployment.
2. **PDF extraction** — `node_pdf_extractor` and `node_section_classifier` are mocked. No Modal.com, no Marker/MinerU, no pypdfium. System evaluates abstracts only.
3. **Accept/Reject endpoints** — No `POST /feed/{id}/accept` or `/reject`. Users can't interact with papers.
4. **Library explain endpoint** — No `POST /library/{id}/explain`. Can't generate on-demand explanations.
5. **GoalDistiller auto-trigger** — Settings PUT has a TODO but doesn't trigger distiller on update.
6. **Feed stats** — `get_feed_stats()` returns hardcoded numbers, not real DB counts.
7. **Pipeline status endpoint** — `/pipeline/{task_id}/status` not implemented.

## Known Inconsistencies
- **Status mapping in celery_app.py**: evaluator accept maps to 'feed' (meaning "show in user feed"), not 'accepted'. This is intentional but confusing — 'accepted' means user explicitly accepted it.
- **Feed stats endpoint** returns static mock data (2500 scraped, 42 evaluated, 3 recommended).
- **.env contains API keys** — should be in .gitignore (OpenAI key exposed).
- **retrieval.py vector formatting**: Manual string interpolation for pgvector parameters instead of proper type binding.

## Architecture Decisions
- **httpOnly cookies** over localStorage for JWT — prevents XSS token theft
- **Reciprocal Rank Fusion** combines BM25 lexical + SPECTER2 semantic scores (k=60 constant)
- **Celery** for background tasks — pipeline runs can take minutes per user
- **pgvector** for in-database vector similarity — avoids external vector DB dependency
- **Separate GoalDistiller** — runs once when user sets goal, stores distilled_criteria for reuse

## Modal.com / PDF Pipeline (Not Yet Integrated)
The spec calls for Marker/MinerU running on Modal.com GPUs for PDF parsing. This is being built in a separate directory (`Modal + maker`). When ready, `node_pdf_extractor` should call the Modal endpoint, with pypdfium as local fallback, and abstract-only as last resort.

## Development Notes
- Windows environment — celery_app.py sets `WindowsSelectorEventLoopPolicy` for asyncio
- Postgres runs on port **5433** (not default 5432) via docker-compose
- CORS allows only localhost:3000 — update if frontend port changes
- LLM calls use langchain_openai (gpt-4o-mini) for graph nodes and langchain_anthropic (claude-3-haiku) for distiller
