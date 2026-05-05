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
