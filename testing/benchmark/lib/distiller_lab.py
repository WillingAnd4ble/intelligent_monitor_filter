"""Distiller Lab: run any model + any prompt over a goal, save the comparison.

Used by Page 5 to test which LLM distills goals best and to iterate on prompt
wording without touching backend/app/agents/distiller.py.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from benchmark.lib import paths, pricing
from benchmark.lib.llm import call_structured

# Mirror the backend's output schema locally so we don't depend on a
# specific symbol surviving in distiller.py through future refactors.
class DistilledCriteriaOutput(BaseModel):
    distilled_criteria: List[str] = Field(
        description="Strict list of exact context inclusion thresholds tracking user parameters."
    )
    lexical_query: str = Field(
        description="Short keyword query (3-8 key terms) optimized for BM25 full-text search."
    )


class ModelResult(BaseModel):
    model: str
    distilled_criteria: List[str]
    lexical_query: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost_usd: float
    error: Optional[str] = None


class DistillerExperiment(BaseModel):
    experiment_id: str
    created_at: datetime
    raw_goal: str
    categories: List[str] = []
    topics: List[str] = []
    content_interest: List[str] = []
    system_prompt: str
    human_prompt: str
    results: Dict[str, ModelResult]  # keyed by model name


def run_one(model: str, system_prompt: str, human_prompt: str, raw_goal: str,
            categories: List[str] | None = None,
            topics: List[str] | None = None,
            content_interest: List[str] | None = None) -> ModelResult:
    """Distill once with a specific model + prompt pair. Returns ModelResult.

    Errors are caught and reported in `error`; the result is still returned so
    the UI can show partial success across a multi-model run.
    """
    try:
        parsed, tin, tout, lat = call_structured(
            model=model,
            output_schema=DistilledCriteriaOutput,
            system_template=system_prompt,
            human_template=human_prompt,
            template_vars={
                "categories": categories or [],
                "topics": topics or [],
                "interests": content_interest or [],
                "goal": raw_goal,
            },
            temperature=0.0,
        )
        cost = pricing.compute_cost_usd(model, tin, tout)
        return ModelResult(
            model=model,
            distilled_criteria=list(parsed.distilled_criteria),
            lexical_query=parsed.lexical_query,
            tokens_in=tin, tokens_out=tout, latency_ms=lat, cost_usd=cost,
        )
    except Exception as e:
        return ModelResult(
            model=model,
            distilled_criteria=[], lexical_query="",
            tokens_in=0, tokens_out=0, latency_ms=0.0, cost_usd=0.0,
            error=f"{type(e).__name__}: {e}",
        )


def save_experiment(exp: DistillerExperiment) -> Path:
    paths.ensure_subdirs()
    root = paths.data_root() / "distiller_experiments"
    root.mkdir(parents=True, exist_ok=True)
    p = root / f"{exp.experiment_id}.json"
    p.write_text(exp.model_dump_json(indent=2), encoding="utf-8")
    return p


def list_experiments() -> List[str]:
    root = paths.data_root() / "distiller_experiments"
    if not root.exists():
        return []
    return sorted(f.stem for f in root.glob("*.json"))


def load_experiment(experiment_id: str) -> DistillerExperiment:
    root = paths.data_root() / "distiller_experiments"
    return DistillerExperiment.model_validate_json(
        (root / f"{experiment_id}.json").read_text(encoding="utf-8")
    )
