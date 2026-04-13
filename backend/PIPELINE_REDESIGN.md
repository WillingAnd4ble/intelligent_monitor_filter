# Pipeline Redesign — Cascade Agentic Funnel (v2)

**Date**: 2026-04-13
**Status**: APPROVED, ready for implementation
**Replaces**: Previous pipeline design (all accepted papers through Marker GPU)

## Problem

Current pipeline routes EVERY accepted paper through Marker GPU (~2-3 min each).
With 20 candidates and ~75% acceptance rate, that's ~15 Marker calls = ~40-50 min per run.
Most of that GPU time is wasted on papers that end up mid-tier in the feed.

## Design Principles

1. **Cascade filtering** — each stage is more expensive but more precise (same principle as LLM-SA approach from Chen et al., 2025, BJO)
2. **Unique information per agent** — no agent repeats another's work with the same data
3. **Marker is the bottleneck** — minimize Marker calls by filtering BEFORE GPU
4. **Parallel execution where possible** — Marker and Deep Reader calls run concurrently

## Architecture Overview

```
RRF → 30 candidates

PHASE 1 — Abstract Filtering (~1-2 min, no GPU):
═══════════════════════════════════════════════
  30 × Evaluator (pointwise)
    Input: abstract + distilled_criteria
    Output: decision (accept/borderline/reject) + score (1-10)
    Instruction: "when uncertain, prefer borderline over reject"

  ~5 × Critique (only borderline papers)
    Input: abstract + evaluator_reasonbook + feedback_memory
    Output: accept/reject
    Unique value: has feedback_memory (user's rejection history)

  Sort accepted papers by score → take Top K
  (K = user's deep_scan_limit setting: 5 / 10 / 15, default 10)

MARKER — Parallel PDF extraction (~10-12 min):
══════════════════════════════════════════════
  asyncio.gather() → all K PDFs concurrently
  Modal distributes across max 3 containers (T4 GPU)
  Markdown saved to UserPaper.extracted_markdown in DB

PHASE 2 — Deep Reading (~30 sec, parallel LLM):
═══════════════════════════════════════════════
  K × Deep Reader (parallel via asyncio.gather)
    Input: full markdown + distilled_criteria + feedback_memory
    Output: accept/reject + final_score (1-10) + explanation (2-3 sentences)
    
    One LLM call does THREE things:
    1. Validates relevance with full text (may reject what abstract accepted)
    2. Assigns final score based on full content
    3. Writes feed explanation ("why this was recommended")

  Papers with score < 5.0 → rejected (do not enter feed)
  Papers with score >= 5.0 → feed

TOP PICKS:
══════════
  Sort accepted papers by Deep Reader score
  Top 3 → is_top_pick=True + email/Slack notifications
  Remaining → regular feed items (still have explanation from Deep Reader)
```

## Agents Summary

| Agent | Input (unique) | Output | LLM calls |
|-------|---------------|--------|-----------|
| **Evaluator** | Abstract only | decision + score | 30 (pointwise) |
| **Critique** | + feedback_memory | accept/reject | ~5 (borderline only) |
| **Deep Reader** | + full markdown | accept/reject + score + explanation | K (parallel) |

Each agent has a UNIQUE information context:
- Evaluator sees: abstract + criteria
- Critique sees: + feedback_memory (rejection history)
- Deep Reader sees: + full paper text (markdown)

No agent duplicates another's work. This enables clean ablation studies:
- Evaluator-only vs full pipeline
- With/without Critique (feedback_memory effect)
- Abstract-only scoring vs full-text scoring (Evaluator score vs Deep Reader score)

## Cost Comparison

| | Old Pipeline | New Pipeline |
|---|---|---|
| RRF candidates | 20 | 30 |
| Marker GPU calls | ~15 (every accepted paper) | **K (only top candidates)** |
| LLM calls | ~80 (eval+marker+classifier+explainer+ranker) | **~45** (30 eval + ~5 critique + K deep reader) |
| Time estimate | ~50 min | **~15 min** |
| Feed quality | Abstract-only scoring | **Full-text validated** |

## Key Design Decisions

### 1. Evaluator gives decision AND score in one call
No separate Ranker for abstracts. Evaluator already sees abstract + criteria — adding
a separate Ranker with the same inputs is redundant. One structured output:
```python
class EvaluatorOutput(BaseModel):
    decision: str   # "accept" / "borderline" / "reject"
    score: float    # 1.0 - 10.0 (used for ranking, not filtering)
    reasonbook: str # internal reasoning (not shown to user)
```

### 2. Deep Reader combines evaluation + explanation in one call
No separate Explainer for feed. Deep Reader already reads full text + criteria —
a separate Explainer with the same inputs adds latency without new information:
```python
class DeepReaderOutput(BaseModel):
    decision: str      # "accept" / "reject"
    score: float       # 1.0 - 10.0 (final score, may differ from Evaluator)
    explanation: str   # 2-3 sentences for feed ("why recommended")
```

### 3. Section Classifier removed from feed pipeline
Full text goes to Deep Reader unfiltered. Section Classifier stays ONLY in the
library deep explanation chain (on-demand), where it filters by user's content_interest
to generate focused 300-600 word explanations.

### 4. Evaluator instructed to be conservative
Following LLM-SA finding (Chen et al.): "abstracts may not provide adequate
information for decisive exclusions." Evaluator prompt includes instruction to
prefer borderline over reject when uncertain. This ensures Deep Reader gets a
chance to validate with full text.

### 5. Top 3 selected by score, not by separate agent
Deep Reader already scored with full text. Additional agent for top-3 selection
would see the same information. Simple sort + take top 3 is sufficient.

### 6. Markdown saved to DB
UserPaper.extracted_markdown stores Marker output. When user later requests
deep explanation in library, the system reuses stored markdown instead of
calling Marker GPU again. Saves ~2-3 min and GPU cost per explanation.

### 7. Parallel Marker execution
asyncio.gather() sends all K PDFs to Modal concurrently. Modal.com's
max_containers=3 limit means ~3-4 batches automatically. From our side,
it's a single await. ~12 min for K=10 instead of ~30 min sequential.

### 8. Parallel Deep Reader execution
asyncio.gather() runs K Deep Reader LLM calls concurrently. Each gets
isolated context (one paper only), avoiding "lost in the middle" problem
that listwise approaches suffer from. ~30 sec for all K.

## DB Changes Required

1. `UserSettings.deep_scan_limit` — Integer, default 10 (choices: 5, 10, 15)
2. `UserSettings.lexical_query` — Text, nullable (auto-generated by GoalDistiller for BM25)
3. `UserPaper.extracted_markdown` — Text, nullable (Marker PDF output cached)
4. `UserPaper.is_top_pick` — Boolean, default False (top 3 flag)

## Files to Modify

| File | Changes |
|------|---------|
| `app/db/models.py` | Add deep_scan_limit, extracted_markdown, is_top_pick |
| `app/schemas/api_schemas.py` | Add deep_scan_limit to settings schema |
| `app/agents/schemas.py` | New EvaluatorOutput (with score), DeepReaderOutput |
| `app/agents/graph.py` | Rewrite: Phase 1 graph (evaluator + critique) + Phase 2 (deep_reader) |
| `app/worker/celery_app.py` | Orchestration: Phase 1 → sort → Marker parallel → Phase 2 parallel → top picks |
| `app/worker/notifications.py` | Filter by is_top_pick instead of score >= 7.0 |
| Alembic migration | New columns |

## Library Deep Explanation (unchanged, on-demand)

```
User clicks "Explain" on accepted paper in library
  → Check if extracted_markdown exists in DB (from pipeline)
    → If yes: use cached markdown (no Marker call!)
    → If no: call Marker GPU
  → Section Classifier filters by content_interest
  → Deep Explainer (gpt-5.4-nano) generates 300-600 word explanation
  → Cached in PaperExplanation table
```

## Academic Justification

This cascade architecture follows established patterns:
- **Cascade ranking** (used in Google Search, recommender systems): cheap broad filter → expensive precise filter
- **LLM-SA approach** (Chen et al., 2025): abstract screening → full-text selection achieved 82.7% recall
- **Key LLM-SA findings applied**:
  - All criteria evaluated together (not separately) — separate evaluation dropped accuracy to 15%
  - Abstract stage should be conservative — "not sure" cases advance
  - Full-text stage corrects abstract-stage errors
  - Main error source is LLM's inability to find info in long text → our Deep Reader gets ONE paper (not a batch)
