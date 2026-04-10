"""
Experiment runner for the benchmarking suite.

Each experiment loads papers from evaluation_dataset.json,
runs them through real or partially-mocked pipeline stages,
and returns structured metrics.  Can be called from Streamlit
or from the command line.

IMPORTANT: These experiments call REAL LLM APIs (OpenAI) to measure
actual agent performance.  PDF extraction is skipped — text is
pre-extracted in the dataset JSON.
"""

import json
import time
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PaperRecord:
    paper_id: str
    title: str
    abstract: str
    full_text: str  # pre-extracted, no PDF needed
    ground_truth: int  # 1 = relevant, 0 = not relevant
    tags: list[str] = field(default_factory=list)  # e.g. ["borderline", "hard_trap"]


@dataclass
class StageResult:
    paper_id: str
    decision: Optional[str] = None  # accept / borderline / reject
    score: Optional[float] = None
    explanation: Optional[str] = None
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ExperimentMetrics:
    name: str
    precision: float
    recall: float
    f1: float
    total_papers: int
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    avg_latency_ms: float = 0.0
    total_cost_usd: float = 0.0
    per_paper_results: list[StageResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Dataset loader
# ---------------------------------------------------------------------------

def load_dataset(path: str | Path = None) -> list[PaperRecord]:
    """Load the evaluation dataset JSON.  Falls back to the template if the
    full dataset doesn't exist yet."""
    if path is None:
        base = Path(__file__).parent.parent
        path = base / "evaluation_dataset.json"
        if not path.exists():
            path = base / "evaluation_dataset_template.json"

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    return [
        PaperRecord(
            paper_id=p["paper_id"],
            title=p["title"],
            abstract=p["abstract"],
            full_text=p.get("full_text", p["abstract"]),
            ground_truth=p["ground_truth"],
            tags=p.get("tags", []),
        )
        for p in raw["papers"]
    ]


# ---------------------------------------------------------------------------
# Cost estimation  (GPT-4o-mini pricing as of 2025)
# ---------------------------------------------------------------------------

# GPT-4o-mini: $0.15 / 1M input tokens, $0.60 / 1M output tokens
INPUT_COST_PER_TOKEN = 0.15 / 1_000_000
OUTPUT_COST_PER_TOKEN = 0.60 / 1_000_000


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return input_tokens * INPUT_COST_PER_TOKEN + output_tokens * OUTPUT_COST_PER_TOKEN


def _calc_metrics(
    name: str,
    papers: list[PaperRecord],
    predictions: list[int],
    results: list[StageResult],
) -> ExperimentMetrics:
    """Calculate precision, recall, F1 from ground truth vs predictions."""
    tp = fp = fn = tn = 0
    for paper, pred in zip(papers, predictions):
        gt = paper.ground_truth
        if gt == 1 and pred == 1:
            tp += 1
        elif gt == 0 and pred == 1:
            fp += 1
        elif gt == 1 and pred == 0:
            fn += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    total_latency = sum(r.latency_ms for r in results)
    total_cost = sum(estimate_cost(r.input_tokens, r.output_tokens) for r in results)
    avg_latency = total_latency / len(results) if results else 0.0

    return ExperimentMetrics(
        name=name,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        total_papers=len(papers),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        avg_latency_ms=round(avg_latency, 1),
        total_cost_usd=round(total_cost, 6),
        per_paper_results=results,
    )


# ===================================================================
# EXPERIMENT 1: Pre-Filter Retrieval Efficacy
# ===================================================================

def run_experiment_1_retrieval(
    papers: list[PaperRecord],
    criteria: list[str],
    top_k: int = 10,
) -> dict[str, ExperimentMetrics]:
    """
    Compare retrieval methods: BM25-only vs Semantic-only vs RRF hybrid.

    Since we can't run real PostgreSQL queries in the benchmark, we simulate
    the retrieval legs using Python:
      - BM25:     keyword overlap (TF-IDF via sklearn)
      - Semantic: cosine similarity of SPECTER2 embeddings (via OpenAI or sentence-transformers)
      - RRF:      fused ranking

    Returns metrics for each variant at cut-off top_k.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np

    query = " ".join(criteria)
    abstracts = [p.abstract for p in papers]
    ground_truths = [p.ground_truth for p in papers]

    # --- BM25 leg (TF-IDF as proxy) ---
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(abstracts + [query])
    query_vec = tfidf_matrix[-1]
    doc_vecs = tfidf_matrix[:-1]
    bm25_scores = cosine_similarity(query_vec, doc_vecs).flatten()
    bm25_ranking = np.argsort(-bm25_scores)

    # --- Semantic leg (sentence-transformers local, or OpenAI embeddings) ---
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        all_texts = abstracts + [query]
        embeddings = model.encode(all_texts)
        query_emb = embeddings[-1].reshape(1, -1)
        doc_embs = embeddings[:-1]
        semantic_scores = cosine_similarity(query_emb, doc_embs).flatten()
    except ImportError:
        logger.warning("sentence-transformers not installed, using TF-IDF for semantic leg too")
        semantic_scores = bm25_scores
    semantic_ranking = np.argsort(-semantic_scores)

    # --- RRF fusion ---
    rrf_k = 60
    rrf_scores = np.zeros(len(papers))
    for rank, idx in enumerate(bm25_ranking):
        rrf_scores[idx] += 1.0 / (rrf_k + rank + 1)
    for rank, idx in enumerate(semantic_ranking):
        rrf_scores[idx] += 1.0 / (rrf_k + rank + 1)
    rrf_ranking = np.argsort(-rrf_scores)

    # --- Evaluate each variant at top_k ---
    results = {}
    for variant_name, ranking in [("BM25", bm25_ranking), ("Semantic", semantic_ranking), ("RRF", rrf_ranking)]:
        preds = [0] * len(papers)
        for idx in ranking[:top_k]:
            preds[idx] = 1  # predicted as relevant

        stub_results = [StageResult(paper_id=p.paper_id) for p in papers]
        results[variant_name] = _calc_metrics(
            name=f"Exp1: {variant_name} @{top_k}",
            papers=papers,
            predictions=preds,
            results=stub_results,
        )

    return results


# ===================================================================
# EXPERIMENT 2: Multi-Agent Efficacy
# ===================================================================

def run_experiment_2_agent_efficacy(
    papers: list[PaperRecord],
    criteria: list[str],
    feedback_memory: str = "",
) -> dict[str, ExperimentMetrics]:
    """
    Compare: Evaluator-only  vs  Evaluator+Critique.

    Calls REAL LLM APIs.  Each paper's abstract is sent through the
    evaluator node, and optionally the critique node.
    """
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from app.agents.schemas import EvaluatorOutput, CritiqueOutput
    from app.core.config import settings

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0, api_key=settings.OPENAI_API_KEY)

    # -- Evaluator --
    eval_structured = llm.with_structured_output(EvaluatorOutput)
    eval_prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are an elite academic recommender AI. Evaluate incoming publications "
         "strictly against the user's specific inclusion/exclusion bounds:\n"
         "{criteria}\n\n"
         "If paper inherently serves the central goal, output 'accept'.\n"
         "If paper touches bounds broadly but isn't centrally focused, output 'borderline'.\n"
         "If paper violates exclusions or misses entirely, output 'reject'."),
        ("human", "Evaluate the following extracted text:\n\n{text}"),
    ])
    eval_chain = eval_prompt | eval_structured

    # -- Critique --
    crit_structured = llm.with_structured_output(CritiqueOutput)
    crit_prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are an alignment AI tasked with overriding a junior agent's recommendation.\n"
         "The junior agent was 'borderline' unsure about this paper for the following reason:\n"
         "{reasonbook}\n\n"
         "CRITICAL DIRECTIVE:\n"
         "The user historically absolutely DESPISES these elements: {memory}\n\n"
         "If the junior agent's reason or the paper's abstract heavily features what the user despises, "
         "you MUST output decision=False (Reject).\n"
         "If it circumvents the despised elements safely, output decision=True (Accept)."),
        ("human", "Evaluate against Memory. Abstract context:\n\n{text}"),
    ])
    crit_chain = crit_prompt | crit_structured

    criteria_str = "\n- ".join(criteria)

    # Variant A: Evaluator only
    eval_only_preds = []
    eval_only_results = []
    for paper in papers:
        t0 = time.time()
        result = eval_chain.invoke({"criteria": criteria_str, "text": paper.abstract})
        latency = (time.time() - t0) * 1000
        pred = 1 if result.decision in ("accept", "borderline") else 0
        eval_only_preds.append(pred)
        eval_only_results.append(StageResult(
            paper_id=paper.paper_id,
            decision=result.decision,
            latency_ms=latency,
            input_tokens=len(paper.abstract.split()) * 2,  # rough estimate
            output_tokens=50,
        ))

    # Variant B: Evaluator + Critique (for borderline papers)
    eval_crit_preds = []
    eval_crit_results = []
    for paper, eval_res in zip(papers, eval_only_results):
        if eval_res.decision == "reject":
            eval_crit_preds.append(0)
            eval_crit_results.append(eval_res)
        elif eval_res.decision == "accept":
            eval_crit_preds.append(1)
            eval_crit_results.append(eval_res)
        else:  # borderline → send to critique
            if not feedback_memory:
                eval_crit_preds.append(1)  # auto-pass
                eval_crit_results.append(eval_res)
            else:
                t0 = time.time()
                crit_result = crit_chain.invoke({
                    "reasonbook": eval_res.decision or "",
                    "memory": feedback_memory,
                    "text": paper.abstract,
                })
                latency = (time.time() - t0) * 1000
                pred = 1 if crit_result.decision else 0
                eval_crit_preds.append(pred)
                eval_crit_results.append(StageResult(
                    paper_id=paper.paper_id,
                    decision="critique_pass" if crit_result.decision else "critique_reject",
                    latency_ms=eval_res.latency_ms + latency,
                    input_tokens=eval_res.input_tokens + len(paper.abstract.split()) * 2,
                    output_tokens=eval_res.output_tokens + 50,
                ))

    return {
        "Evaluator Only": _calc_metrics("Exp2: Evaluator Only", papers, eval_only_preds, eval_only_results),
        "Evaluator + Critique": _calc_metrics("Exp2: Evaluator + Critique", papers, eval_crit_preds, eval_crit_results),
    }


# ===================================================================
# EXPERIMENT 3: Longitudinal Feedback Shift
# ===================================================================

def run_experiment_3_feedback_shift(
    papers: list[PaperRecord],
    criteria: list[str],
    simulated_rejections: list[str],
) -> dict[str, ExperimentMetrics]:
    """
    Run the pipeline twice:
      Run 1 — blank feedback_memory
      Run 2 — after feeding simulated rejection comments through the MemorySummarizer

    Measures how precision/recall shift as the system "learns".
    """
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from app.agents.schemas import MemoryOutput
    from app.core.config import settings

    # Build cumulative feedback memory from simulated rejections
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0, api_key=settings.OPENAI_API_KEY)
    mem_structured = llm.with_structured_output(MemoryOutput)
    mem_prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You maintain a concise summary of what a user dislikes in academic papers. "
         "Merge the new rejection comment into the existing summary. "
         "Keep the result under 300 words."),
        ("human",
         "Existing summary:\n{existing}\n\nNew rejection comment:\n{new_comment}\n\n"
         "Output the updated consolidated summary."),
    ])
    mem_chain = mem_prompt | mem_structured

    feedback = ""
    for comment in simulated_rejections:
        result = mem_chain.invoke({
            "existing": feedback or "No prior feedback.",
            "new_comment": comment,
        })
        feedback = result.summarized_feedback

    logger.info(f"Built feedback memory from {len(simulated_rejections)} rejections: {feedback[:100]}...")

    # Run 1: blank memory
    run1 = run_experiment_2_agent_efficacy(papers, criteria, feedback_memory="")

    # Run 2: with accumulated memory
    run2 = run_experiment_2_agent_efficacy(papers, criteria, feedback_memory=feedback)

    return {
        "Run 1 (blank memory)": run1["Evaluator + Critique"],
        "Run 2 (with feedback)": run2["Evaluator + Critique"],
    }


# ===================================================================
# EXPERIMENT 4: Context Size Economic Decay
# ===================================================================

def run_experiment_4_context_cost(
    papers: list[PaperRecord],
    criteria: list[str],
) -> dict[str, ExperimentMetrics]:
    """
    Compare agent quality at different context sizes:
      - Abstract only (~200 tokens)
      - Full text truncated to 2000 tokens
      - Full text truncated to 4000 tokens
      - Full text (up to 8000 tokens)

    Measures F1 vs cost tradeoff.
    """
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from app.agents.schemas import EvaluatorOutput
    from app.core.config import settings

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0, api_key=settings.OPENAI_API_KEY)
    eval_structured = llm.with_structured_output(EvaluatorOutput)
    eval_prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are an elite academic recommender AI. Evaluate against:\n{criteria}\n\n"
         "Output 'accept', 'borderline', or 'reject'."),
        ("human", "Evaluate:\n\n{text}"),
    ])
    eval_chain = eval_prompt | eval_structured
    criteria_str = "\n- ".join(criteria)

    def _truncate(text: str, max_tokens: int) -> str:
        words = text.split()
        return " ".join(words[:max_tokens])

    variants = {
        "Abstract Only": None,           # use abstract
        "2000 tokens": 2000,
        "4000 tokens": 4000,
        "8000 tokens (full)": 8000,
    }

    results = {}
    for variant_name, max_tok in variants.items():
        preds = []
        stage_results = []
        for paper in papers:
            if max_tok is None:
                text = paper.abstract
            else:
                text = _truncate(paper.full_text, max_tok)

            t0 = time.time()
            result = eval_chain.invoke({"criteria": criteria_str, "text": text})
            latency = (time.time() - t0) * 1000

            pred = 1 if result.decision in ("accept", "borderline") else 0
            preds.append(pred)

            n_input_tokens = len(text.split()) * 2 + 100  # rough estimate
            stage_results.append(StageResult(
                paper_id=paper.paper_id,
                decision=result.decision,
                latency_ms=latency,
                input_tokens=n_input_tokens,
                output_tokens=50,
            ))

        results[variant_name] = _calc_metrics(
            name=f"Exp4: {variant_name}",
            papers=papers,
            predictions=preds,
            results=stage_results,
        )

    return results


# ===================================================================
# CLI runner
# ===================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run benchmark experiments")
    parser.add_argument("--experiment", type=int, choices=[1, 2, 3, 4], required=True)
    parser.add_argument("--dataset", type=str, default=None)
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    papers = load_dataset(args.dataset)
    criteria = [
        "Must feature multi-agent systems with 2 or more collaborating agents",
        "Must focus on Large Language Models (not classical robotics or RL-only)",
        "Must include experimental evaluation or benchmarks",
    ]

    if args.experiment == 1:
        results = run_experiment_1_retrieval(papers, criteria, top_k=args.top_k)
    elif args.experiment == 2:
        results = run_experiment_2_agent_efficacy(papers, criteria)
    elif args.experiment == 3:
        results = run_experiment_3_feedback_shift(papers, criteria, simulated_rejections=[
            "Too focused on robotics, I don't care about physical robot control",
            "Pure reinforcement learning without LLM involvement",
            "Theoretical only, no experiments or code",
            "Single agent system, not multi-agent",
            "About NLP tasks like translation, not agent coordination",
        ])
    elif args.experiment == 4:
        results = run_experiment_4_context_cost(papers, criteria)

    for name, metrics in results.items():
        print(f"\n{'='*60}")
        print(f"  {name}")
        print(f"{'='*60}")
        print(f"  Precision: {metrics.precision:.4f}")
        print(f"  Recall:    {metrics.recall:.4f}")
        print(f"  F1:        {metrics.f1:.4f}")
        print(f"  TP={metrics.true_positives}  FP={metrics.false_positives}  "
              f"FN={metrics.false_negatives}  TN={metrics.true_negatives}")
        print(f"  Avg latency: {metrics.avg_latency_ms:.0f} ms")
        print(f"  Total cost:  ${metrics.total_cost_usd:.6f}")