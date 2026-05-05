"""Pydantic schemas for every JSON file the harness reads or writes.

All file I/O round-trips through these models — never write or read raw dicts.
"""

import hashlib
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
