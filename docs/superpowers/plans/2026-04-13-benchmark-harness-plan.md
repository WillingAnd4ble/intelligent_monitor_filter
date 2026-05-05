# Benchmark Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Streamlit-based benchmark harness with cached real-LLM cascade execution, hand-labeling UI, and thesis-ready chart export — implementing the spec at `docs/superpowers/specs/2026-04-13-benchmark-harness-design.md`.

**Architecture:** Multi-page Streamlit app with thin UI calling pure-Python `lib/*` modules. JSON files on disk are the contract between pages. LLM responses cached by `sha256(paper_id + node + prompt_version + node_input + llm_model)`. Backend code is read-only — we import shipped Pydantic schemas from `backend/app/agents/schemas.py` and call SPECTER2/RRF from `backend/app/db/retrieval.py`, but mirror the LLM prompts locally so we can swap models cleanly.

**Tech Stack:** Streamlit, Pydantic v2, SQLAlchemy 2.x async (asyncpg), `langchain-openai`, `langchain-anthropic`, matplotlib, pytest + pytest-asyncio.

**Working directory for all paths below:** project root (`c:/Users/Work/Documents/Studie/Intelligent_filter/Building_planning_station/`)

---

## File structure being built

```
testing/
├── benchmark/
│   ├── app.py                       # Streamlit entrypoint (Home page)
│   ├── pages/
│   │   ├── 1_Pull_Candidates.py
│   │   ├── 2_Label.py
│   │   ├── 3_Run_Experiment.py
│   │   └── 4_Charts.py
│   ├── lib/
│   │   ├── __init__.py
│   │   ├── schemas.py               # Pydantic models
│   │   ├── paths.py                 # data/ path helpers
│   │   ├── cache.py                 # LLM response cache + manifest
│   │   ├── pull.py                  # candidate retrievers (bm25/specter2/rrf)
│   │   ├── distill.py               # GoalDistiller wrapper
│   │   ├── llm.py                   # multi-provider LLM call factory
│   │   ├── prompts.py               # mirrored prompts (versioned)
│   │   ├── runner.py                # cascade orchestration
│   │   ├── metrics.py               # precision, Wilson CI, pass-through, cost
│   │   ├── pricing.py               # per-model token rates
│   │   ├── chart_style.py           # matplotlib rcparams (Okabe-Ito)
│   │   └── charts.py                # 10 chart-building functions
│   └── tests/
│       ├── conftest.py
│       ├── test_schemas.py
│       ├── test_cache.py
│       ├── test_metrics.py
│       ├── test_pricing.py
│       ├── test_runner.py
│       └── test_paths.py
├── data/
│   ├── goals/
│   ├── candidates/
│   ├── labels/
│   ├── results/
│   ├── llm_cache/
│   └── cache_manifest.json
└── .env.benchmark                   # read-only DB connection
```

---

## Phase 0: Scaffolding

### Task 0: Project scaffolding and dependencies

**Files:**
- Create: `testing/benchmark/lib/__init__.py`
- Create: `testing/benchmark/tests/__init__.py`
- Create: `testing/benchmark/tests/conftest.py`
- Create: `testing/benchmark/pytest.ini`
- Modify: `testing/requirements.txt` (add new packages)
- Modify: `.gitignore` (add data exclusions)
- Create: `testing/.env.benchmark.example`

- [ ] **Step 1: Create directory tree**

```bash
mkdir -p testing/benchmark/lib testing/benchmark/pages testing/benchmark/tests
mkdir -p testing/data/goals testing/data/candidates testing/data/labels
mkdir -p testing/data/results testing/data/llm_cache
```

- [ ] **Step 2: Create empty package files**

Create `testing/benchmark/lib/__init__.py` with content:
```python
"""Benchmark harness library — pure Python, no Streamlit imports."""
```

Create `testing/benchmark/tests/__init__.py` (empty file).

- [ ] **Step 3: Add pytest config**

Create `testing/benchmark/pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
```

- [ ] **Step 4: Update requirements.txt**

Read `testing/requirements.txt` and append (deduplicate if any are present):
```
streamlit>=1.32
pydantic>=2.6
matplotlib>=3.8
langchain-openai>=0.1
langchain-anthropic>=0.1
sqlalchemy>=2.0
asyncpg>=0.29
pgvector>=0.2.5
pytest-asyncio>=0.23
scipy>=1.11
```

- [ ] **Step 5: Update .gitignore**

Read `.gitignore`. Append:
```
# Benchmark harness data
testing/data/llm_cache/
testing/data/labels/
testing/data/results/
testing/.env.benchmark
```

Note: `testing/data/goals/`, `testing/data/candidates/`, and `testing/data/cache_manifest.json` ARE committed (they're inputs/proofs, not regenerable secrets).

- [ ] **Step 6: Create env example**

Create `testing/.env.benchmark.example`:
```
# Read-only Postgres connection for benchmark harness
# Copy to .env.benchmark and fill in real values
BENCHMARK_DB_URL=postgresql+asyncpg://readonly_user:password@localhost:5433/arxiv_filter

# OpenAI for gpt-4o-mini and gpt-5.4-nano models
OPENAI_API_KEY=sk-...

# Anthropic for claude-haiku-4-5
ANTHROPIC_API_KEY=sk-ant-...

# Optional: hard cost cap per run (USD), default 5.00
BENCHMARK_COST_CAP_USD=5.00
```

- [ ] **Step 7: Conftest with shared fixtures**

Create `testing/benchmark/tests/conftest.py`:
```python
import os
import pytest
import tempfile
from pathlib import Path

@pytest.fixture
def tmp_data_dir(monkeypatch):
    """Redirect data/ writes to a tempdir for tests."""
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("BENCHMARK_DATA_DIR", tmp)
        yield Path(tmp)
```

- [ ] **Step 8: Commit**

```bash
git add testing/benchmark testing/data testing/requirements.txt testing/.env.benchmark.example .gitignore
git commit -m "scaffold: benchmark harness directory tree and dependencies"
```

---

## Phase 1: Pure-logic library

### Task 1: Path helpers (`lib/paths.py`)

Keeps every file path concentrated in one module so test fixtures can redirect it.

**Files:**
- Create: `testing/benchmark/lib/paths.py`
- Create: `testing/benchmark/tests/test_paths.py`

- [ ] **Step 1: Write the failing test**

Create `testing/benchmark/tests/test_paths.py`:
```python
from pathlib import Path
import os
from benchmark.lib import paths

def test_data_root_uses_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("BENCHMARK_DATA_DIR", str(tmp_path))
    assert paths.data_root() == tmp_path

def test_goal_path_format(monkeypatch, tmp_path):
    monkeypatch.setenv("BENCHMARK_DATA_DIR", str(tmp_path))
    p = paths.goal_path("security_v1")
    assert p == tmp_path / "goals" / "security_v1.json"

def test_candidates_path_format(monkeypatch, tmp_path):
    monkeypatch.setenv("BENCHMARK_DATA_DIR", str(tmp_path))
    p = paths.candidates_path("security_v1", "rrf")
    assert p == tmp_path / "candidates" / "security_v1__rrf.json"

def test_labels_path_format(monkeypatch, tmp_path):
    monkeypatch.setenv("BENCHMARK_DATA_DIR", str(tmp_path))
    p = paths.labels_path("security_v1")
    assert p == tmp_path / "labels" / "security_v1.json"

def test_result_path_format(monkeypatch, tmp_path):
    monkeypatch.setenv("BENCHMARK_DATA_DIR", str(tmp_path))
    p = paths.result_path("security_v1__abc12345__2026-04-13T16:05Z")
    assert p == tmp_path / "results" / "security_v1__abc12345__2026-04-13T16:05Z.json"
```

- [ ] **Step 2: Run test, expect failure**

```bash
cd testing/benchmark && pytest tests/test_paths.py -v
```
Expected: ImportError or fail because `paths` doesn't exist yet.

- [ ] **Step 3: Implement `lib/paths.py`**

```python
"""Path helpers — every data-file path in the harness goes through here."""

import os
from pathlib import Path


def data_root() -> Path:
    """Root of the data/ directory. Honors BENCHMARK_DATA_DIR env var (used by tests)."""
    env = os.environ.get("BENCHMARK_DATA_DIR")
    if env:
        return Path(env)
    # default: testing/data relative to repo root
    return Path(__file__).resolve().parents[3] / "testing" / "data"


def goal_path(goal_id: str) -> Path:
    return data_root() / "goals" / f"{goal_id}.json"


def candidates_path(goal_id: str, retriever: str) -> Path:
    return data_root() / "candidates" / f"{goal_id}__{retriever}.json"


def labels_path(goal_id: str) -> Path:
    return data_root() / "labels" / f"{goal_id}.json"


def result_path(run_id: str) -> Path:
    return data_root() / "results" / f"{run_id}.json"


def cache_path(node: str, hash_hex: str) -> Path:
    return data_root() / "llm_cache" / node / f"{hash_hex}.json"


def cache_manifest_path() -> Path:
    return data_root() / "cache_manifest.json"


def ensure_subdirs() -> None:
    """Create data/* subdirs if missing. Safe to call repeatedly."""
    root = data_root()
    for sub in ("goals", "candidates", "labels", "results", "llm_cache"):
        (root / sub).mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 4: Run tests, expect pass**

```bash
cd testing/benchmark && pytest tests/test_paths.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add testing/benchmark/lib/paths.py testing/benchmark/tests/test_paths.py
git commit -m "feat(benchmark): add path helpers for data/* files"
```

---

### Task 2: Pydantic schemas (`lib/schemas.py`)

Defines every JSON file shape. Writing them first nails down the contracts.

**Files:**
- Create: `testing/benchmark/lib/schemas.py`
- Create: `testing/benchmark/tests/test_schemas.py`

- [ ] **Step 1: Write the failing test**

Create `testing/benchmark/tests/test_schemas.py`:
```python
from datetime import datetime, timezone
from benchmark.lib.schemas import (
    Criterion, ScoringRule, GoalFile, CandidatePaper, CandidatesFile,
    PaperLabel, LabelsFile, RunConfig, StageOutcome, PerPaperRecord,
    RunMetrics, ResultsFile, CacheManifestEntry,
)


def test_goal_file_roundtrip():
    g = GoalFile(
        goal_id="security_v1",
        raw_goal="test",
        distilled_criteria=[Criterion(id="c1", text="must mention security")],
        lexical_query="security llm",
        scoring_rule=ScoringRule(type="majority", threshold=1),
        frozen_at=datetime.now(timezone.utc),
        distiller_model="gpt-4o-mini",
    )
    j = g.model_dump_json()
    g2 = GoalFile.model_validate_json(j)
    assert g2.goal_id == "security_v1"
    assert g2.distilled_criteria[0].id == "c1"


def test_candidates_file_roundtrip():
    c = CandidatesFile(
        goal_id="security_v1",
        retriever="rrf",
        top_k=30,
        rrf_params={"k_semantic": 30, "k_lexical": 60},
        pulled_at=datetime.now(timezone.utc),
        papers=[
            CandidatePaper(
                paper_id="2024.12345",
                title="Test Paper",
                abstract="An abstract.",
                authors=["A. Author"],
                pdf_url="https://arxiv.org/pdf/2024.12345",
                rrf_rank=1,
                rrf_score=0.04,
                has_extracted_markdown=True,
            )
        ],
    )
    j = c.model_dump_json()
    c2 = CandidatesFile.model_validate_json(j)
    assert len(c2.papers) == 1
    assert c2.papers[0].rrf_rank == 1


def test_labels_file_roundtrip():
    l = LabelsFile(
        goal_id="security_v1",
        labeler="user",
        labels={
            "2024.12345": PaperLabel(
                criteria_satisfied=["c1"],
                ground_truth_score=1,
                borderline=False,
                notes="ok",
                labeled_at=datetime.now(timezone.utc),
            )
        },
    )
    j = l.model_dump_json()
    l2 = LabelsFile.model_validate_json(j)
    assert l2.labels["2024.12345"].ground_truth_score == 1


def test_run_config_hash_is_stable():
    a = RunConfig(model="gpt-4o-mini", evaluator=True, critique=True,
                  deep_reader=True, feedback_memory="empty", deep_scan_limit=10)
    b = RunConfig(model="gpt-4o-mini", evaluator=True, critique=True,
                  deep_reader=True, feedback_memory="empty", deep_scan_limit=10)
    assert a.config_hash() == b.config_hash()
    assert len(a.config_hash()) == 8


def test_run_config_hash_differs_on_model():
    a = RunConfig(model="gpt-4o-mini", evaluator=True, critique=True,
                  deep_reader=True, feedback_memory="empty", deep_scan_limit=10)
    b = RunConfig(model="claude-haiku-4-5-20251001", evaluator=True, critique=True,
                  deep_reader=True, feedback_memory="empty", deep_scan_limit=10)
    assert a.config_hash() != b.config_hash()


def test_results_file_metrics_required():
    r = ResultsFile(
        run_id="security_v1__abc12345__2026-04-13T16:05Z",
        goal_id="security_v1",
        config=RunConfig(model="gpt-4o-mini", evaluator=True, critique=True,
                         deep_reader=True, feedback_memory="empty", deep_scan_limit=10),
        per_paper=[],
        metrics=RunMetrics(
            precision_final=0.83, precision_final_ci=(0.65, 0.93),
            precision_after_evaluator=0.71, precision_after_critique=0.78, precision_after_deep_reader=0.83,
            pass_through={"evaluator": 0.6, "critique": 0.8, "deep_reader": 0.92},
            latency_ms_median=1650.0, latency_ms_p95=2400.0,
            cost_usd=0.042,
            agreement_evaluator_vs_deep_reader_pearson=0.68,
            counts={"tp": 10, "fp": 2, "fn": 2, "borderline_excluded": 4, "missing_fulltext": 1},
            cache_hit_rate=0.5,
        ),
    )
    j = r.model_dump_json()
    r2 = ResultsFile.model_validate_json(j)
    assert r2.metrics.precision_final == 0.83
```

- [ ] **Step 2: Run test, expect failure**

```bash
cd testing/benchmark && pytest tests/test_schemas.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `lib/schemas.py`**

```python
"""Pydantic schemas for every JSON file the harness reads or writes.

All file I/O round-trips through these models — never write or read raw dicts.
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


# --- Goal ---

class Criterion(BaseModel):
    id: str
    text: str


class ScoringRule(BaseModel):
    type: Literal["majority", "strict", "lenient"] = "majority"
    threshold: int = Field(description="Minimum number of criteria that must be satisfied")


class GoalFile(BaseModel):
    goal_id: str
    raw_goal: str
    distilled_criteria: List[Criterion]
    lexical_query: str
    scoring_rule: ScoringRule
    frozen_at: datetime
    distiller_model: str


# --- Candidates ---

class CandidatePaper(BaseModel):
    paper_id: str
    title: str
    abstract: str
    authors: List[str]
    pdf_url: Optional[str]
    rrf_rank: int
    rrf_score: float
    has_extracted_markdown: bool


class CandidatesFile(BaseModel):
    goal_id: str
    retriever: Literal["bm25", "specter2", "rrf"]
    top_k: int
    rrf_params: Optional[Dict[str, int]] = None
    pulled_at: datetime
    papers: List[CandidatePaper]


# --- Labels ---

class PaperLabel(BaseModel):
    criteria_satisfied: List[str]
    ground_truth_score: int  # 0 or 1
    borderline: bool
    notes: Optional[str] = None
    labeled_at: datetime


class LabelsSummary(BaseModel):
    total: int
    positive: int
    negative: int
    borderline: int


class LabelsFile(BaseModel):
    goal_id: str
    labeler: str = "user"
    labels: Dict[str, PaperLabel]  # keyed by paper_id

    def summary(self) -> LabelsSummary:
        total = len(self.labels)
        positive = sum(1 for v in self.labels.values() if v.ground_truth_score == 1 and not v.borderline)
        negative = sum(1 for v in self.labels.values() if v.ground_truth_score == 0 and not v.borderline)
        borderline = sum(1 for v in self.labels.values() if v.borderline)
        return LabelsSummary(total=total, positive=positive, negative=negative, borderline=borderline)


# --- Run config + results ---

class RunConfig(BaseModel):
    model: str
    evaluator: bool = True
    critique: bool = True
    deep_reader: bool = True
    feedback_memory: Literal["empty", "seeded"] = "empty"
    deep_scan_limit: int = 10

    def config_hash(self) -> str:
        """8-char sha256 of the canonical config JSON. Used in run_id."""
        canonical = self.model_dump_json()
        return hashlib.sha256(canonical.encode()).hexdigest()[:8]


class StageOutcome(BaseModel):
    decision: Optional[str] = None
    score: Optional[float] = None
    latency_ms: float
    tokens_in: int
    tokens_out: int
    cached: bool


class PerPaperRecord(BaseModel):
    paper_id: str
    stages: Dict[str, Optional[StageOutcome]]  # keys: evaluator, critique, deep_reader
    final_decision: Literal["accept", "reject"]
    final_score: Optional[float]
    gt_label: Optional[int]  # 0/1, or None if borderline


class RunMetrics(BaseModel):
    precision_final: float
    precision_final_ci: Tuple[float, float]  # (lower, upper) Wilson 95%
    precision_after_evaluator: Optional[float] = None
    precision_after_critique: Optional[float] = None
    precision_after_deep_reader: Optional[float] = None
    pass_through: Dict[str, float]
    latency_ms_median: float
    latency_ms_p95: float
    cost_usd: float
    agreement_evaluator_vs_deep_reader_pearson: Optional[float] = None
    counts: Dict[str, int]
    cache_hit_rate: float


class ResultsFile(BaseModel):
    run_id: str
    goal_id: str
    config: RunConfig
    per_paper: List[PerPaperRecord]
    metrics: RunMetrics


# --- Cache manifest ---

class CacheManifestEntry(BaseModel):
    hash: str
    paper_id: str
    node: Literal["evaluator", "critique", "deep_reader"]
    config_signature: str
    created_at: datetime
```

- [ ] **Step 4: Run tests, expect pass**

```bash
cd testing/benchmark && pytest tests/test_schemas.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add testing/benchmark/lib/schemas.py testing/benchmark/tests/test_schemas.py
git commit -m "feat(benchmark): add pydantic schemas for all JSON file shapes"
```

---

### Task 3: Pricing table (`lib/pricing.py`)

Per-model token rates and cost calculation. Isolated so it's easy to update prices without touching pipeline logic.

**Files:**
- Create: `testing/benchmark/lib/pricing.py`
- Create: `testing/benchmark/tests/test_pricing.py`

- [ ] **Step 1: Write the failing test**

Create `testing/benchmark/tests/test_pricing.py`:
```python
import pytest
from benchmark.lib.pricing import compute_cost_usd, KNOWN_MODELS


def test_known_models_includes_three_targets():
    assert "gpt-4o-mini" in KNOWN_MODELS
    assert "claude-haiku-4-5-20251001" in KNOWN_MODELS
    assert "gpt-5.4-nano-2026-03-17" in KNOWN_MODELS


def test_compute_cost_zero_tokens():
    assert compute_cost_usd("gpt-4o-mini", 0, 0) == 0.0


def test_compute_cost_gpt_4o_mini_one_million_in():
    # $0.15 per 1M input
    cost = compute_cost_usd("gpt-4o-mini", 1_000_000, 0)
    assert cost == pytest.approx(0.15, rel=1e-6)


def test_compute_cost_gpt_4o_mini_one_million_out():
    # $0.60 per 1M output
    cost = compute_cost_usd("gpt-4o-mini", 0, 1_000_000)
    assert cost == pytest.approx(0.60, rel=1e-6)


def test_compute_cost_unknown_model_raises():
    with pytest.raises(KeyError):
        compute_cost_usd("nonexistent-model", 100, 50)
```

- [ ] **Step 2: Run, expect failure**

```bash
cd testing/benchmark && pytest tests/test_pricing.py -v
```

- [ ] **Step 3: Implement `lib/pricing.py`**

```python
"""Per-model token pricing.

Rates expressed as USD per 1M tokens. Update when providers change pricing.
"""

from typing import Dict, NamedTuple


class TokenRate(NamedTuple):
    input_per_million_usd: float
    output_per_million_usd: float


KNOWN_MODELS: Dict[str, TokenRate] = {
    # OpenAI — verify at https://openai.com/api/pricing
    "gpt-4o-mini": TokenRate(0.15, 0.60),
    # Project-defined "gpt-5.4-nano" — adjust when rate-card published
    "gpt-5.4-nano-2026-03-17": TokenRate(0.10, 0.40),
    # Anthropic — verify at https://www.anthropic.com/pricing
    "claude-haiku-4-5-20251001": TokenRate(1.00, 5.00),
}


def compute_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    rate = KNOWN_MODELS[model]
    return (
        tokens_in * rate.input_per_million_usd / 1_000_000
        + tokens_out * rate.output_per_million_usd / 1_000_000
    )
```

- [ ] **Step 4: Run, expect pass**

```bash
cd testing/benchmark && pytest tests/test_pricing.py -v
```

- [ ] **Step 5: Commit**

```bash
git add testing/benchmark/lib/pricing.py testing/benchmark/tests/test_pricing.py
git commit -m "feat(benchmark): add per-model token pricing table"
```

---

### Task 4: LLM response cache (`lib/cache.py`)

Hash-keyed JSON cache backing the "cached real LLM" pattern.

**Files:**
- Create: `testing/benchmark/lib/cache.py`
- Create: `testing/benchmark/tests/test_cache.py`

- [ ] **Step 1: Write the failing test**

Create `testing/benchmark/tests/test_cache.py`:
```python
import json
from datetime import datetime, timezone
from pathlib import Path
from benchmark.lib import cache


def test_compute_key_is_deterministic():
    k1 = cache.compute_key("paper1", "evaluator", "v1", "input-text", "gpt-4o-mini")
    k2 = cache.compute_key("paper1", "evaluator", "v1", "input-text", "gpt-4o-mini")
    assert k1 == k2
    assert len(k1) == 64  # full sha256 hex


def test_compute_key_changes_on_any_field():
    base = cache.compute_key("p", "evaluator", "v1", "x", "m")
    assert cache.compute_key("p2", "evaluator", "v1", "x", "m") != base
    assert cache.compute_key("p", "critique", "v1", "x", "m") != base
    assert cache.compute_key("p", "evaluator", "v2", "x", "m") != base
    assert cache.compute_key("p", "evaluator", "v1", "y", "m") != base
    assert cache.compute_key("p", "evaluator", "v1", "x", "m2") != base


def test_get_returns_none_on_miss(monkeypatch, tmp_path):
    monkeypatch.setenv("BENCHMARK_DATA_DIR", str(tmp_path))
    assert cache.get("evaluator", "deadbeef" * 8) is None


def test_put_then_get_roundtrips(monkeypatch, tmp_path):
    monkeypatch.setenv("BENCHMARK_DATA_DIR", str(tmp_path))
    payload = {"decision": "accept", "score": 7.5, "tokens_in": 100, "tokens_out": 20, "latency_ms": 420}
    key = "ab" * 32
    cache.put("evaluator", key, payload, paper_id="p1", config_signature="cfg-sig")
    got = cache.get("evaluator", key)
    assert got == payload


def test_put_appends_manifest_entry(monkeypatch, tmp_path):
    monkeypatch.setenv("BENCHMARK_DATA_DIR", str(tmp_path))
    payload = {"decision": "accept"}
    cache.put("evaluator", "ab" * 32, payload, paper_id="p1", config_signature="cfg-sig")
    cache.put("critique", "cd" * 32, payload, paper_id="p2", config_signature="cfg-sig")
    manifest = json.loads((tmp_path / "cache_manifest.json").read_text())
    assert len(manifest) == 2
    nodes = {e["node"] for e in manifest}
    assert nodes == {"evaluator", "critique"}
```

- [ ] **Step 2: Run, expect failure**

- [ ] **Step 3: Implement `lib/cache.py`**

```python
"""LLM response cache. Hash-keyed JSON files plus a committed manifest.

Cache key: sha256(paper_id || node || prompt_version || node_input || llm_model)
The cache directory itself is gitignored; the manifest lists what was cached.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from benchmark.lib import paths


def compute_key(paper_id: str, node: str, prompt_version: str,
                node_input: str, llm_model: str) -> str:
    """Stable sha256 hex key. Order matters; never reorder these fields."""
    h = hashlib.sha256()
    for part in (paper_id, node, prompt_version, node_input, llm_model):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")  # separator prevents accidental collisions
    return h.hexdigest()


def get(node: str, key: str) -> Optional[Dict[str, Any]]:
    p = paths.cache_path(node, key)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def put(node: str, key: str, payload: Dict[str, Any],
        paper_id: str, config_signature: str) -> None:
    p = paths.cache_path(node, key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _append_manifest(key, paper_id, node, config_signature)


def _append_manifest(key: str, paper_id: str, node: str, config_signature: str) -> None:
    mp = paths.cache_manifest_path()
    entries = []
    if mp.exists():
        entries = json.loads(mp.read_text(encoding="utf-8"))
    entries.append({
        "hash": key,
        "paper_id": paper_id,
        "node": node,
        "config_signature": config_signature,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(entries, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run, expect pass**

- [ ] **Step 5: Commit**

```bash
git add testing/benchmark/lib/cache.py testing/benchmark/tests/test_cache.py
git commit -m "feat(benchmark): add hash-keyed LLM response cache + manifest"
```

---

### Task 5: Mirrored prompts (`lib/prompts.py`)

We mirror the Phase 1 + Phase 2 prompts here so the harness can swap LLM models cleanly without touching backend code. Each prompt has a `_VERSION` constant — bump it whenever the prompt text changes (this invalidates the cache automatically).

**Files:**
- Create: `testing/benchmark/lib/prompts.py`

- [ ] **Step 1: Implement `lib/prompts.py`**

```python
"""Prompts mirrored from backend/app/agents/graph.py and distiller.py.

When the backend prompts change, update these AND bump the matching _VERSION
constant so the cache invalidates. Version strings are part of the cache key.
"""

# --- Evaluator (mirror of node_evaluator in backend/app/agents/graph.py) ---

EVALUATOR_VERSION = "evaluator:v1"

EVALUATOR_SYSTEM = (
    "You are an academic paper screening AI. Evaluate this paper's abstract "
    "against the user's research criteria.\n\n"
    "CRITERIA:\n{criteria}\n\n"
    "INSTRUCTIONS:\n"
    "- Output 'accept' if the paper clearly matches the criteria.\n"
    "- Output 'borderline' if it partially matches or you are uncertain. "
    "When uncertain, PREFER 'borderline' over 'reject'.\n"
    "- Output 'reject' ONLY if the paper clearly does not match.\n"
    "- Assign a relevance score from 1.0 to 10.0.\n"
    "- Write a brief reasoning trace in reasonbook (internal use only)."
)
EVALUATOR_HUMAN = "Abstract:\n\n{abstract}"


# --- Critique (mirror of node_critique) ---

CRITIQUE_VERSION = "critique:v1"

CRITIQUE_SYSTEM = (
    "You are reviewing a borderline paper recommendation.\n\n"
    "The evaluator was uncertain about this paper for this reason:\n"
    "{reasonbook}\n\n"
    "The user has historically rejected papers with these characteristics:\n"
    "{memory}\n\n"
    "If this paper's abstract matches what the user dislikes, output decision=False (reject).\n"
    "If it avoids the disliked elements, output decision=True (accept)."
)
CRITIQUE_HUMAN = "Abstract:\n\n{abstract}"


# --- Deep Reader (mirror of run_deep_reader) ---

DEEP_READER_VERSION = "deep_reader:v1"

DEEP_READER_SYSTEM = (
    "You are an expert academic paper analyst. Read the full paper text and evaluate "
    "it against the user's research criteria.\n\n"
    "CRITERIA:\n{criteria}\n\n"
    "USER REJECTION HISTORY:\n{feedback_memory}\n\n"
    "INSTRUCTIONS:\n"
    "1. Determine if this paper is truly relevant based on its FULL content "
    "(not just abstract). Output 'accept' or 'reject'.\n"
    "2. Assign a final relevance score from 1.0 to 10.0.\n"
    "3. Write a 2-3 sentence explanation of WHY this paper is relevant to the user. "
    "This will be shown directly to the user in their feed.\n"
    "- If the paper scored well on abstract but the full text reveals it's not actually "
    "relevant, output 'reject' with a low score.\n"
    "- Papers with score below 5.0 will be filtered out."
)
DEEP_READER_HUMAN = "Full paper text:\n\n{text}"


def truncate_markdown(markdown: str, limit: int = 30000) -> str:
    return markdown[:limit] if len(markdown) > limit else markdown
```

- [ ] **Step 2: Commit**

```bash
git add testing/benchmark/lib/prompts.py
git commit -m "feat(benchmark): mirror Phase 1+2 prompts with version constants"
```

---

### Task 6: Multi-provider LLM call factory (`lib/llm.py`)

Builds a structured-output LLM call for any of the three target models. Returns the parsed Pydantic instance plus token counts and latency.

**Files:**
- Create: `testing/benchmark/lib/llm.py`

- [ ] **Step 1: Implement `lib/llm.py`**

```python
"""Multi-provider LLM call factory.

Returns parsed structured output + (tokens_in, tokens_out, latency_ms).
Used by runner.py for evaluator/critique/deep_reader calls.
"""

import time
from typing import Tuple, Type

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel


def _build_llm(model: str, temperature: float = 0.0):
    if model.startswith("claude-"):
        return ChatAnthropic(model=model, temperature=temperature)
    # Default: OpenAI (covers gpt-4o-mini and gpt-5.4-nano-*)
    return ChatOpenAI(model=model, temperature=temperature)


def call_structured(
    model: str,
    output_schema: Type[BaseModel],
    system_template: str,
    human_template: str,
    template_vars: dict,
    temperature: float = 0.0,
) -> Tuple[BaseModel, int, int, float]:
    """Run a structured-output LLM call.

    Returns: (parsed_output, tokens_in, tokens_out, latency_ms)
    Tokens are read from response metadata; if unavailable, returns 0/0
    and the caller can estimate from input/output character length.
    """
    llm = _build_llm(model, temperature=temperature)
    structured = llm.with_structured_output(output_schema, include_raw=True)

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", human_template),
    ])

    t0 = time.perf_counter()
    result = (prompt | structured).invoke(template_vars)
    latency_ms = (time.perf_counter() - t0) * 1000.0

    parsed = result["parsed"]
    raw = result.get("raw")
    tokens_in = 0
    tokens_out = 0
    if raw is not None and getattr(raw, "usage_metadata", None):
        tokens_in = int(raw.usage_metadata.get("input_tokens", 0))
        tokens_out = int(raw.usage_metadata.get("output_tokens", 0))
    return parsed, tokens_in, tokens_out, latency_ms
```

- [ ] **Step 2: Commit**

```bash
git add testing/benchmark/lib/llm.py
git commit -m "feat(benchmark): add multi-provider structured-output LLM factory"
```

---

### Task 7: Goal distiller wrapper (`lib/distill.py`)

Wraps `backend.app.agents.distiller.run_goal_distiller` with file I/O and freezing semantics.

**Files:**
- Create: `testing/benchmark/lib/distill.py`

- [ ] **Step 1: Implement `lib/distill.py`**

```python
"""GoalDistiller wrapper: distill, freeze, persist."""

import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

# Allow importing from ../backend
_BACKEND = Path(__file__).resolve().parents[3] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.agents.distiller import run_goal_distiller  # type: ignore

from benchmark.lib import paths
from benchmark.lib.schemas import Criterion, GoalFile, ScoringRule


def distill(raw_goal: str, categories: List[str] | None = None,
            topics: List[str] | None = None,
            content_interest: List[str] | None = None) -> tuple[List[Criterion], str]:
    """Run the GoalDistiller. Returns (criteria, lexical_query)."""
    out = run_goal_distiller(
        categories=categories or [],
        topics=topics or [],
        content_interest=content_interest or [],
        filtering_goal=raw_goal,
    )
    criteria = [Criterion(id=f"c{i+1}", text=t)
                for i, t in enumerate(out.distilled_criteria)]
    return criteria, out.lexical_query


def freeze(goal_id: str, raw_goal: str, criteria: List[Criterion],
           lexical_query: str, distiller_model: str = "gpt-4o-mini") -> GoalFile:
    """Write goals/{goal_id}.json. Refuses to overwrite — frozen is frozen."""
    path = paths.goal_path(goal_id)
    if path.exists():
        raise FileExistsError(
            f"{path} already exists — frozen goals are immutable. "
            f"Use a new goal_id (e.g. {goal_id}_v2) to revise."
        )

    n = len(criteria)
    threshold = math.ceil(n / 2) if n > 0 else 0
    g = GoalFile(
        goal_id=goal_id,
        raw_goal=raw_goal,
        distilled_criteria=criteria,
        lexical_query=lexical_query,
        scoring_rule=ScoringRule(type="majority", threshold=threshold),
        frozen_at=datetime.now(timezone.utc),
        distiller_model=distiller_model,
    )
    paths.ensure_subdirs()
    path.write_text(g.model_dump_json(indent=2), encoding="utf-8")
    return g


def load(goal_id: str) -> GoalFile:
    path = paths.goal_path(goal_id)
    return GoalFile.model_validate_json(path.read_text(encoding="utf-8"))
```

- [ ] **Step 2: Commit**

```bash
git add testing/benchmark/lib/distill.py
git commit -m "feat(benchmark): add goal distiller wrapper with freeze semantics"
```

---

### Task 8: Candidate retrievers (`lib/pull.py`)

Three retrievers: BM25-only, SPECTER2-only, RRF. All async, all read-only.

**Files:**
- Create: `testing/benchmark/lib/pull.py`

- [ ] **Step 1: Implement `lib/pull.py`**

```python
"""Candidate retrievers: BM25, SPECTER2, RRF.

Each returns a list of CandidatePaper objects pulled from the prod papers table.
SPECTER2 embedding for the goal is computed via Modal GPU on demand.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker

# Allow importing from ../backend
_BACKEND = Path(__file__).resolve().parents[3] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.db.retrieval import perform_hybrid_rrf_search  # type: ignore
from app.worker.modal_client import specter2_embed_batch  # type: ignore

from benchmark.lib import paths
from benchmark.lib.schemas import CandidatePaper, CandidatesFile


def _engine():
    url = os.environ.get("BENCHMARK_DB_URL")
    if not url:
        raise RuntimeError(
            "BENCHMARK_DB_URL is unset. Copy testing/.env.benchmark.example "
            "to testing/.env.benchmark and load it before running."
        )
    return create_async_engine(url, future=True, pool_pre_ping=True)


def _session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


async def smoke_test_db_access() -> int:
    """Run a SELECT 1 + count papers. Fails fast with clear message if DB unreachable."""
    engine = _engine()
    factory = _session_factory(engine)
    async with factory() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM papers"))
        return result.scalar_one()


async def embed_goal(raw_goal: str, goal_id: str) -> List[float]:
    """Compute SPECTER2 embedding for the goal text. Used for SPECTER2 + RRF retrievers."""
    pairs = [(goal_id, raw_goal)]
    embeddings = await specter2_embed_batch(pairs)
    return embeddings[0]


async def pull_bm25(session: AsyncSession, lexical_query: str, k: int = 30) -> List[CandidatePaper]:
    stmt = text("""
        SELECT p.id, p.title, p.abstract, p.authors, p.pdf_url, p.source_url, p.published_at,
               ts_rank_cd(p.search_vector, websearch_to_tsquery('english', :q)) AS lex_score,
               EXISTS (
                 SELECT 1 FROM user_papers up
                 WHERE up.paper_id = p.id AND up.extracted_markdown IS NOT NULL
               ) AS has_md
        FROM papers p
        WHERE p.search_vector @@ websearch_to_tsquery('english', :q)
        ORDER BY lex_score DESC
        LIMIT :k
    """)
    rows = (await session.execute(stmt, {"q": lexical_query, "k": k})).mappings().fetchall()
    return [
        CandidatePaper(
            paper_id=r["id"], title=r["title"], abstract=r["abstract"],
            authors=list(r["authors"] or []), pdf_url=r["pdf_url"],
            rrf_rank=i + 1, rrf_score=float(r["lex_score"]),
            has_extracted_markdown=bool(r["has_md"]),
        )
        for i, r in enumerate(rows)
    ]


async def pull_specter2(session: AsyncSession, goal_embedding: List[float], k: int = 30) -> List[CandidatePaper]:
    vector_str = f"[{','.join(map(str, goal_embedding))}]"
    stmt = text("""
        SELECT p.id, p.title, p.abstract, p.authors, p.pdf_url, p.source_url, p.published_at,
               1 - (p.embedding <=> CAST(:emb AS vector)) AS sim,
               EXISTS (
                 SELECT 1 FROM user_papers up
                 WHERE up.paper_id = p.id AND up.extracted_markdown IS NOT NULL
               ) AS has_md
        FROM papers p
        WHERE p.embedding IS NOT NULL
        ORDER BY p.embedding <=> CAST(:emb AS vector)
        LIMIT :k
    """)
    rows = (await session.execute(stmt, {"emb": vector_str, "k": k})).mappings().fetchall()
    return [
        CandidatePaper(
            paper_id=r["id"], title=r["title"], abstract=r["abstract"],
            authors=list(r["authors"] or []), pdf_url=r["pdf_url"],
            rrf_rank=i + 1, rrf_score=float(r["sim"]),
            has_extracted_markdown=bool(r["has_md"]),
        )
        for i, r in enumerate(rows)
    ]


async def pull_rrf(session: AsyncSession, lexical_query: str, goal_embedding: List[float],
                   k: int = 30, k_semantic: int = 30, k_lexical: int = 60) -> List[CandidatePaper]:
    rows = await perform_hybrid_rrf_search(
        session=session,
        query_text=lexical_query,
        query_embedding=goal_embedding,
        limit=k,
        rrf_k_semantic=k_semantic,
        rrf_k_lexical=k_lexical,
    )
    # Augment with markdown availability via a single follow-up query
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    md_q = text("""
        SELECT paper_id, COUNT(*) > 0 AS has_md
        FROM user_papers
        WHERE paper_id = ANY(:ids) AND extracted_markdown IS NOT NULL
        GROUP BY paper_id
    """)
    md_rows = (await session.execute(md_q, {"ids": ids})).mappings().fetchall()
    md_set = {r["paper_id"] for r in md_rows if r["has_md"]}

    return [
        CandidatePaper(
            paper_id=r["id"], title=r["title"], abstract=r["abstract"],
            authors=list(r.get("authors") or []), pdf_url=r.get("pdf_url"),
            rrf_rank=i + 1, rrf_score=float(r["rrf_score"]),
            has_extracted_markdown=r["id"] in md_set,
        )
        for i, r in enumerate(rows)
    ]


async def pull_and_save(goal_id: str, retriever: Literal["bm25", "specter2", "rrf"],
                        lexical_query: str, goal_embedding: List[float],
                        k: int = 30) -> CandidatesFile:
    engine = _engine()
    factory = _session_factory(engine)
    async with factory() as session:
        if retriever == "bm25":
            papers = await pull_bm25(session, lexical_query, k=k)
            rrf_params = None
        elif retriever == "specter2":
            papers = await pull_specter2(session, goal_embedding, k=k)
            rrf_params = None
        else:
            papers = await pull_rrf(session, lexical_query, goal_embedding, k=k)
            rrf_params = {"k_semantic": 30, "k_lexical": 60}

    cf = CandidatesFile(
        goal_id=goal_id, retriever=retriever, top_k=k,
        rrf_params=rrf_params, pulled_at=datetime.now(timezone.utc),
        papers=papers,
    )
    paths.ensure_subdirs()
    paths.candidates_path(goal_id, retriever).write_text(
        cf.model_dump_json(indent=2), encoding="utf-8"
    )
    return cf
```

- [ ] **Step 2: Commit**

```bash
git add testing/benchmark/lib/pull.py
git commit -m "feat(benchmark): add bm25/specter2/rrf candidate retrievers"
```

---

### Task 9: Metrics — precision, Wilson CI, pass-through, agreement (`lib/metrics.py`)

**Files:**
- Create: `testing/benchmark/lib/metrics.py`
- Create: `testing/benchmark/tests/test_metrics.py`

- [ ] **Step 1: Write the failing test**

Create `testing/benchmark/tests/test_metrics.py`:
```python
import pytest
from benchmark.lib.metrics import (
    wilson_ci_95, precision_with_ci, pass_through_rates, pearson,
)


def test_wilson_ci_zero_observations():
    lo, hi = wilson_ci_95(0, 0)
    assert lo == 0.0 and hi == 1.0


def test_wilson_ci_perfect():
    lo, hi = wilson_ci_95(10, 10)
    assert hi == pytest.approx(1.0, abs=1e-6)
    assert lo > 0.6  # 10/10 still has lower bound below 1


def test_wilson_ci_half():
    lo, hi = wilson_ci_95(5, 10)
    assert lo < 0.5 < hi


def test_precision_with_ci_excludes_borderline():
    # tp=3, fp=2, fn=1, borderline=4 — borderline must not affect denominator
    p, (lo, hi) = precision_with_ci(tp=3, fp=2)
    assert p == pytest.approx(0.6)
    assert 0 <= lo <= p <= hi <= 1


def test_precision_zero_predictions():
    p, (lo, hi) = precision_with_ci(tp=0, fp=0)
    assert p == 0.0
    assert lo == 0.0 and hi == 1.0


def test_pass_through_basic():
    rates = pass_through_rates(
        before={"evaluator": 30, "critique": 18, "deep_reader": 14},
        after={"evaluator": 18, "critique": 14, "deep_reader": 12},
    )
    assert rates["evaluator"] == pytest.approx(0.6)
    assert rates["critique"] == pytest.approx(14 / 18)
    assert rates["deep_reader"] == pytest.approx(12 / 14)


def test_pearson_perfect_correlation():
    r = pearson([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
    assert r == pytest.approx(1.0)


def test_pearson_zero_variance_returns_none():
    assert pearson([1, 1, 1], [1, 2, 3]) is None
```

- [ ] **Step 2: Run, expect failure**

- [ ] **Step 3: Implement `lib/metrics.py`**

```python
"""Precision, Wilson 95% CI, pass-through rates, Pearson agreement.

All functions are pure — no I/O, no side effects.
"""

import math
from typing import Dict, List, Optional, Tuple


def wilson_ci_95(successes: int, trials: int) -> Tuple[float, float]:
    """Wilson score 95% CI for a binomial proportion. Stable at extremes."""
    if trials == 0:
        return (0.0, 1.0)
    z = 1.96
    p = successes / trials
    denom = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denom
    half = (z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials))) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def precision_with_ci(tp: int, fp: int) -> Tuple[float, Tuple[float, float]]:
    """Precision + Wilson CI. Borderline papers should be excluded *before* calling this."""
    n = tp + fp
    if n == 0:
        return (0.0, (0.0, 1.0))
    return (tp / n, wilson_ci_95(tp, n))


def pass_through_rates(before: Dict[str, int], after: Dict[str, int]) -> Dict[str, float]:
    """survivors_after_node / survivors_before_node, per stage."""
    out: Dict[str, float] = {}
    for stage, b in before.items():
        a = after.get(stage, 0)
        out[stage] = (a / b) if b > 0 else 0.0
    return out


def pearson(xs: List[float], ys: List[float]) -> Optional[float]:
    """Pearson r. Returns None if variance is zero in either series."""
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def percentile(values: List[float], q: float) -> float:
    """Linear-interpolation percentile, q in [0, 100]. Empty list → 0.0."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    pos = (q / 100.0) * (len(s) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)
```

- [ ] **Step 4: Run, expect pass**

- [ ] **Step 5: Commit**

```bash
git add testing/benchmark/lib/metrics.py testing/benchmark/tests/test_metrics.py
git commit -m "feat(benchmark): add precision/Wilson-CI/pass-through/Pearson metrics"
```

---

### Task 10: Cascade runner (`lib/runner.py`)

The orchestration core: for each labeled paper, route through Evaluator → (maybe Critique) → (maybe Deep Reader), honoring cache + toggle config. Returns a fully populated `ResultsFile`.

**Files:**
- Create: `testing/benchmark/lib/runner.py`
- Create: `testing/benchmark/tests/test_runner.py`

- [ ] **Step 1: Write the failing test**

Create `testing/benchmark/tests/test_runner.py`:
```python
"""Runner test — uses a fake LLM call so no network or cache hits."""

import pytest
from datetime import datetime, timezone
from benchmark.lib.runner import build_run_id, decide_routes, summarize_per_paper
from benchmark.lib.schemas import (
    CandidatePaper, CandidatesFile, RunConfig, StageOutcome, PerPaperRecord,
)


def test_build_run_id_format():
    cfg = RunConfig(model="gpt-4o-mini", evaluator=True, critique=True,
                    deep_reader=True, feedback_memory="empty", deep_scan_limit=10)
    run_id = build_run_id("security_v1", cfg)
    parts = run_id.split("__")
    assert parts[0] == "security_v1"
    assert len(parts[1]) == 8  # config hash
    assert parts[2].endswith("Z") or "T" in parts[2]


def test_decide_routes_accept_skips_critique():
    routes = decide_routes(evaluator_decision="accept", critique_enabled=True)
    assert routes == ["evaluator"]


def test_decide_routes_borderline_uses_critique():
    routes = decide_routes(evaluator_decision="borderline", critique_enabled=True)
    assert routes == ["evaluator", "critique"]


def test_decide_routes_borderline_critique_off_drops_paper():
    routes = decide_routes(evaluator_decision="borderline", critique_enabled=False)
    assert routes == ["evaluator"]


def test_decide_routes_reject_skips_critique():
    routes = decide_routes(evaluator_decision="reject", critique_enabled=True)
    assert routes == ["evaluator"]


def test_summarize_per_paper_final_decision_logic():
    # Evaluator accept, no critique, no deep reader → final accept
    rec = summarize_per_paper(
        paper_id="p1",
        evaluator=StageOutcome(decision="accept", score=7.5, latency_ms=400, tokens_in=300, tokens_out=40, cached=False),
        critique=None,
        deep_reader=None,
        gt_label=1,
    )
    assert rec.final_decision == "accept"
    assert rec.final_score == 7.5


def test_summarize_per_paper_critique_overrides():
    # Borderline → critique rejects → final reject
    rec = summarize_per_paper(
        paper_id="p1",
        evaluator=StageOutcome(decision="borderline", score=5.5, latency_ms=400, tokens_in=300, tokens_out=40, cached=False),
        critique=StageOutcome(decision="reject", score=None, latency_ms=400, tokens_in=200, tokens_out=20, cached=False),
        deep_reader=None,
        gt_label=0,
    )
    assert rec.final_decision == "reject"


def test_summarize_per_paper_deep_reader_final_score_wins():
    rec = summarize_per_paper(
        paper_id="p1",
        evaluator=StageOutcome(decision="accept", score=7.5, latency_ms=400, tokens_in=300, tokens_out=40, cached=False),
        critique=None,
        deep_reader=StageOutcome(decision="accept", score=8.2, latency_ms=1200, tokens_in=4000, tokens_out=180, cached=False),
        gt_label=1,
    )
    assert rec.final_decision == "accept"
    assert rec.final_score == 8.2
```

- [ ] **Step 2: Run, expect failure**

- [ ] **Step 3: Implement `lib/runner.py`**

```python
"""Cascade runner: orchestrates Evaluator → Critique → Deep Reader per paper.

Honors the cache layer transparently and produces a ResultsFile.
"""

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

from benchmark.lib import cache, metrics, paths, pricing, prompts
from benchmark.lib.llm import call_structured
from benchmark.lib.schemas import (
    CandidatesFile, GoalFile, LabelsFile, PerPaperRecord, ResultsFile, RunConfig,
    RunMetrics, StageOutcome,
)

# Allow importing backend agent schemas
_BACKEND = Path(__file__).resolve().parents[3] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
from app.agents.schemas import EvaluatorOutput, CritiqueOutput, DeepReaderOutput  # type: ignore


SEEDED_MEMORY = (
    "User has rejected papers that: focus on pure theoretical results without empirical "
    "validation; rely solely on synthetic benchmarks; lack reproducible code; or are "
    "purely cryptographic in nature without an AI/ML decision component; or apply RL to "
    "toy environments without real-world deployment evidence."
)


# -------- helpers --------

def build_run_id(goal_id: str, config: RunConfig) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    return f"{goal_id}__{config.config_hash()}__{ts}"


def decide_routes(evaluator_decision: str, critique_enabled: bool) -> List[str]:
    """Route a paper based on evaluator decision and toggle.

    Critique only fires for borderline papers when enabled.
    """
    routes = ["evaluator"]
    if evaluator_decision == "borderline" and critique_enabled:
        routes.append("critique")
    return routes


def _final_from(evaluator: StageOutcome, critique: Optional[StageOutcome],
                deep_reader: Optional[StageOutcome]) -> Tuple[Literal["accept", "reject"], Optional[float]]:
    if deep_reader is not None:
        return (deep_reader.decision, deep_reader.score)  # type: ignore[return-value]
    if critique is not None:
        return ("accept" if critique.decision == "accept" else "reject", evaluator.score)
    if evaluator.decision == "accept":
        return ("accept", evaluator.score)
    return ("reject", evaluator.score)


def summarize_per_paper(paper_id: str, evaluator: StageOutcome,
                        critique: Optional[StageOutcome],
                        deep_reader: Optional[StageOutcome],
                        gt_label: Optional[int]) -> PerPaperRecord:
    final_decision, final_score = _final_from(evaluator, critique, deep_reader)
    return PerPaperRecord(
        paper_id=paper_id,
        stages={"evaluator": evaluator, "critique": critique, "deep_reader": deep_reader},
        final_decision=final_decision,
        final_score=final_score,
        gt_label=gt_label,
    )


# -------- per-stage callers (with cache) --------

def _node_input_evaluator(abstract: str, criteria: List[str]) -> str:
    return json.dumps({"abstract": abstract, "criteria": criteria}, sort_keys=True)


def _call_evaluator(model: str, paper_id: str, abstract: str, criteria: List[str],
                    config_signature: str) -> StageOutcome:
    node_input = _node_input_evaluator(abstract, criteria)
    key = cache.compute_key(paper_id, "evaluator", prompts.EVALUATOR_VERSION, node_input, model)
    hit = cache.get("evaluator", key)
    if hit is not None:
        return StageOutcome(decision=hit["decision"], score=hit["score"],
                            latency_ms=hit["latency_ms"], tokens_in=hit["tokens_in"],
                            tokens_out=hit["tokens_out"], cached=True)

    parsed, tin, tout, lat = call_structured(
        model=model, output_schema=EvaluatorOutput,
        system_template=prompts.EVALUATOR_SYSTEM, human_template=prompts.EVALUATOR_HUMAN,
        template_vars={"criteria": "\n- ".join(criteria), "abstract": abstract},
        temperature=0.0,
    )
    payload = {"decision": parsed.decision, "score": parsed.score, "reasonbook": parsed.reasonbook,
               "latency_ms": lat, "tokens_in": tin, "tokens_out": tout}
    cache.put("evaluator", key, payload, paper_id=paper_id, config_signature=config_signature)
    return StageOutcome(decision=parsed.decision, score=parsed.score,
                        latency_ms=lat, tokens_in=tin, tokens_out=tout, cached=False)


def _node_input_critique(abstract: str, reasonbook: str, memory: str) -> str:
    return json.dumps({"abstract": abstract, "reasonbook": reasonbook, "memory": memory}, sort_keys=True)


def _call_critique(model: str, paper_id: str, abstract: str, reasonbook: str,
                   memory: str, config_signature: str) -> StageOutcome:
    node_input = _node_input_critique(abstract, reasonbook, memory)
    key = cache.compute_key(paper_id, "critique", prompts.CRITIQUE_VERSION, node_input, model)
    hit = cache.get("critique", key)
    if hit is not None:
        return StageOutcome(decision=hit["decision"], score=None,
                            latency_ms=hit["latency_ms"], tokens_in=hit["tokens_in"],
                            tokens_out=hit["tokens_out"], cached=True)

    parsed, tin, tout, lat = call_structured(
        model=model, output_schema=CritiqueOutput,
        system_template=prompts.CRITIQUE_SYSTEM, human_template=prompts.CRITIQUE_HUMAN,
        template_vars={"reasonbook": reasonbook, "memory": memory, "abstract": abstract},
        temperature=0.0,
    )
    decision_str = "accept" if parsed.decision else "reject"
    payload = {"decision": decision_str, "reasonbook": parsed.reasonbook,
               "latency_ms": lat, "tokens_in": tin, "tokens_out": tout}
    cache.put("critique", key, payload, paper_id=paper_id, config_signature=config_signature)
    return StageOutcome(decision=decision_str, score=None,
                        latency_ms=lat, tokens_in=tin, tokens_out=tout, cached=False)


def _node_input_deep_reader(text: str, criteria: List[str], memory: str) -> str:
    return json.dumps({"text": text[:30000], "criteria": criteria, "memory": memory}, sort_keys=True)


def _call_deep_reader(model: str, paper_id: str, text: str, criteria: List[str],
                      memory: str, config_signature: str) -> StageOutcome:
    truncated = prompts.truncate_markdown(text)
    node_input = _node_input_deep_reader(truncated, criteria, memory)
    key = cache.compute_key(paper_id, "deep_reader", prompts.DEEP_READER_VERSION, node_input, model)
    hit = cache.get("deep_reader", key)
    if hit is not None:
        return StageOutcome(decision=hit["decision"], score=hit["score"],
                            latency_ms=hit["latency_ms"], tokens_in=hit["tokens_in"],
                            tokens_out=hit["tokens_out"], cached=True)

    parsed, tin, tout, lat = call_structured(
        model=model, output_schema=DeepReaderOutput,
        system_template=prompts.DEEP_READER_SYSTEM, human_template=prompts.DEEP_READER_HUMAN,
        template_vars={"criteria": "\n- ".join(criteria), "feedback_memory": memory or "No rejection history.", "text": truncated},
        temperature=0.3,
    )
    payload = {"decision": parsed.decision, "score": parsed.score, "explanation": parsed.explanation,
               "latency_ms": lat, "tokens_in": tin, "tokens_out": tout}
    cache.put("deep_reader", key, payload, paper_id=paper_id, config_signature=config_signature)
    return StageOutcome(decision=parsed.decision, score=parsed.score,
                        latency_ms=lat, tokens_in=tin, tokens_out=tout, cached=False)


# -------- orchestrator --------

def _gt_for(paper_id: str, labels: LabelsFile) -> Optional[int]:
    if paper_id not in labels.labels:
        return None
    lbl = labels.labels[paper_id]
    if lbl.borderline:
        return None
    return lbl.ground_truth_score


def _fetch_markdown(paper_id: str) -> Optional[str]:
    """Read UserPaper.extracted_markdown from prod DB. Returns None if missing.

    Never re-runs Marker. We just take what's already cached.
    """
    import asyncio
    from sqlalchemy import text as sql_text
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    import os

    async def _go() -> Optional[str]:
        engine = create_async_engine(os.environ["BENCHMARK_DB_URL"], future=True)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as s:
            row = (await s.execute(
                sql_text("SELECT extracted_markdown FROM user_papers WHERE paper_id = :pid AND extracted_markdown IS NOT NULL LIMIT 1"),
                {"pid": paper_id},
            )).first()
            return row[0] if row else None

    return asyncio.get_event_loop().run_until_complete(_go()) if not asyncio.get_event_loop().is_running() else asyncio.run(_go())


def run(goal_id: str, config: RunConfig, candidates: CandidatesFile,
        labels: LabelsFile, criteria: List[str]) -> ResultsFile:
    """Execute the cascade for every labeled paper. Returns ResultsFile (not yet written)."""
    memory = SEEDED_MEMORY if config.feedback_memory == "seeded" else ""
    config_signature = config.config_hash()

    # Phase 1: Evaluator (+ optional Critique) for ALL labeled papers
    phase1: List[Tuple[str, StageOutcome, Optional[StageOutcome]]] = []
    by_id = {p.paper_id: p for p in candidates.papers}
    for pid in labels.labels.keys():
        paper = by_id.get(pid)
        if paper is None:
            continue
        ev = _call_evaluator(config.model, pid, paper.abstract, criteria, config_signature)
        cr: Optional[StageOutcome] = None
        if ev.decision == "borderline" and config.critique:
            cr = _call_critique(config.model, pid, paper.abstract,
                                reasonbook="(reasonbook from cached evaluator response)",
                                memory=memory, config_signature=config_signature)
        phase1.append((pid, ev, cr))

    # Determine which papers go to Deep Reader: top-K by evaluator score among accepted
    accepted = [(pid, ev, cr) for (pid, ev, cr) in phase1
                if (ev.decision == "accept") or (cr is not None and cr.decision == "accept")]
    accepted.sort(key=lambda t: t[1].score or 0.0, reverse=True)
    top_k_ids = {t[0] for t in accepted[:config.deep_scan_limit]} if config.deep_reader else set()

    per_paper: List[PerPaperRecord] = []
    missing_fulltext = 0
    for (pid, ev, cr) in phase1:
        dr: Optional[StageOutcome] = None
        if pid in top_k_ids:
            md = _fetch_markdown(pid)
            if md is None:
                missing_fulltext += 1
                # Fall back to abstract-only by passing the abstract as "text"
                md = by_id[pid].abstract
            dr = _call_deep_reader(config.model, pid, md, criteria, memory, config_signature)
        gt = _gt_for(pid, labels)
        per_paper.append(summarize_per_paper(pid, ev, cr, dr, gt))

    # Aggregate metrics
    metrics_block = _compute_metrics(per_paper, config.model, missing_fulltext)
    run_id = build_run_id(goal_id, config)
    return ResultsFile(run_id=run_id, goal_id=goal_id, config=config,
                       per_paper=per_paper, metrics=metrics_block)


def _compute_metrics(per_paper: List[PerPaperRecord], model: str, missing_fulltext: int) -> RunMetrics:
    # tp/fp/fn against ground truth (None gt = borderline excluded)
    final_accept = [r for r in per_paper if r.final_decision == "accept" and r.gt_label is not None]
    final_reject = [r for r in per_paper if r.final_decision == "reject" and r.gt_label is not None]
    tp = sum(1 for r in final_accept if r.gt_label == 1)
    fp = sum(1 for r in final_accept if r.gt_label == 0)
    fn = sum(1 for r in final_reject if r.gt_label == 1)
    borderline_excluded = sum(1 for r in per_paper if r.gt_label is None)
    p_final, ci = metrics.precision_with_ci(tp, fp)

    # Per-stage precision: at each stage exit, what fraction of "accept" outcomes were correct?
    def precision_after(stage: str) -> Optional[float]:
        accept_at_stage: List[PerPaperRecord] = []
        for r in per_paper:
            if r.gt_label is None:
                continue
            s = r.stages.get(stage)
            if stage == "evaluator" and s is not None and s.decision == "accept":
                accept_at_stage.append(r)
            elif stage == "critique" and s is not None and s.decision == "accept":
                accept_at_stage.append(r)
            elif stage == "deep_reader" and s is not None and s.decision == "accept":
                accept_at_stage.append(r)
        if not accept_at_stage:
            return None
        return sum(1 for r in accept_at_stage if r.gt_label == 1) / len(accept_at_stage)

    # Pass-through: counts entering vs surviving
    n_total = len(per_paper)
    surv_eval = sum(1 for r in per_paper if (r.stages.get("evaluator") and r.stages["evaluator"].decision == "accept")
                    or (r.stages.get("critique") and r.stages["critique"].decision == "accept"))
    n_to_critique = sum(1 for r in per_paper if r.stages.get("evaluator") and r.stages["evaluator"].decision == "borderline")
    surv_crit = sum(1 for r in per_paper if r.stages.get("critique") and r.stages["critique"].decision == "accept")
    n_to_dr = sum(1 for r in per_paper if r.stages.get("deep_reader") is not None)
    surv_dr = sum(1 for r in per_paper if r.stages.get("deep_reader") and r.stages["deep_reader"].decision == "accept")
    pt = metrics.pass_through_rates(
        before={"evaluator": n_total, "critique": n_to_critique, "deep_reader": n_to_dr},
        after={"evaluator": surv_eval, "critique": surv_crit, "deep_reader": surv_dr},
    )

    # Latency + cost
    all_lat: List[float] = []
    total_in = 0
    total_out = 0
    cache_hits = 0
    cache_calls = 0
    ev_scores: List[float] = []
    dr_scores: List[float] = []
    for r in per_paper:
        for stage_name, s in r.stages.items():
            if s is None:
                continue
            all_lat.append(s.latency_ms)
            total_in += s.tokens_in
            total_out += s.tokens_out
            cache_calls += 1
            if s.cached:
                cache_hits += 1
            if stage_name == "evaluator" and s.score is not None:
                ev_scores.append(s.score)
            if stage_name == "deep_reader" and s.score is not None:
                dr_scores.append(s.score)
    cost = pricing.compute_cost_usd(model, total_in, total_out)
    cache_hit_rate = (cache_hits / cache_calls) if cache_calls else 0.0

    # Pearson on paired (evaluator_score, deep_reader_score) where both exist
    paired_ev: List[float] = []
    paired_dr: List[float] = []
    for r in per_paper:
        ev = r.stages.get("evaluator")
        dr = r.stages.get("deep_reader")
        if ev and dr and ev.score is not None and dr.score is not None:
            paired_ev.append(ev.score)
            paired_dr.append(dr.score)
    pearson_r = metrics.pearson(paired_ev, paired_dr)

    return RunMetrics(
        precision_final=p_final, precision_final_ci=ci,
        precision_after_evaluator=precision_after("evaluator"),
        precision_after_critique=precision_after("critique"),
        precision_after_deep_reader=precision_after("deep_reader"),
        pass_through=pt,
        latency_ms_median=metrics.percentile(all_lat, 50),
        latency_ms_p95=metrics.percentile(all_lat, 95),
        cost_usd=cost,
        agreement_evaluator_vs_deep_reader_pearson=pearson_r,
        counts={"tp": tp, "fp": fp, "fn": fn,
                "borderline_excluded": borderline_excluded,
                "missing_fulltext": missing_fulltext},
        cache_hit_rate=cache_hit_rate,
    )


def save_result(result: ResultsFile) -> Path:
    paths.ensure_subdirs()
    p = paths.result_path(result.run_id)
    p.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return p
```

- [ ] **Step 4: Run, expect pass**

```bash
cd testing/benchmark && pytest tests/test_runner.py -v
```
Expected: 8 passed (no LLM calls — only the pure helpers are tested).

- [ ] **Step 5: Commit**

```bash
git add testing/benchmark/lib/runner.py testing/benchmark/tests/test_runner.py
git commit -m "feat(benchmark): add cascade runner with cache + per-stage metrics"
```

---

### Task 11: Chart styling and chart functions (`lib/chart_style.py`, `lib/charts.py`)

Pure functions returning matplotlib figures. Page 4 calls them. We implement Charts 1, 5, 8, 10 (the four called out in spec §12) plus Chart 3 (cost/precision frontier). The remaining charts in the catalog are listed in `charts.py` as `NotImplementedError` stubs the user can fill in later.

**Files:**
- Create: `testing/benchmark/lib/chart_style.py`
- Create: `testing/benchmark/lib/charts.py`

- [ ] **Step 1: Implement `lib/chart_style.py`**

```python
"""Shared matplotlib style: Okabe-Ito palette, thesis-ready fonts."""

import matplotlib as mpl

OKABE_ITO = ["#000000", "#E69F00", "#56B4E9", "#009E73",
             "#F0E442", "#0072B2", "#D55E00", "#CC79A7"]


def apply_thesis_style() -> None:
    mpl.rcParams.update({
        "axes.prop_cycle": mpl.cycler(color=OKABE_ITO),
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "legend.fontsize": 9,
        "figure.dpi": 100,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
    })
```

- [ ] **Step 2: Implement `lib/charts.py`**

```python
"""Chart-building functions. Each takes ResultsFile(s) → matplotlib Figure.

The 10-chart catalog from spec §7. Implemented now: 1, 3, 5, 8, 10.
The remaining are stubs — fill in as thesis needs evolve.
"""

from typing import List

import matplotlib.pyplot as plt

from benchmark.lib.chart_style import apply_thesis_style
from benchmark.lib.schemas import ResultsFile


def chart1_precision_by_stage(result: ResultsFile) -> plt.Figure:
    apply_thesis_style()
    m = result.metrics
    stages = ["after Evaluator", "after Critique", "after Deep Reader", "Final"]
    values = [m.precision_after_evaluator, m.precision_after_critique,
              m.precision_after_deep_reader, m.precision_final]
    # Replace None with 0 and mark with hatching by collecting indices
    none_mask = [v is None for v in values]
    values = [v if v is not None else 0.0 for v in values]
    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(stages, values)
    for i, b in enumerate(bars):
        if none_mask[i]:
            b.set_hatch("//")
            b.set_alpha(0.3)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Precision")
    ax.set_title(f"Precision by stage — {result.goal_id} / {result.config.model}")
    return fig


def chart3_precision_cost_scatter(results: List[ResultsFile]) -> plt.Figure:
    apply_thesis_style()
    fig, ax = plt.subplots(figsize=(6, 4))
    for r in results:
        ax.scatter(r.metrics.cost_usd, r.metrics.precision_final, s=60)
        ax.annotate(f"K={r.config.deep_scan_limit}",
                    (r.metrics.cost_usd, r.metrics.precision_final),
                    xytext=(5, 5), textcoords="offset points", fontsize=8)
    ax.set_xlabel("Cost (USD)")
    ax.set_ylabel("Precision")
    ax.set_ylim(0, 1)
    ax.set_title("Precision × Cost frontier")
    return fig


def chart5_deep_reader_ablation(off: ResultsFile, on: ResultsFile) -> plt.Figure:
    apply_thesis_style()
    labels = ["Deep Reader OFF", "Deep Reader ON"]
    p = [off.metrics.precision_final, on.metrics.precision_final]
    ci = [off.metrics.precision_final_ci, on.metrics.precision_final_ci]
    err_low = [p[i] - ci[i][0] for i in range(2)]
    err_high = [ci[i][1] - p[i] for i in range(2)]
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.bar(labels, p, yerr=[err_low, err_high], capsize=6)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Precision (95% Wilson CI)")
    ax.set_title(f"Deep Reader ablation — {off.goal_id}")
    return fig


def chart8_cross_goal(results_by_goal: dict) -> plt.Figure:
    """results_by_goal: {goal_id: ResultsFile} — same config across goals."""
    apply_thesis_style()
    goals = list(results_by_goal.keys())
    p = [results_by_goal[g].metrics.precision_final for g in goals]
    ci = [results_by_goal[g].metrics.precision_final_ci for g in goals]
    err_low = [p[i] - ci[i][0] for i in range(len(goals))]
    err_high = [ci[i][1] - p[i] for i in range(len(goals))]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(goals, p, yerr=[err_low, err_high], capsize=6)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Precision (95% Wilson CI)")
    ax.set_title("Cross-goal generalizability")
    return fig


def chart10_model_comparison(results_by_model: dict) -> plt.Figure:
    """results_by_model: {model_name: ResultsFile} — same goal across models."""
    apply_thesis_style()
    models = list(results_by_model.keys())
    p = [results_by_model[m].metrics.precision_final for m in models]
    cost = [results_by_model[m].metrics.cost_usd for m in models]
    lat = [results_by_model[m].metrics.latency_ms_median / 1000.0 for m in models]
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    axes[0].bar(models, p); axes[0].set_ylim(0, 1); axes[0].set_title("Precision"); axes[0].tick_params(axis="x", rotation=20)
    axes[1].bar(models, cost); axes[1].set_title("Cost (USD)"); axes[1].tick_params(axis="x", rotation=20)
    axes[2].bar(models, lat); axes[2].set_title("Median latency (s)"); axes[2].tick_params(axis="x", rotation=20)
    fig.suptitle("Model comparison")
    fig.tight_layout()
    return fig


def latex_figure_block(png_relative_path: str, caption: str, label: str) -> str:
    return (
        "\\begin{figure}[H]\n"
        "  \\centering\n"
        f"  \\includegraphics[width=0.85\\linewidth]{{{png_relative_path}}}\n"
        f"  \\caption{{{caption}}}\n"
        f"  \\label{{{label}}}\n"
        "\\end{figure}\n"
    )
```

- [ ] **Step 3: Commit**

```bash
git add testing/benchmark/lib/chart_style.py testing/benchmark/lib/charts.py
git commit -m "feat(benchmark): add chart styling + 5 implemented chart functions"
```

---

## Phase 2: Streamlit pages

### Task 12: App entrypoint (`benchmark/app.py`)

Streamlit's "Home" page — exists primarily so `streamlit run` has a target and so the multi-page navigation lights up.

**Files:**
- Create: `testing/benchmark/app.py`

- [ ] **Step 1: Implement `benchmark/app.py`**

```python
"""Benchmark harness — Streamlit entrypoint.

Run: streamlit run testing/benchmark/app.py
"""

import os
from pathlib import Path

import streamlit as st

# Make benchmark/lib and ../backend importable
_HERE = Path(__file__).resolve().parent
import sys
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

# Load .env.benchmark if present
_env = _HERE.parent / ".env.benchmark"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


from benchmark.lib import paths


st.set_page_config(page_title="arXiv Benchmark Harness", layout="wide")

st.title("arXiv Filtering — Benchmark Harness")

st.markdown(
    """
This is the Phase 1 evaluation tool for the agent-based arXiv filtering thesis.

**Workflow:**
1. **Pull Candidates** — paste a goal, distill, freeze criteria, pull RRF/BM25/SPECTER2 top-30.
2. **Label** — one paper at a time; check criteria boxes; saved incrementally.
3. **Run Experiment** — pick a model + toggles, run the cascade, results saved.
4. **Charts** — render figures for thesis, export PNG + LaTeX block.

Data files live under `testing/data/`. Frozen goal files and the cache manifest
are committed; labels, results, and the LLM cache are gitignored.
"""
)

paths.ensure_subdirs()

with st.expander("Environment & DB check"):
    db_url = os.environ.get("BENCHMARK_DB_URL")
    if not db_url:
        st.error("BENCHMARK_DB_URL is not set. Copy testing/.env.benchmark.example to testing/.env.benchmark.")
    else:
        st.success("BENCHMARK_DB_URL is configured.")

    if not os.environ.get("OPENAI_API_KEY"):
        st.warning("OPENAI_API_KEY not set — gpt-4o-mini and gpt-5.4-nano runs will fail.")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.warning("ANTHROPIC_API_KEY not set — claude-haiku-4-5 runs will fail.")

    st.write(f"Data root: `{paths.data_root()}`")

st.info("Pick a page from the left sidebar to begin.")
```

- [ ] **Step 2: Smoke-run the app**

```bash
cd testing && streamlit run benchmark/app.py
```

Open the URL Streamlit prints. You should see the title page with the sidebar showing 4 (greyed-out, since pages don't exist yet) entries. Stop with Ctrl+C.

- [ ] **Step 3: Commit**

```bash
git add testing/benchmark/app.py
git commit -m "feat(benchmark): add streamlit app entrypoint with env checks"
```

---

### Task 13: Page 1 — Pull Candidates (`pages/1_Pull_Candidates.py`)

Goal entry → distill → freeze → pull all three retrievers. UI for editing criteria before freezing.

**Files:**
- Create: `testing/benchmark/pages/1_Pull_Candidates.py`

- [ ] **Step 1: Implement `pages/1_Pull_Candidates.py`**

```python
"""Page 1 — Pull Candidates: distill goal, freeze criteria, pull retrievers."""

import asyncio
import sys
from pathlib import Path

import streamlit as st

# Make benchmark/lib importable
_BENCH = Path(__file__).resolve().parents[1]
if str(_BENCH.parent) not in sys.path:
    sys.path.insert(0, str(_BENCH.parent))

from benchmark.lib import distill, paths, pull
from benchmark.lib.schemas import Criterion


st.title("1 — Pull Candidates")

with st.form("goal_form"):
    goal_id = st.text_input("goal_id (slug, e.g. security_v1)")
    raw_goal = st.text_area("Raw filtering goal", height=160)
    top_k = st.number_input("Top K", min_value=5, max_value=100, value=30, step=5)
    distill_clicked = st.form_submit_button("Distill & Preview")

if distill_clicked:
    if not goal_id or not raw_goal:
        st.error("goal_id and raw_goal are required.")
    elif paths.goal_path(goal_id).exists():
        st.error(f"{goal_id}.json already exists — frozen goals are immutable. Use a new goal_id.")
    else:
        with st.spinner("Distilling..."):
            criteria, lexical_query = distill.distill(raw_goal=raw_goal)
        st.session_state.draft_criteria = [c.model_dump() for c in criteria]
        st.session_state.draft_lexical = lexical_query
        st.session_state.draft_goal_id = goal_id
        st.session_state.draft_raw_goal = raw_goal
        st.session_state.draft_top_k = int(top_k)

if "draft_criteria" in st.session_state:
    st.subheader("Distilled criteria — edit if needed")
    edited = []
    for c in st.session_state.draft_criteria:
        new_text = st.text_input(f"Criterion {c['id']}", value=c["text"], key=f"crit_{c['id']}")
        edited.append({"id": c["id"], "text": new_text})
    new_lex = st.text_input("Lexical query (BM25)", value=st.session_state.draft_lexical, key="lex_q")

    col_a, col_b = st.columns([1, 3])
    with col_a:
        if st.button("Re-distill"):
            with st.spinner("Re-distilling..."):
                criteria, lexical_query = distill.distill(raw_goal=st.session_state.draft_raw_goal)
            st.session_state.draft_criteria = [c.model_dump() for c in criteria]
            st.session_state.draft_lexical = lexical_query
            st.rerun()
    with col_b:
        if st.button("Freeze & Pull all three retrievers"):
            criteria_objs = [Criterion(**c) for c in edited]
            with st.spinner("Freezing goal..."):
                gf = distill.freeze(
                    goal_id=st.session_state.draft_goal_id,
                    raw_goal=st.session_state.draft_raw_goal,
                    criteria=criteria_objs,
                    lexical_query=new_lex,
                )
                st.success(f"Frozen: {paths.goal_path(gf.goal_id)}")

            with st.spinner("Computing SPECTER2 embedding..."):
                emb = asyncio.run(pull.embed_goal(st.session_state.draft_raw_goal, gf.goal_id))
                st.success(f"Embedding: {len(emb)} dims")

            for retriever in ("rrf", "bm25", "specter2"):
                with st.spinner(f"Pulling {retriever}..."):
                    cf = asyncio.run(pull.pull_and_save(
                        goal_id=gf.goal_id, retriever=retriever,
                        lexical_query=new_lex, goal_embedding=emb,
                        k=st.session_state.draft_top_k,
                    ))
                    st.success(f"{retriever}: {len(cf.papers)} papers → {paths.candidates_path(gf.goal_id, retriever)}")

            for k in ("draft_criteria", "draft_lexical", "draft_goal_id",
                      "draft_raw_goal", "draft_top_k"):
                st.session_state.pop(k, None)
            st.balloons()
```

- [ ] **Step 2: Commit**

```bash
git add testing/benchmark/pages/1_Pull_Candidates.py
git commit -m "feat(benchmark): add Page 1 — distill goal, freeze, pull retrievers"
```

---

### Task 14: Page 2 — Label (`pages/2_Label.py`)

One paper at a time. Resumable. Borderline + notes. Soft break prompt every 20.

**Files:**
- Create: `testing/benchmark/pages/2_Label.py`

- [ ] **Step 1: Implement `pages/2_Label.py`**

```python
"""Page 2 — Label: paper-at-a-time UI with frozen criteria checkboxes."""

import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

_BENCH = Path(__file__).resolve().parents[1]
if str(_BENCH.parent) not in sys.path:
    sys.path.insert(0, str(_BENCH.parent))

from benchmark.lib import paths
from benchmark.lib.schemas import GoalFile, CandidatesFile, LabelsFile, PaperLabel


st.title("2 — Label")


def list_goal_ids() -> list[str]:
    p = paths.data_root() / "goals"
    if not p.exists():
        return []
    return sorted([f.stem for f in p.glob("*.json")])


def load_labels(goal_id: str) -> LabelsFile:
    lp = paths.labels_path(goal_id)
    if lp.exists():
        return LabelsFile.model_validate_json(lp.read_text(encoding="utf-8"))
    return LabelsFile(goal_id=goal_id, labeler="user", labels={})


def save_labels(lf: LabelsFile) -> None:
    paths.ensure_subdirs()
    paths.labels_path(lf.goal_id).write_text(lf.model_dump_json(indent=2), encoding="utf-8")


goal_ids = list_goal_ids()
if not goal_ids:
    st.info("No frozen goals yet. Go to Page 1 to create one.")
    st.stop()

goal_id = st.selectbox("Goal", goal_ids)
gf = GoalFile.model_validate_json(paths.goal_path(goal_id).read_text(encoding="utf-8"))
cp_path = paths.candidates_path(goal_id, "rrf")
if not cp_path.exists():
    st.error(f"Missing {cp_path}. Pull RRF candidates on Page 1.")
    st.stop()
cf = CandidatesFile.model_validate_json(cp_path.read_text(encoding="utf-8"))
lf = load_labels(goal_id)

# Session timer
st.session_state.setdefault(f"session_start_{goal_id}", time.time())
elapsed = int(time.time() - st.session_state[f"session_start_{goal_id}"])
mm, ss = divmod(elapsed, 60)
st.caption(f"Session: {mm:02d}:{ss:02d}")

# Progress + borderline warning
total = len(cf.papers)
done = len(lf.labels)
borderline = sum(1 for v in lf.labels.values() if v.borderline)
st.progress(done / max(total, 1), text=f"{done}/{total} labeled")
if done > 0 and borderline / done > 0.30:
    st.warning(f"Borderline > 30% ({borderline}/{done}). Consider re-reading criteria or adding one to disambiguate.")
if done > 0 and done % 20 == 0:
    st.info(f"You've labeled {done}. Consider a short break before continuing — labeling fatigue introduces noise.")

# Pick next unlabeled paper, or allow override
unlabeled = [p for p in cf.papers if p.paper_id not in lf.labels]
if not unlabeled:
    st.success("All papers labeled!")
    summary = lf.summary()
    st.write(summary.model_dump())
    st.stop()

idx = st.number_input("Paper index", 0, len(unlabeled) - 1, 0)
paper = unlabeled[idx]

st.subheader(paper.title)
st.caption(", ".join(paper.authors[:5]) + ("..." if len(paper.authors) > 5 else ""))
st.write(paper.abstract)
if paper.pdf_url:
    st.markdown(f"[Open PDF]({paper.pdf_url})")
st.markdown(f"[Open on arXiv](https://arxiv.org/abs/{paper.paper_id})")

st.divider()
st.markdown("**Tick which criteria this paper satisfies:**")
satisfied: list[str] = []
for c in gf.distilled_criteria:
    if st.checkbox(c.text, key=f"crit_{paper.paper_id}_{c.id}"):
        satisfied.append(c.id)

borderline_flag = st.checkbox("Borderline — exclude from precision", key=f"bord_{paper.paper_id}")
notes = st.text_area("Notes (optional)", key=f"notes_{paper.paper_id}")

if st.button("Save & Next"):
    n_total = len(gf.distilled_criteria)
    threshold = gf.scoring_rule.threshold
    score = 1 if (len(satisfied) >= threshold and not borderline_flag) else 0
    lf.labels[paper.paper_id] = PaperLabel(
        criteria_satisfied=satisfied,
        ground_truth_score=score,
        borderline=borderline_flag,
        notes=notes or None,
        labeled_at=datetime.now(timezone.utc),
    )
    save_labels(lf)
    st.rerun()
```

- [ ] **Step 2: Commit**

```bash
git add testing/benchmark/pages/2_Label.py
git commit -m "feat(benchmark): add Page 2 — labeling UI with criteria checkboxes"
```

---

### Task 15: Page 3 — Run Experiment (`pages/3_Run_Experiment.py`)

Toggle config + preset buttons. Cost preview. Run executes the cascade and writes result JSON.

**Files:**
- Create: `testing/benchmark/pages/3_Run_Experiment.py`

- [ ] **Step 1: Implement `pages/3_Run_Experiment.py`**

```python
"""Page 3 — Run Experiment: configure cascade toggles, run, save result."""

import os
import sys
from pathlib import Path

import streamlit as st

_BENCH = Path(__file__).resolve().parents[1]
if str(_BENCH.parent) not in sys.path:
    sys.path.insert(0, str(_BENCH.parent))

from benchmark.lib import paths, runner, pricing
from benchmark.lib.schemas import GoalFile, CandidatesFile, LabelsFile, RunConfig

st.title("3 — Run Experiment")


def list_goal_ids() -> list[str]:
    p = paths.data_root() / "goals"
    return sorted([f.stem for f in p.glob("*.json")]) if p.exists() else []


goal_ids = list_goal_ids()
if not goal_ids:
    st.info("No frozen goals yet.")
    st.stop()

goal_id = st.selectbox("Goal", goal_ids)
gf = GoalFile.model_validate_json(paths.goal_path(goal_id).read_text(encoding="utf-8"))
labels_p = paths.labels_path(goal_id)
if not labels_p.exists():
    st.error(f"No labels for {goal_id}. Label some papers on Page 2 first.")
    st.stop()
lf = LabelsFile.model_validate_json(labels_p.read_text(encoding="utf-8"))
cf = CandidatesFile.model_validate_json(paths.candidates_path(goal_id, "rrf").read_text(encoding="utf-8"))

st.caption(f"{len(lf.labels)} labeled / {len(cf.papers)} candidates")

st.subheader("Preset experiments")
cols = st.columns(5)
preset = None
if cols[0].button("Exp 1 — Model selection"): preset = "exp1"
if cols[1].button("Exp 2 — Critique ablation"): preset = "exp2"
if cols[2].button("Exp 3 — Memory effect"): preset = "exp3"
if cols[3].button("Exp 4 — K curve"): preset = "exp4"
if cols[4].button("Exp 5 — Deep Reader"): preset = "exp5"

st.subheader("Toggle config")

model_choices = ["gpt-4o-mini", "claude-haiku-4-5-20251001", "gpt-5.4-nano-2026-03-17"]
default_model = "gpt-4o-mini"
critique_default = True
deep_reader_default = True
memory_default = "empty"
k_default = 10

if preset == "exp1":
    st.info("Exp 1 — run once per model, comparing precision/cost/latency. Pick a model below and click Run, then repeat for the other two.")
elif preset == "exp2":
    st.info("Exp 2 — run with Critique=ON, then again with Critique=OFF.")
    critique_default = True
elif preset == "exp3":
    st.info("Exp 3 — run with memory='empty', then again with memory='seeded'.")
elif preset == "exp4":
    st.info("Exp 4 — run for K ∈ {5, 10, 15, 30}.")
elif preset == "exp5":
    st.info("Exp 5 — run with Deep Reader=ON, then again with Deep Reader=OFF.")

model = st.selectbox("Model", model_choices, index=model_choices.index(default_model))
critique = st.checkbox("Critique enabled", value=critique_default)
deep_reader = st.checkbox("Deep Reader enabled", value=deep_reader_default)
memory = st.selectbox("Feedback memory", ["empty", "seeded"], index=0 if memory_default == "empty" else 1)
k = st.selectbox("deep_scan_limit K", [5, 10, 15, 30], index=[5,10,15,30].index(k_default))

config = RunConfig(model=model, evaluator=True, critique=critique,
                   deep_reader=deep_reader, feedback_memory=memory, deep_scan_limit=k)

# Cost preview — count cache misses with a dry pass
st.subheader("Cost preview")
n_papers = len(lf.labels)
# Rough: ~400 in / ~50 out for evaluator, ~600/40 critique, ~5000/200 deep_reader
est_in = n_papers * 400
est_out = n_papers * 50
if critique:
    est_in += int(n_papers * 0.2 * 600)
    est_out += int(n_papers * 0.2 * 40)
if deep_reader:
    n_dr = min(k, n_papers)
    est_in += n_dr * 5000
    est_out += n_dr * 200
est_cost = pricing.compute_cost_usd(model, est_in, est_out)
cap = float(os.environ.get("BENCHMARK_COST_CAP_USD", "5.00"))
st.write(f"Estimated worst-case cost (assuming 100% cache miss): **${est_cost:.3f}**")
st.write(f"Hard cap: ${cap:.2f}")

over_cap = est_cost > cap
override = False
if over_cap:
    override = st.checkbox(f"I acknowledge cost may exceed ${cap:.2f} and want to proceed anyway")

run_disabled = over_cap and not override
if st.button("Run", disabled=run_disabled):
    with st.spinner("Running cascade — first run may take several minutes (subsequent are cached)..."):
        criteria_text = [c.text for c in gf.distilled_criteria]
        result = runner.run(goal_id=goal_id, config=config, candidates=cf,
                            labels=lf, criteria=criteria_text)
        out_path = runner.save_result(result)
    st.success(f"Saved {out_path}")
    st.json(result.metrics.model_dump())
```

- [ ] **Step 2: Commit**

```bash
git add testing/benchmark/pages/3_Run_Experiment.py
git commit -m "feat(benchmark): add Page 3 — toggle UI, cost preview, run cascade"
```

---

### Task 16: Page 4 — Charts (`pages/4_Charts.py`)

Multi-select runs, render charts, export PNG, copy LaTeX block.

**Files:**
- Create: `testing/benchmark/pages/4_Charts.py`

- [ ] **Step 1: Implement `pages/4_Charts.py`**

```python
"""Page 4 — Charts: render thesis-ready figures, export PNG + LaTeX."""

import io
import sys
from pathlib import Path

import streamlit as st

_BENCH = Path(__file__).resolve().parents[1]
if str(_BENCH.parent) not in sys.path:
    sys.path.insert(0, str(_BENCH.parent))

from benchmark.lib import charts, paths
from benchmark.lib.schemas import ResultsFile

st.title("4 — Charts")


def list_results() -> list[ResultsFile]:
    rdir = paths.data_root() / "results"
    if not rdir.exists():
        return []
    out = []
    for f in sorted(rdir.glob("*.json")):
        try:
            out.append(ResultsFile.model_validate_json(f.read_text(encoding="utf-8")))
        except Exception as e:
            st.warning(f"Skipped {f.name}: {e}")
    return out


def fig_to_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    buf.seek(0)
    return buf.read()


def export_block(chart_id: str, fig, default_caption: str) -> None:
    cap = st.text_input(f"Caption for {chart_id}", value=default_caption, key=f"cap_{chart_id}")
    label = st.text_input(f"Label for {chart_id}", value=f"fig:{chart_id}", key=f"lbl_{chart_id}")
    png_bytes = fig_to_bytes(fig)
    rel_path = f"figures/{chart_id}.png"
    st.download_button("Export PNG (300dpi)", data=png_bytes, file_name=f"{chart_id}.png", mime="image/png", key=f"dl_{chart_id}")
    latex = charts.latex_figure_block(rel_path, cap, label)
    st.code(latex, language="latex")


all_results = list_results()
if not all_results:
    st.info("No results yet. Run an experiment on Page 3.")
    st.stop()

chart_choice = st.selectbox("Chart", [
    "Chart 1 — Precision by stage (one run)",
    "Chart 3 — Precision × Cost scatter (multi-run)",
    "Chart 5 — Deep Reader ablation (2 runs)",
    "Chart 8 — Cross-goal (multi-goal, same config)",
    "Chart 10 — Model comparison (3 runs)",
])

run_labels = [f"{r.run_id}" for r in all_results]

if chart_choice.startswith("Chart 1"):
    pick = st.selectbox("Run", run_labels)
    r = all_results[run_labels.index(pick)]
    fig = charts.chart1_precision_by_stage(r)
    st.pyplot(fig)
    export_block("chart1_precision_by_stage", fig,
                 f"Precision by stage for {r.goal_id} using {r.config.model}.")

elif chart_choice.startswith("Chart 3"):
    picks = st.multiselect("Runs", run_labels, default=run_labels[:4])
    rs = [all_results[run_labels.index(p)] for p in picks]
    if rs:
        fig = charts.chart3_precision_cost_scatter(rs)
        st.pyplot(fig)
        export_block("chart3_precision_cost", fig, "Precision–cost frontier across K values.")

elif chart_choice.startswith("Chart 5"):
    off_pick = st.selectbox("Deep Reader OFF run", run_labels, key="dr_off")
    on_pick = st.selectbox("Deep Reader ON run", run_labels, key="dr_on")
    off = all_results[run_labels.index(off_pick)]
    on = all_results[run_labels.index(on_pick)]
    fig = charts.chart5_deep_reader_ablation(off, on)
    st.pyplot(fig)
    export_block("chart5_deep_reader_ablation", fig,
                 f"Deep Reader ablation on {off.goal_id}.")

elif chart_choice.startswith("Chart 8"):
    picks = st.multiselect("One run per goal", run_labels)
    rs = [all_results[run_labels.index(p)] for p in picks]
    by_goal = {r.goal_id: r for r in rs}
    if len(by_goal) >= 2:
        fig = charts.chart8_cross_goal(by_goal)
        st.pyplot(fig)
        export_block("chart8_cross_goal", fig,
                     "Cross-goal precision comparison.")
    else:
        st.info("Pick at least one run per goal.")

elif chart_choice.startswith("Chart 10"):
    picks = st.multiselect("Three runs (same goal, different models)", run_labels)
    rs = [all_results[run_labels.index(p)] for p in picks]
    by_model = {r.config.model: r for r in rs}
    if len(by_model) >= 2:
        fig = charts.chart10_model_comparison(by_model)
        st.pyplot(fig)
        export_block("chart10_model_comparison", fig,
                     f"Model comparison on {rs[0].goal_id}.")
    else:
        st.info("Pick at least 2 different-model runs.")
```

- [ ] **Step 2: Commit**

```bash
git add testing/benchmark/pages/4_Charts.py
git commit -m "feat(benchmark): add Page 4 — chart selector with PNG + LaTeX export"
```

---

## Phase 3: Cutover

### Task 17: Run the cutover gate manually

This is a manual verification step the engineer performs in the browser.

- [ ] **Step 1: Start the app**

```bash
cd testing && streamlit run benchmark/app.py
```

- [ ] **Step 2: Verify Page 1 end-to-end (gate check 1)**

Use goal_id `security_v1` and the goal text from spec §3 option E2. Click Distill & Preview → Freeze & Pull. Verify all three files were written:

```bash
ls testing/data/goals/security_v1.json
ls testing/data/candidates/security_v1__rrf.json
ls testing/data/candidates/security_v1__bm25.json
ls testing/data/candidates/security_v1__specter2.json
```

All four should exist. Each candidates file should contain 30 papers.

- [ ] **Step 3: Verify Page 2 end-to-end (gate check 2)**

Open Page 2, select `security_v1`, label 3 papers (any way: tick boxes, click Save & Next). Verify:

```bash
cat testing/data/labels/security_v1.json | python -c "import json,sys; d=json.load(sys.stdin); print(len(d['labels']))"
```
Expected: `3`.

Stop and restart Streamlit. Reopen Page 2 — the 3 labels are still there, the unlabeled paper count is now 27.

- [ ] **Step 4: Verify Page 3 end-to-end (gate check 3)**

Set model = `gpt-4o-mini`, all toggles default. Click Run. Verify a result file appears:

```bash
ls testing/data/results/security_v1__*.json
```

Open Page 4, pick Chart 1, select that result. Confirm a chart renders. Click Export PNG — verify download.

- [ ] **Step 5: Document findings**

If any gate check failed, fix the bug, restart, and re-verify before proceeding to Task 18. If all three passed, the gate is satisfied and we can do the cutover.

---

### Task 18: Cutover commit

Single commit deletes the old benchmark files and updates the docs.

**Files:**
- Delete: `testing/benchmark/benchmark_pipeline.py`
- Delete: `testing/benchmark/experiments.py`
- Modify: `testing/EVALUATION_BENCHMARK_SPECIFICATION.md`
- Modify: `testing/CLAUDE.md`

- [ ] **Step 1: Delete old files**

```bash
git rm testing/benchmark/benchmark_pipeline.py testing/benchmark/experiments.py
```

- [ ] **Step 2: Replace `EVALUATION_BENCHMARK_SPECIFICATION.md`**

Open `testing/EVALUATION_BENCHMARK_SPECIFICATION.md`, replace the entire contents with:

```markdown
# Thesis Evaluation & Benchmarking Specification

This document is superseded by [`docs/superpowers/specs/2026-04-13-benchmark-harness-design.md`](../docs/superpowers/specs/2026-04-13-benchmark-harness-design.md).

## How to run

```bash
cd testing
cp .env.benchmark.example .env.benchmark
# fill in BENCHMARK_DB_URL, OPENAI_API_KEY, ANTHROPIC_API_KEY
streamlit run benchmark/app.py
```

Walk through pages 1 → 2 → 3 → 4 to pull candidates, label, run experiments, and export charts.

## Phase 1 experiments (active)
1. Model selection (gpt-4o-mini / claude-haiku-4-5 / gpt-5.4-nano)
2. Critique ablation
3. Longitudinal feedback
4. Cost–value K curve
5. Deep Reader value

## Phase 2 (deferred)
6. Pre-filter retrieval recall — requires union-of-retrievers labeled dataset
```

- [ ] **Step 3: Update `testing/CLAUDE.md`**

Open `testing/CLAUDE.md`. Find the section starting with "## Benchmark Pipeline (from EVALUATION_BENCHMARK_SPECIFICATION.md)" and replace from there to the end of that section with:

```markdown
## Benchmark Harness — see docs/superpowers/specs/2026-04-13-benchmark-harness-design.md

Multi-page Streamlit app at `testing/benchmark/app.py`:

- **Page 1 Pull Candidates** — distill goal, freeze criteria, pull RRF/BM25/SPECTER2 top-30
- **Page 2 Label** — paper-at-a-time hand labeling
- **Page 3 Run Experiment** — toggle cascade config, cached real LLM, save metrics
- **Page 4 Charts** — render thesis figures with PNG + LaTeX export

Pure logic lives in `testing/benchmark/lib/`. Run unit tests with:
```bash
cd testing/benchmark && pytest tests/ -v
```

Data files in `testing/data/`. Goal files and `cache_manifest.json` are committed; labels, results, and llm_cache are gitignored.
```

- [ ] **Step 4: Commit**

```bash
git add testing/benchmark/benchmark_pipeline.py testing/benchmark/experiments.py testing/EVALUATION_BENCHMARK_SPECIFICATION.md testing/CLAUDE.md
git commit -m "feat(benchmark): cutover — delete old files, update docs"
```

---

## Self-review notes

**Coverage check (spec § → task):**
- §3.1 directory layout → Task 0
- §3.2 principles + §3.3 data flow → enforced via Tasks 1–10
- §4.1 goal freezing → Task 7 + Task 13
- §4.2 retrievers (3 of them) → Task 8 + Task 13
- §4.3 labeling protocol → Task 14
- §5.1 toggles + §5.2 presets → Task 15
- §5.3 run execution + cache → Tasks 4, 5, 6, 10
- §5.4 metrics (precision, Wilson, pass-through, agreement, cost) → Task 9 + Task 10
- §6 schemas → Task 2
- §7 charts (5 implemented + LaTeX export) → Tasks 11, 16
- §8 cutover → Tasks 17, 18
- §9 risk mitigations: R3 prompt versions in Task 5; R4 smoke test in Task 8 + Task 12; R5 timer + break prompt in Task 14; R6 cost cap in Task 15; R7 borderline warning in Task 14

**Out-of-scope reminder:** Charts 2, 4, 6, 7, 9 are NOT implemented — they are stubs the user can add when their thesis writing requires them. Same for the Phase 2 pre-filter recall experiment (Exp 6).

**Known caveats:**
- The `_fetch_markdown` helper in Task 10 uses a sync-wrapper around an async DB call. Streamlit's event loop has known quirks; if it misbehaves, refactor that helper to use a single ad-hoc psycopg2 sync connection instead. Either approach satisfies the spec — what matters is that Marker is never called.
- The token-cost preview in Task 15 is a rough heuristic; the *actual* cost reported in metrics comes from real `usage_metadata`.
