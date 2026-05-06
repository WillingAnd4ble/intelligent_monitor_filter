"""Path helpers — every data-file path in the harness goes through here."""

import os
from pathlib import Path


def data_root() -> Path:
    """Root of the data/ directory. Honors BENCHMARK_DATA_DIR env var (used by tests)."""
    env = os.environ.get("BENCHMARK_DATA_DIR")
    if env:
        return Path(env)
    # Assumes this file lives at testing/benchmark/lib/paths.py;
    # parents[3] climbs to the repo root.
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


def dataset_path(dataset_id: str) -> Path:
    return data_root() / "datasets" / f"{dataset_id}.json"


def markdown_path(paper_id: str) -> Path:
    safe = paper_id.replace("/", "_").replace(":", "_")
    return data_root() / "markdown" / f"{safe}.md"


def ensure_subdirs() -> None:
    """Create data/* subdirs if missing. Safe to call repeatedly."""
    root = data_root()
    for sub in ("goals", "candidates", "labels", "results", "llm_cache",
                "datasets", "markdown"):
        (root / sub).mkdir(parents=True, exist_ok=True)
