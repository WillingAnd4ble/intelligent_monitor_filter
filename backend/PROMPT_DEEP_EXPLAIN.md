# Backend Instance — Async Deep Explain Endpoint

Read CLAUDE.md first.

## Context

When a user clicks "Explain" on an accepted paper in their library, we want a **deep, PDF-based explanation** — not just a 3-sentence abstract summary. The flow:

1. Fetch full paper PDF via Marker (Modal GPU) — `modal_client.marker_extract_pdf()` **already exists**
2. Classify sections via LLM — figure out which parts of the paper match user's `content_interest`
3. Generate a 300-600 word explanation from the relevant sections
4. Cache it so next click is instant

This is async because Marker takes 10-30s. Frontend polls for the result.

**Architecture rule**: Marker/Modal is NOT used in the filtering pipeline. Only here, for library explanations. The pipeline stays abstract-only. Don't touch `graph.py`.

## What Already Exists (DO NOT recreate)

- `app/worker/modal_client.py` — has `marker_extract_pdf(pdf_url: str) -> str` with MODAL_GPU_ENABLED kill switch + mock fallback. Use it as-is.
- `app/core/config.py` — already has `MODAL_GPU_ENABLED`, `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`
- `app/db/models.py` — `PaperExplanation` table with `user_paper_id`, `level`, `explanation`, `created_at`
- `app/agents/schemas.py` — `ExplainerOutput(explanation: str)` used by the pipeline explainer
- `POST /library/{id}/explain` in `library.py` — exists but is synchronous and abstract-only. **Rewrite this.**

## Task 1: Create `app/agents/section_classifier.py`

New file. This classifies paper sections using an LLM, then filters to only the sections the user cares about.

### Pydantic models (define in this file):

```python
from pydantic import BaseModel, Field
from typing import Literal

class SectionEntry(BaseModel):
    section_name: str = Field(description="Actual heading from paper, e.g. '3.1 Our Approach'")
    category: Literal["introduction", "methodology", "experiments", "conclusions", "other"]
    start_line: int
    end_line: int

class TableOfContents(BaseModel):
    sections: list[SectionEntry]
```

### Function:

```python
def classify_sections(full_text: str, content_interest: list[str]) -> str:
```

Logic:
1. If `full_text` is shorter than 50 lines → skip classification, return full text as-is
2. Prepend line numbers to each line of `full_text`: `"1: First line\n2: Second line\n..."`
3. Call LLM (gpt-4o-mini, temperature=0.0) with `.with_structured_output(TableOfContents)`
4. Prompt: `"You are a scientific paper analyst. Given a paper's full text with line numbers, identify all section boundaries. Map each section to exactly one of these categories: introduction, methodology, experiments, conclusions, other. Return the table of contents as structured JSON."`
5. Filter sections where `entry.category in content_interest`
6. For each matching section, slice original text lines `[start_line-1 : end_line]`
7. Concatenate filtered sections with `## {section_name}` headers preserved
8. Return concatenated text

Fallbacks:
- If content_interest filtering returns empty (no matching sections) → return full text
- If LLM call fails (exception) → log warning, return full text
- Use same LLM pattern as existing nodes in `graph.py` (ChatOpenAI + with_structured_output)

## Task 2: Add `ExplainResponse` schema to `app/schemas/api_schemas.py`

Add this alongside the existing `ExplanationResponse` (don't delete the old one yet — the pipeline nodes may reference it):

```python
class ExplainResponse(BaseModel):
    status: Literal["ready", "processing", "error"]
    level: Optional[str] = None
    explanation: Optional[str] = None
    task_id: Optional[str] = None
    detail: Optional[str] = None
```

## Task 3: Rewrite `POST /library/{user_paper_id}/explain` in `library.py`

Replace the current synchronous implementation. New logic:

1. Verify `user_paper_id` belongs to current user and `status='accepted'`
2. Get user's `library_explanation_level` and `content_interest` from UserSettings
3. Check `PaperExplanation` cache — if entry exists for `(user_paper_id, level)`, return:
   ```json
   { "status": "ready", "level": "professional", "explanation": "cached markdown..." }
   ```
4. If no cache → dispatch Celery task, return:
   ```json
   { "status": "processing", "task_id": "celery-task-uuid" }
   ```

Use `response_model=ExplainResponse`.

## Task 4: Add `GET /library/{user_paper_id}/explain/status` endpoint

New endpoint in `library.py`. Query param: `task_id: str`. Auth required.

Logic:
1. Get user's `library_explanation_level` from UserSettings
2. Check `PaperExplanation` cache first — if it appeared since the POST was made:
   ```json
   { "status": "ready", "level": "...", "explanation": "..." }
   ```
3. Otherwise check `celery_app.AsyncResult(task_id)`:
   - State is PENDING or STARTED → `{ "status": "processing" }`
   - State is FAILURE → `{ "status": "error", "detail": "Explanation generation failed" }`
   - State is SUCCESS → check cache again (task should have saved it)

## Task 5: Add `generate_deep_explanation` Celery task in `app/worker/celery_app.py`

New task that orchestrates the full flow. Signature:

```python
@celery_app.task(name="library.generate_deep_explanation")
def generate_deep_explanation(user_paper_id: str, user_id: str):
```

Steps inside the task:

**Step 1 — Fetch full PDF text:**
```python
from app.worker.modal_client import marker_extract_pdf

extracted_text = marker_extract_pdf(pdf_url)
# If empty (Modal disabled or failed), fall back to paper.abstract
if not extracted_text:
    extracted_text = paper.abstract
```

**Step 2 — Classify and filter sections:**
```python
from app.agents.section_classifier import classify_sections

filtered_text = classify_sections(extracted_text, user_settings.content_interest or [])
```

**Step 3 — Generate deep explanation:**
Call LLM (gpt-4o-mini, temperature=0.7) with structured output. The prompt should receive:
- Paper title and authors
- The filtered sections from Step 2
- User's `filtering_goal` (for contextual relevance)
- The `library_explanation_level`

Level instructions:
- **"professional"**: Technical depth, discusses methodology, experimental design, implications, limitations. Assumes domain knowledge.
- **"student"**: Explains key concepts, defines acronyms, relates to broader field, walks through results.
- **"kid"**: Plain language, analogies, no jargon, focuses on "what they did and why it matters."

Output: Markdown (headers, bullets, bold key terms). 300-600 words. This is a deep read, not a 3-sentence summary.

Define a Pydantic model for the output:
```python
class DeepExplanationOutput(BaseModel):
    explanation: str = Field(description="Markdown-formatted deep explanation, 300-600 words")
```

**Step 4 — Cache result:**
Save to `PaperExplanation` table (`user_paper_id` + `level`). Handle the race condition (double-click): if a row already exists for `(user_paper_id, level)`, update it instead of inserting a duplicate.

### Async wrapper:
Follow the same `asyncio.run(_run())` pattern used by existing Celery tasks in this file (like `trigger_agent_discovery` and `run_memory_summarizer`). Read from DB, call the functions, write to DB.

## What NOT to Touch
- `app/agents/graph.py` — the pipeline stays untouched. It has its own `node_explainer` for lightweight feed explanations. That's a different code path.
- `app/worker/modal_client.py` — already built, use `marker_extract_pdf()` as-is
- `app/core/config.py` — no changes needed, all config vars exist
- `app/db/models.py` — `PaperExplanation` table already exists with the right schema
- Files in `../gpu/` or `../web_ui/` — separate instances manage those

## Frontend Contract Note
The web_ui currently has `ExplainResponse = { level: string; explanation: string }` and calls `POST /library/{id}/explain`. After this change, the response shape changes to include `status` and optionally `task_id`. A separate web_ui instance will update the frontend to handle polling. Your job is just the backend.

## File Summary
| Action | File |
|--------|------|
| **Create** | `app/agents/section_classifier.py` |
| **Add schema** | `app/schemas/api_schemas.py` (add `ExplainResponse`) |
| **Rewrite** | `app/api/v1/endpoints/library.py` — rewrite `explain_paper`, add `explain_status` |
| **Add task** | `app/worker/celery_app.py` — add `generate_deep_explanation` |
