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
