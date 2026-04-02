# Architecture QA & Edge Cases Specification
**Project:** Agent-based Information System for Personalized arXiv Publication Monitoring

This document directly addresses architectural critiques, explicitly defining the resolution to problematic fields, edge cases, cost estimations, and infrastructure scaling gaps.

## 1. Resolved Specification Inconsistencies
*These items reconcile the issues identified between the DataFlow Diagrams and the Agent Logic.*

### 1.1 `PDFExtractor` & `SectionClassifier` Logic
- **Issue:** Missing formal Pydantic contracts and extraction logic.
- **Resolution:** Formalized as nodes in the daily pipeline. The `SectionClassifier` utilizes a two-tier extraction logic:
  1. **Rule-Based Fast Path:** Executes Python Regex against OCR Markdown headers (e.g., `# Introduction`, `## Methodology`) matching the user's `content_interest` array. 
  2. **LLM Fallback:** If the PDF lacks clear structural headers, it passes the text to an LLM prompted to cognitively classify and extract the requested sections into a Pydantic `SectionOutput(BaseModel)`.

### 1.2 `GoalDistiller` Execution Trigger
- **Resolution:** `GoalDistiller` is strictly a Background Standalone task fired ONLY via `/api/v1/settings`. The main daily pipeline fetches the *pre-cached* `distilled_criteria` synchronously from the Database.

### 1.3 `Ranker` Input Circular Logic
- **Resolution:** The `Ranker` node evaluates strictly utilizing `sectioned_text` + `distilled_criteria` to verify objective relevance without recursive LLM bias.

### 1.4 Central Explainer Split (Pipeline vs. Library)
- **Resolution:** 
  - **Pipeline Explainer:** Generates a rapid 3-sentence justification saved to `UserPapers.agent_explanation`.
  - **Library Explainer:** An entirely decoupled, on-demand API route (`POST /api/v1/library/{paper_id}/explain`) utilizing lazy-caching to explain deep concepts at varying complexity tiers.

### 1.5 The Missing `MemorySummarizer` Trigger
- **Resolution:** A Web UI `reject` payload instantly dispatches `process_reject_comment.delay()`. Celery handles hitting the summarizer LLM entirely asynchronously, completely removing UI latency constraints.

### 1.6 Modal.com Fallback Diagnostics (Compute Outage)
- **Issue:** Modal.com acts as the serverless GPU compute host for running heavy open-source PDF extraction models like `Marker` or `MinerU`. What happens during a compute outage?
- **Resolution:** The pipeline implements a Graceful Degradation Strategy:
  1. Attempt `Marker` or `MinerU` extraction via Modal.com GPU compute.
  2. *Fallback (Timeout/500):* Attempt local crude text extraction via `pypdfium`.
  3. *Fallback (Parsing Failure):* Skip deep PDF extraction entirely and execute the `Deep Evaluator` utilizing solely the `raw_abstract`. The UI will tag the paper indicating degraded evaluation.

---

## 2. Infrastructure Scaling & Edge Cases

### 2.1 Error Handling, Rate Limits & Pydantic Validation Retries
- **Problem:** External LLM APIs (429/500 limits), arXiv limits, and importantly, malformed LLM outputs (invalid JSON/hallucinated schema fields).
- **Resolution:** 
  - **API Outages:** Celery tasks wrap external integrations utilizing `@celery.task(autoretry_for=(RateLimitError, Timeout), backoff=True)`. arXiv scraping uniquely enforces exactly a **3.1-second wait limiter**.
  - **Malformed Pydantic JSON Outputs:** All LangGraph LLM nodes utilizing `Pydantic` schema outputs are wrapped utilizing LangChain's `RetryOutputParser`. If the LLM generates invalid JSON or bad fields, the exception is caught natively. The raw errored output alongside the exact Pydantic validation error is fed back into the LLM as a retry prompt (up to 3 times) before raising a Graph exception.

### 2.2 Concurrency vs Latency (Batching the Top 50)
- **Problem:** Looping 50 sequential blockings LLM calls for the `Evaluator` abstract scans creates extreme latency.
- **Resolution:** The `Evaluator` node executes across the `Top 50` pool utilizing **async parallel batches** (e.g., executing blocks of 10 requests concurrently via `asyncio.gather()`), lowering a 50-minute blocking task down to ~20 seconds.

### 2.3 User Polling UI Mechanism
- **Resolution:** The UI utilizes standard HTTP short-polling (every 5 seconds) hitting `GET /api/v1/pipeline/{task_id}/status`.

### 2.4 Celery Beat Production Scheduling
- **Resolution:** `Celery Beat` operates on a global hourly cron performing a parallel query: `SELECT user_id FROM user_settings WHERE notification_time == 'CURRENT_HOUR'`. It spawns a distributed `orchestrate_daily_pipeline` Celery task per user.

---

## 3. Anticipated System Risks & Thesis Metrics

### 3.1 Hard Token Truncation Warning
- **Risk:** Deeply scanning a mathematical PDF may exceed context windows even after Marker/MinerU parses text out.
- **Solution:** Add native Python hard-truncation limits restricting `PDFExtractor` strings to 80,000 max tokens prior to `SectionClassifier` consumption.

### 3.2 Token Cost Estimation Profile
- **Thesis Objective:** Quantify scaling cost metrics per pipeline run.
- **Estimate (Calculated via GPT-4o-mini baseline):** 
  - *Funnel Scan (50 abstracts):* ~300 tokens input + 10 output = 15k tokens. (~$0.02)
  - *Deep Phase (5 full papers):* ~8000 tokens input + 150 output = 40k tokens. (~$0.06)
  - **Verdict:** Operation is incredibly highly constrained to under ~$0.10 daily operating cost per active user by heavily utilizing the RRF Postgre Database funnel prior to costly deep scanning.
