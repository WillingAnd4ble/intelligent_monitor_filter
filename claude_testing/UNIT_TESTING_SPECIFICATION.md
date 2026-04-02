# Unit & Integration Testing Specification
**Project:** Agent-based Information System for Personalized arXiv Publication Monitoring

This specification establishes the rigorous code boundary tests verifying system stability dynamically without exposing the CI environment to massive LLM token liabilities.

---

## 1. Testing Subsystem Architecture
- **Framework Core:** Python `pytest`.
- **Async Environment:** `pytest-asyncio` strictly handling all FastAPI routing requests.
- **HTTP Isolation:** `unittest.mock` (or `pytest-mock`). No raw OpenAI/Anthropic/Modal network calls are permitted during standard testing.
- **PostgreSQL Sandbox:** Fast integration tests operate pointing `SQLAlchemy` directly against an isolated SQLite test database (or cleanly wiped temporary Postgres schema pre-seeded with predictable fixture data).

## 2. Agent Node Unit Boundary Tests
Unit testing LangGraph requires feeding isolated LLM string approximations confirming Pydantic boundary mapping succeeds identically.
- **`test_node_goal_distiller`**: Mocks an LLM response string. Asserts extraction correctly unpacks to the `List[str]` boundary format.
- **`test_node_evaluator_validity`**: Verifies the node successfully transforms valid evaluation JSON down into the strict `EvaluatorOutput(BaseModel)`.
- **`test_node_critique_override`**: Injects a borderline output alongside a deeply conflicting `feedback_memory` boundary array. Asserts Mock forces output `False`.
- **`test_fallback_modal_extractor`**: Forces a mock `requests.post` timeout error routing to `Modal`. Asserts function dynamically defaults local fallback tracking `pypdfium`.

## 3. Full FR Traceability Smoke Suite
A comprehensive suite mapping directly to the **18 Functional Requirements**. Each test validates API 200/202 return codes alongside verifying internal Database/Queue state mutations strictly using Python mock elements.

**Data Integrations**
- `test_fr1_arxiv_scrape`: Yields static XML mock; asserts it Upserts metadata cleanly into `papers`.
- `test_fr2_hybrid_retrieval`: Queries sandbox; asserts pure DB `ts_rank` + `pg_vector` returns valid items.

**User Subsystems**
- `test_fr3_user_auth_flow`: Tests `POST /login` maps correct JWT and flags it strictly `httpOnly; Secure`.
- `test_fr4_settings_filters`: PUT parameters into `/settings` and verifies category tracking.
- `test_fr5_distillation_trigger`: Asserting goal changes automatically dispatches the distillation queue event.

**Core User Activities**
- `test_fr6_feed_generation`: Verify `GET /feed` outputs matching dictionary sets.
- `test_fr7_library_accept`: Assert `Accept` payload forces DB status out of queue.
- `test_fr8_library_reject`: Assert `Reject` payload immediately returns instant `202 Async`.
- `test_fr9_memory_summary`: Maps the async Celery job utilizing mock strings mutating `user_preferences`.

**Paper Processing Pipelines**
- `test_fr10_pdf_local_ocr`: Evaluates dummy PDF byte array text slicing natively.
- `test_fr11_pdf_modal_ocr`: Evaluates webhook success paths natively executing marker payloads.
- `test_fr12_section_classifier`: Asserts RegEx boundary targets (`# Introduction`) isolate bytes bypassing heavy LLM loads perfectly.
- `test_fr13_evaluator_validation`: Validates pipeline mapping inputs inside the fast funnel.
- `test_fr14_critique_override_layer`: Smoke test routing mapping state tracking.
- `test_fr15_nested_explanations`: Ensures `level: student` parameter correctly routes onto caching keys avoiding duplicate computations natively.

**UI Output Rendering**
- `test_fr16_dashboard_stats`: Pings `GET /stats` asserting widget math aggregation queries accurately.
- `test_fr17_daily_email`: Asserts UI trigger dispatches the `SMTP_HOST` configuration rendering the dynamic HTML agent strings.
- `test_fr18_slack_webhook`: Asserts tracking mapping hits standard `hooks.slack.com` using the `Block Kit` validation schema formats.
