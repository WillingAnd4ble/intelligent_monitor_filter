"""GoalDistiller wrapper: distill, freeze, persist."""

import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

# Allow importing from ../backend
_BACKEND = Path(__file__).resolve().parents[3] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.agents.distiller import run_goal_distiller  # type: ignore

from benchmark.lib import paths
from benchmark.lib.schemas import Criterion, GoalFile, ScoringRule


def distill(raw_goal: str, categories: List[str] | None = None,
            topics: List[str] | None = None,
            content_interest: List[str] | None = None) -> Tuple[List[Criterion], str]:
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
