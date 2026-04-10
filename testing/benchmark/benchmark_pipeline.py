"""
Streamlit Benchmarking Dashboard

Run with:  streamlit run benchmark/benchmark_pipeline.py

Loads a pre-extracted evaluation_dataset.json, runs the 4 thesis experiments
against REAL LLM APIs, and displays precision/recall/F1 charts.
"""

import sys
import os
import json
from pathlib import Path

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# Make backend importable
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from experiments import (
    load_dataset,
    run_experiment_1_retrieval,
    run_experiment_2_agent_efficacy,
    run_experiment_3_feedback_shift,
    run_experiment_4_context_cost,
    ExperimentMetrics,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Agent Pipeline Benchmarks", layout="wide")
st.title("Agent-Based ArXiv Filter — Benchmarking Dashboard")

# ---------------------------------------------------------------------------
# Sidebar: dataset & criteria config
# ---------------------------------------------------------------------------
st.sidebar.header("Configuration")

dataset_path = st.sidebar.text_input(
    "Dataset path",
    value=str(Path(__file__).parent.parent / "evaluation_dataset.json"),
)

criteria_text = st.sidebar.text_area(
    "Distilled Criteria (one per line)",
    value=(
        "Must feature multi-agent systems with 2+ collaborating agents\n"
        "Must focus on Large Language Models (not robotics or RL-only)\n"
        "Must include experimental evaluation or benchmarks\n"
        "Must discuss inter-agent communication or coordination"
    ),
)
criteria = [c.strip() for c in criteria_text.strip().split("\n") if c.strip()]

top_k = st.sidebar.slider("Retrieval top-k", min_value=5, max_value=50, value=10)

# Load dataset
try:
    papers = load_dataset(dataset_path)
    n_relevant = sum(1 for p in papers if p.ground_truth == 1)
    n_total = len(papers)
    st.sidebar.success(f"Loaded {n_total} papers ({n_relevant} relevant, {n_total - n_relevant} irrelevant)")
except Exception as e:
    st.sidebar.error(f"Failed to load dataset: {e}")
    st.stop()


# ---------------------------------------------------------------------------
# Helper: render metrics table + bar chart
# ---------------------------------------------------------------------------

def render_metrics(results: dict[str, ExperimentMetrics]):
    """Show a comparison table and bar chart for a set of experiment variants."""
    rows = []
    for name, m in results.items():
        rows.append({
            "Variant": name,
            "Precision": m.precision,
            "Recall": m.recall,
            "F1": m.f1,
            "TP": m.true_positives,
            "FP": m.false_positives,
            "FN": m.false_negatives,
            "TN": m.true_negatives,
            "Avg Latency (ms)": m.avg_latency_ms,
            "Cost ($)": m.total_cost_usd,
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Bar chart: Precision / Recall / F1
    fig, ax = plt.subplots(figsize=(10, 4))
    x = range(len(df))
    width = 0.25
    ax.bar([i - width for i in x], df["Precision"], width, label="Precision", color="#2196F3")
    ax.bar(x, df["Recall"], width, label="Recall", color="#FF9800")
    ax.bar([i + width for i in x], df["F1"], width, label="F1", color="#4CAF50")
    ax.set_xticks(x)
    ax.set_xticklabels(df["Variant"], rotation=15, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    st.pyplot(fig)

    return df


def render_cost_curve(results: dict[str, ExperimentMetrics]):
    """Plot F1 vs Cost for Experiment 4."""
    names = list(results.keys())
    f1s = [results[n].f1 for n in names]
    costs = [results[n].total_cost_usd for n in names]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(costs, f1s, "o-", color="#9C27B0", markersize=8)
    for i, name in enumerate(names):
        ax.annotate(name, (costs[i], f1s[i]), textcoords="offset points",
                    xytext=(5, 10), fontsize=8)
    ax.set_xlabel("Total Cost ($)")
    ax.set_ylabel("F1 Score")
    ax.set_title("Cost-to-Quality Plateau")
    ax.grid(alpha=0.3)
    st.pyplot(fig)


# ---------------------------------------------------------------------------
# Experiment tabs
# ---------------------------------------------------------------------------

tab1, tab2, tab3, tab4 = st.tabs([
    "Exp 1: Retrieval Efficacy",
    "Exp 2: Multi-Agent Efficacy",
    "Exp 3: Feedback Shift",
    "Exp 4: Context-Cost Tradeoff",
])

# ── Experiment 1 ──────────────────────────────────────────────────

with tab1:
    st.header("Experiment 1: Pre-Filter Retrieval Efficacy")
    st.markdown("""
    Compares three retrieval methods **before** any LLM agents act:
    - **BM25**: Keyword/lexical matching (TF-IDF proxy)
    - **Semantic**: Embedding cosine similarity
    - **RRF**: Reciprocal Rank Fusion of both

    Measures which retrieval method surfaces the most relevant papers in the top-k.
    """)

    if st.button("Run Experiment 1", key="exp1"):
        with st.spinner("Running retrieval experiment..."):
            results = run_experiment_1_retrieval(papers, criteria, top_k=top_k)
        render_metrics(results)

# ── Experiment 2 ──────────────────────────────────────────────────

with tab2:
    st.header("Experiment 2: Multi-Agent Pipeline Efficacy")
    st.markdown("""
    Compares:
    - **Evaluator Only**: Single LLM agent makes accept/borderline/reject decisions
    - **Evaluator + Critique**: Borderline papers get a second opinion from the Critique agent

    Uses **real API calls** to GPT-4o-mini. Shows whether the Critique node improves precision.
    """)

    feedback_for_exp2 = st.text_area(
        "Feedback memory for Critique (leave empty to test without)",
        value="User dislikes pure robotics papers, single-agent RL, and theoretical proofs without experiments.",
        key="exp2_feedback",
    )

    if st.button("Run Experiment 2", key="exp2"):
        with st.spinner("Running agent pipeline on all papers (real API calls)..."):
            results = run_experiment_2_agent_efficacy(papers, criteria, feedback_memory=feedback_for_exp2)
        render_metrics(results)

# ── Experiment 3 ──────────────────────────────────────────────────

with tab3:
    st.header("Experiment 3: Longitudinal Feedback Shift")
    st.markdown("""
    Simulates the feedback learning loop:
    - **Run 1**: Pipeline with blank feedback memory
    - **Run 2**: Pipeline after 5 simulated user rejections are summarized

    Shows whether the MemorySummarizer improves filtering over time.
    """)

    rejections_text = st.text_area(
        "Simulated rejection comments (one per line)",
        value=(
            "Too focused on robotics, I don't care about physical robot control\n"
            "Pure reinforcement learning without LLM involvement\n"
            "Theoretical only, no experiments or code\n"
            "Single agent system, not multi-agent\n"
            "About NLP tasks like translation, not agent coordination"
        ),
        key="exp3_rejections",
    )
    rejections = [r.strip() for r in rejections_text.strip().split("\n") if r.strip()]

    if st.button("Run Experiment 3", key="exp3"):
        with st.spinner("Running 2 pipeline passes (blank + with feedback)..."):
            results = run_experiment_3_feedback_shift(papers, criteria, simulated_rejections=rejections)
        render_metrics(results)

# ── Experiment 4 ──────────────────────────────────────────────────

with tab4:
    st.header("Experiment 4: Context Size vs Cost Tradeoff")
    st.markdown("""
    Tests how much context the LLM needs to make good decisions:
    - **Abstract Only** (~200 tokens) — cheapest
    - **2000 tokens** of full text
    - **4000 tokens** of full text
    - **8000 tokens** (full paper) — most expensive

    Plots the "Cost-to-Quality Plateau": the point where adding more tokens stops improving F1.
    """)

    if st.button("Run Experiment 4", key="exp4"):
        with st.spinner("Running 4 variants across all papers (real API calls)..."):
            results = run_experiment_4_context_cost(papers, criteria)
        df = render_metrics(results)
        render_cost_curve(results)


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.caption("Agent-Based ArXiv Filter Benchmarking Suite | Thesis Project 2026")