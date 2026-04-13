# Benchmark Harness Redesign — Design Spec

**Date:** 2026-04-13
**Status:** Approved for implementation
**Replaces:** `testing/benchmark/benchmark_pipeline.py`, `testing/benchmark/experiments.py`, and the 4-experiment layout in `testing/EVALUATION_BENCHMARK_SPECIFICATION.md`
**Owner:** Undergrad thesis — agent-based arXiv filtering project
**Scope:** Phase 1 of thesis evaluation rigor (Phase 2 = union-based dataset, deferred)

---

## 1. Purpose & thesis framing

Primary thesis claim: **the agent-based system effectively reduces information overload and surfaces relevant arXiv papers for a user-defined goal**. The multi-agent cascade architecture is an *implementation choice* that needs empirical justification, not the headline research question.

This spec defines a Streamlit-based benchmark harness that:

1. Produces thesis-grade precision, cost, and latency metrics against a hand-labeled ground truth
2. Empirically justifies architectural and model choices via ablation
3. Enables rapid "run → chart → thesis figure" iteration

## 2. Scope

### In scope (Phase 1)

- Goal-parameterized candidate pulling from the production database
- GoalDistiller-based labeling protocol with frozen criteria
- Cached real-LLM execution of the shipped cascade pipeline (`evaluator` + `critique` + `deep_reader`)
- 5 experiments (Model selection, Critique ablation, Longitudinal feedback, Cost–value curve, Deep Reader value)
- Two goals in parallel: `security_v1` and `finance_v1`
- Single-afternoon hand-labeling workflow (~30 papers per goal)
- Thesis-ready chart exports (PNG + copy-pastable LaTeX figure blocks)

### Out of scope (Phase 2)

- Union-of-retrievers ground-truth dataset (BM25 ∪ SPECTER2 ∪ RRF, ~150 papers)
- Pre-filter retrieval recall experiment (Exp 6)
- Publishing labels to the public repo
- Multi-labeler inter-annotator agreement

## 3. Architecture

### 3.1 Directory layout

```
testing/
├── benchmark/
│   ├── app.py                      # Streamlit entrypoint
│   ├── pages/
│   │   ├── 1_Pull_Candidates.py    # Goal → distill → multi-retriever pull
│   │   ├── 2_Label.py              # Paper-at-a-time labeling UI
│   │   ├── 3_Run_Experiment.py     # Toggle config + preset buttons
│   │   └── 4_Charts.py             # Result viewer + export
│   ├── lib/
│   │   ├── pull.py                 # pull_candidates(goal, retriever, k)
│   │   ├── runner.py               # run_pipeline(papers, config) with cache
│   │   ├── metrics.py              # precision, pass-through, latency, cost, Wilson CI
│   │   ├── schemas.py              # Pydantic models for all JSON file shapes
│   │   ├── chart_style.py          # matplotlib rcparams (Okabe-Ito, thesis-ready)
│   │   └── cache.py                # LLM response cache (sha256 keys, prompt_version)
│   ├── benchmark_pipeline.py       # KEPT until cutover gate passes, then deleted
│   └── experiments.py              # KEPT until cutover gate passes, then deleted
├── data/                           # NEW, gitignored EXCEPT cache_manifest.json
│   ├── goals/{goal_id}.json
│   ├── candidates/{goal_id}__{retriever}.json
│   ├── labels/{goal_id}.json
│   ├── results/{run_id}.json
│   ├── llm_cache/{node}/{hash}.json
│   └── cache_manifest.json         # committed — (hash, paper_id, node, config) tuples
├── .env.benchmark                  # read-only DB connection string
└── tests/                          # UNTOUCHED (separate FR1-18 pytest workstream)
```

### 3.2 Core design principles

- **App is thin UI.** All logic lives in `lib/`. Each `lib/` module has no Streamlit imports and is unit-testable with pytest.
- **Data files are the contract.** Pages communicate through JSON on disk, not session state. Workflow is resumable across app restarts.
- **Frozen is frozen.** Once `goals/{goal_id}.json` is written, its criteria are immutable. Revisions require a new `{goal_id}_v2` file.
- **Backend is read-only.** The harness imports from `../backend/app/` (agents, retrieval, distiller) and queries the prod Postgres read-only. It never writes to the prod DB and never re-runs Marker GPU.
- **Cached real LLM calls.** The shipped cascade is executed with real LLM responses on first run; subsequent runs replay from cache (keyed by `sha256(paper_id + node + prompt_version + node_input + llm_model)`).
- **Each goal gets its own ID** (`security_v1`, `finance_v1`). Parallel tracks visible in every page.

### 3.3 Data flow

```
Page 1: raw goal
  → GoalDistiller → criteria (iterate, then freeze)
  → goals/{goal_id}.json
  → for retriever in [bm25, specter2, rrf]:
       perform_hybrid_rrf_search(criteria, retriever, k=30)
       → candidates/{goal_id}__{retriever}.json

Page 2: select goal_id
  → read candidates/{goal_id}__rrf.json   (Phase 1 labels only RRF)
  → paper-at-a-time UI with criteria checklist
  → labels/{goal_id}.json (incremental writes)

Page 3: select goal_id + config
  → for each paper in labels:
       run shipped cascade nodes per config, honoring cache
  → metrics computed
  → results/{run_id}.json

Page 4: select goal_id + run_ids
  → load results/*.json
  → render charts, export PNG, copy LaTeX
```

## 4. Labeling protocol

### 4.1 Goal freezing (Page 1)

1. User enters `goal_id` (slug) and `raw_goal` (textarea).
2. Click "Distill & Preview" → calls `GoalDistiller` (imported from `backend/app/agents/distiller.py`).
3. Distilled criteria displayed in an editable table. User may edit wording inline or re-run distillation with amended goal text.
4. Click "Freeze & Pull" writes `goals/{goal_id}.json` and triggers candidate pulls for all three retrievers in parallel.

**Frozen contents** (see §6 for schema): raw goal, distilled criteria array, `lexical_query`, scoring rule (default `majority`, threshold `ceil(N/2)`), `distiller_model`, `frozen_at` timestamp.

### 4.2 Candidate pulling (Page 1, automatic)

Pulls `top_k=30` papers per retriever:

- **BM25-only**: `tsvector` search using the distilled `lexical_query`
- **SPECTER2-only**: cosine similarity against `goal_embedding` (stored in `UserSettings`)
- **RRF (default)**: `perform_hybrid_rrf_search` with production defaults (`k_semantic=30`, `k_lexical=60`)

Output: three separate JSON files (`candidates/{goal_id}__bm25.json`, `..._specter2.json`, `..._rrf.json`). Only the RRF file is labeled in Phase 1. The other two exist for Phase 2 recall analysis without re-querying a possibly-drifted DB.

### 4.3 Hand labeling (Page 2)

- Select `goal_id`.
- UI shows one paper at a time: title, authors, full abstract, "open on arXiv" link, one checkbox per frozen criterion, `borderline` toggle, optional free-text notes, Prev/Next/Save buttons.
- Progress bar and session timer visible. Soft prompt for a break every 20 papers (R5 mitigation).
- Warning banner if `borderline > 30%` of labeled-so-far — prompts re-reading criteria or adding a criterion to disambiguate (R7 mitigation).

**Scoring rule** (configurable in sidebar, locked after first save):

- `ground_truth_score = 1` iff `|criteria_satisfied| ≥ ceil(N/2)` AND `borderline = False`
- `ground_truth_score = 0` otherwise
- Borderline papers are excluded from precision's numerator and denominator

**Save behavior**: incremental write to `labels/{goal_id}.json` on every Next/Save. Keyed by `paper_id`. Resumable.

## 5. Experiment runner

### 5.1 Toggle config (Page 3)

| Toggle | Values | Notes |
|---|---|---|
| Model | `gpt-4o-mini` / `claude-haiku-4-5-20251001` / `gpt-5.4-nano-2026-03-17` | Applies to all agent LLM calls in the run |
| Evaluator | always on | Phase 1 entry |
| Critique | on / off | Ablates `feedback_memory` effect |
| Deep Reader | on / off | Ablates full-text stage |
| Feedback memory | empty / seeded(5 rejections) | Simulates FR14 longitudinal |
| deep_scan_limit K | 5 / 10 / 15 / 30 | 30 disables the top-K cut |

### 5.2 Experiment presets

| # | Experiment | Preset |
|---|---|---|
| 1 | **Model selection (first test)** | model ∈ {gpt-4o-mini, haiku-4-5, gpt-5.4-nano}, others fixed (Critique=on, Deep Reader=on, memory=empty, K=10) |
| 2 | Critique ablation | Critique off vs on, others fixed |
| 3 | Longitudinal feedback | memory=empty vs seeded, others fixed |
| 4 | Cost–value K curve | K ∈ {5, 10, 15, 30}, others fixed |
| 5 | Deep Reader value | Deep Reader off vs on, others fixed |
| 6 | *(deferred)* Pre-filter recall | BM25 vs SPECTER2 vs RRF — requires Phase 2 union dataset |

**Cost preview**: before the Run button enables, Page 3 shows an estimated USD cost based on cache state + token estimates. Hard cap `$5` per run in config; requires explicit override to exceed (R6 mitigation).

### 5.3 Run execution (`lib/runner.py`)

For each labeled paper in the goal's RRF candidate set:

1. **Cache lookup** — key = `sha256(paper_id || node_name || prompt_version || node_input_hash || llm_model)`. Hit → return cached response + counters. Miss → real LLM call, store response JSON, update `cache_manifest.json`.
2. Route through configured pipeline per toggles:
   - `node_evaluator(abstract, criteria) → EvaluatorOutput`
   - If `decision == "borderline"` and Critique on: `node_critique(abstract, reasonbook, feedback_memory) → CritiqueOutput`
   - If Deep Reader on and paper ranks in top-K by evaluator_score: `run_deep_reader(extracted_markdown, criteria, feedback_memory) → DeepReaderOutput`
3. **Marker is never called.** If `UserPaper.extracted_markdown` is `NULL` for a paper, Deep Reader falls back to abstract-only scoring, and the run logs `missing_fulltext_count += 1`.
4. Record per-paper: predicted decision, predicted score, per-node latency (ms), per-node token counts, per-node `cached` bool.

**Prompt version tracking** (R3 mitigation): each node module exposes a `PROMPT_VERSION` string constant (e.g., `"evaluator:v3"`). Cache key includes it. Prompt edits require bumping the constant; stale cache entries become unreachable and regenerate on next run.

### 5.4 Metrics (`lib/metrics.py`)

Computed against hand labels (borderline excluded):

- **Precision** (overall + per-stage: after Evaluator, after Critique, after Deep Reader) with **Wilson 95% CI** (R2 mitigation)
- **Per-stage pass-through rate**: `survivors_after_node / survivors_before_node`
- **Per-stage latency**: median + p95 ms
- **Token cost USD**: per-model rate table in `config.py`; totaled per run
- **Score agreement**: Pearson correlation between Evaluator score and Deep Reader score (for "when did full text change the mind" story)
- **Run counters**: `tp`, `fp`, `fn`, `borderline_excluded`, `missing_fulltext_count`, `cache_hit_rate`

## 6. Data schemas (Pydantic, in `lib/schemas.py`)

Canonical shapes are defined in `lib/schemas.py` as Pydantic models; all file I/O round-trips through them. Summary of files and their purpose:

- `data/goals/{goal_id}.json` — frozen goal + criteria + scoring rule + timestamps
- `data/candidates/{goal_id}__{retriever}.json` — retriever output (bm25, specter2, rrf)
- `data/labels/{goal_id}.json` — per-paper ground truth + borderline + notes
- `data/results/{run_id}.json` — per-paper stage outcomes + aggregate metrics
- `data/cache_manifest.json` — committed index: `[{hash, paper_id, node, config_signature}]`
- `data/llm_cache/{node}/{hash}.json` — gitignored response payload

Run ID format: `{goal_id}__{config_hash8}__{iso8601_minute}`.

## 7. Charts (`lib/chart_style.py` + Page 4)

Single shared matplotlib rcparams: Okabe-Ito colorblind palette, thesis-sized fonts, minimal chartjunk.

| # | Chart | Input | Thesis use |
|---|---|---|---|
| 1 | Precision by stage (bar) | one run | Cascade funnel visualization |
| 2 | Pass-through funnel (Sankey) | one run | 30 → after Evaluator → after Critique → after Deep Reader |
| 3 | Precision × Cost scatter | multi-run | Experiment 4 frontier |
| 4 | Critique ablation (paired bar) | 2 runs | Experiment 2 |
| 5 | Deep Reader ablation (paired bar) | 2 runs | Experiment 5 headline |
| 6 | Score agreement scatter | one run | Evaluator vs Deep Reader per paper |
| 7 | Memory effect (paired bar) | 2 runs | Experiment 3 |
| 8 | Cross-goal grouped bar | runs across goals | Security vs Finance generalizability |
| 9 | Latency × precision scatter | multi-run | "more calls ≠ better" story if present |
| 10 | Model comparison grouped bar | 3 runs | Experiment 1 headline: precision, cost, latency per model |

Each chart has "Export PNG" (300dpi) and "Copy LaTeX figure block" buttons. LaTeX block includes caption placeholder, `\label`, and relative path.

## 8. Implementation strategy: parallel build + cutover

### 8.1 Parallel build

Build `benchmark/app.py`, `benchmark/pages/`, `benchmark/lib/`, and `data/` **alongside** the existing `benchmark_pipeline.py` and `experiments.py`. Do not delete anything until the cutover gate passes.

### 8.2 Cutover gate

New app must pass these checks before deleting old files:

1. Pull candidates for goal `security_v1` end-to-end (GoalDistiller runs, all three retrievers return 30 papers each, JSON files written).
2. Label ≥3 papers through Page 2 UI; JSON written correctly with expected schema; resumable after app restart.
3. Run Experiment 1 (model selection, gpt-4o-mini leg) with cached LLMs; result JSON written; Chart 1 renders.

### 8.3 Cutover commit

A single commit:

- Deletes `testing/benchmark/benchmark_pipeline.py`
- Deletes `testing/benchmark/experiments.py`
- Rewrites `testing/EVALUATION_BENCHMARK_SPECIFICATION.md` to reflect this spec
- Updates `testing/CLAUDE.md` to point at the new entrypoint and file layout

The `testing/tests/` pytest workstream is untouched.

## 9. Risks & mitigations

| # | Risk | Mitigation |
|---|---|---|
| R1 | ~~Pipeline redesign not implemented~~ | **Resolved** — cascade shipped in `graph.py`, `run_deep_reader()`, `celery_app.py` orchestration. |
| R2 | N=30 precision has wide CIs; architectural deltas may be noise | Wilson 95% CI reported alongside every precision number; thesis language is "directional" when CIs overlap. |
| R3 | Prompt edits silently invalidate cache | `PROMPT_VERSION` constant per node module; cache key includes it. Bump on prompt change. |
| R4 | Prod DB dependency for RRF + markdown | Read-only `.env.benchmark` connection string; `smoke_test_db_access()` on app startup with clear failure message. |
| R5 | Labeling fatigue → noisy labels | Session timer; break prompt every 20 papers; timestamps enable fatigue-drift audit. |
| R6 | Cost surprise on first cache-miss run | Pre-Run cost preview; hard cap $5/run with explicit override. |
| R7 | Borderline-label abuse → unstable precision | Warning banner at >30% borderline; prompts criterion review. |
| R8 | Model-selection sweep one-time cost ~$6–18 | One-time spend; cache makes all reruns free. Explicit line-item in thesis methodology. |

## 10. Open decisions locked

- **Q1 answered**: model choice is itself Experiment 1. Three candidates: `gpt-4o-mini`, `claude-haiku-4-5-20251001`, `gpt-5.4-nano-2026-03-17`.
- **Q2 answered**: pull all three retrievers at candidate time. Only RRF is labeled in Phase 1.
- **Q3 answered**: labels remain gitignored in Phase 1. Revisit before thesis defense.

## 11. Phase 2 (deferred, sketched for continuity)

- Extend `pull.py` to compute the labeled-set union across retrievers.
- Add a "label missing papers" mode to Page 2 for papers in union minus current labels.
- Enable Experiment 6 (pre-filter retrieval recall).
- Add second goal per domain (generalizability within security, within finance).
- Add inter-annotator agreement if a second labeler is available.

## 12. Success criteria

This spec is successfully implemented when:

1. User can run `streamlit run testing/benchmark/app.py`, pull candidates for `security_v1`, label 30 papers, run Experiment 1 for all three models, and export Chart 10 (model comparison) as a PNG + LaTeX block — in a single sitting.
2. The same workflow repeats for `finance_v1` with no code changes.
3. All five experiments for both goals produce result JSON files with metrics block populated and charts rendering correctly.
4. The thesis architecture chapter can cite `data/goals/*.json` criteria verbatim and include Charts 1, 5, 8, and 10 without manual redrawing.

---

**Next step:** invoke `writing-plans` skill to produce step-by-step implementation plan for this spec.