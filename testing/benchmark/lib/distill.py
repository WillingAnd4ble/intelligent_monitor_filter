"""GoalDistiller wrapper: distill (any model), freeze, persist.

Distillation routes through the harness's lib/llm.py + lib/prompts.py so any
supported model (direct OpenAI/Anthropic or any OpenRouter id) can be used
to produce the criteria. The backend's hardcoded gpt-4o-mini distiller is
left untouched for the prod pipeline.
"""

import math
from datetime import datetime, timezone
from typing import List, Tuple

from benchmark.lib import distiller_lab, paths, prompts
from benchmark.lib.schemas import Criterion, GoalFile, ScoringRule


def distill(raw_goal: str, model: str = "gpt-4o-mini",
            categories: List[str] | None = None,
            topics: List[str] | None = None,
            content_interest: List[str] | None = None) -> Tuple[List[Criterion], str]:
    """Run the GoalDistiller via any chosen model. Returns (criteria, lexical_query)."""
    result = distiller_lab.run_one(
        model=model,
        system_prompt=prompts.DISTILLER_SYSTEM,
        human_prompt=prompts.DISTILLER_HUMAN,
        raw_goal=raw_goal,
        categories=categories or [],
        topics=topics or [],
        content_interest=content_interest or [],
    )
    if result.error:
        raise RuntimeError(f"Distillation failed: {result.error}")
    criteria = [Criterion(id=f"c{i+1}", text=t)
                for i, t in enumerate(result.distilled_criteria)]
    return criteria, result.lexical_query


def freeze(goal_id: str, raw_goal: str, criteria: List[Criterion],
           lexical_query: str, distiller_model: str = "gpt-4o-mini",
           dataset_id: str | None = None) -> GoalFile:
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
        dataset_id=dataset_id,
    )
    paths.ensure_subdirs()
    path.write_text(g.model_dump_json(indent=2), encoding="utf-8")
    return g


def load(goal_id: str) -> GoalFile:
    path = paths.goal_path(goal_id)
    return GoalFile.model_validate_json(path.read_text(encoding="utf-8"))
