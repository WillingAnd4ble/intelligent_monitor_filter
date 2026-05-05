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
