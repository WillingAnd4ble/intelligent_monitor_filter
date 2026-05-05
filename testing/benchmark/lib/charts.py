"""Chart-building functions. Each takes ResultsFile(s) → matplotlib Figure.

The 10-chart catalog from spec §7. Implemented now: 1, 3, 5, 8, 10.
The remaining are stubs — fill in as thesis needs evolve.
"""

from typing import List

import matplotlib.pyplot as plt

from benchmark.lib.chart_style import apply_thesis_style
from benchmark.lib.schemas import ResultsFile


def chart1_precision_by_stage(result: ResultsFile) -> plt.Figure:
    apply_thesis_style()
    m = result.metrics
    stages = ["after Evaluator", "after Critique", "after Deep Reader", "Final"]
    values = [m.precision_after_evaluator, m.precision_after_critique,
              m.precision_after_deep_reader, m.precision_final]
    none_mask = [v is None for v in values]
    values = [v if v is not None else 0.0 for v in values]
    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(stages, values)
    for i, b in enumerate(bars):
        if none_mask[i]:
            b.set_hatch("//")
            b.set_alpha(0.3)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Precision")
    ax.set_title(f"Precision by stage — {result.goal_id} / {result.config.model}")
    return fig


def chart3_precision_cost_scatter(results: List[ResultsFile]) -> plt.Figure:
    apply_thesis_style()
    fig, ax = plt.subplots(figsize=(6, 4))
    for r in results:
        ax.scatter(r.metrics.cost_usd, r.metrics.precision_final, s=60)
        ax.annotate(f"K={r.config.deep_scan_limit}",
                    (r.metrics.cost_usd, r.metrics.precision_final),
                    xytext=(5, 5), textcoords="offset points", fontsize=8)
    ax.set_xlabel("Cost (USD)")
    ax.set_ylabel("Precision")
    ax.set_ylim(0, 1)
    ax.set_title("Precision × Cost frontier")
    return fig


def chart5_deep_reader_ablation(off: ResultsFile, on: ResultsFile) -> plt.Figure:
    apply_thesis_style()
    labels = ["Deep Reader OFF", "Deep Reader ON"]
    p = [off.metrics.precision_final, on.metrics.precision_final]
    ci = [off.metrics.precision_final_ci, on.metrics.precision_final_ci]
    err_low = [p[i] - ci[i][0] for i in range(2)]
    err_high = [ci[i][1] - p[i] for i in range(2)]
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.bar(labels, p, yerr=[err_low, err_high], capsize=6)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Precision (95% Wilson CI)")
    ax.set_title(f"Deep Reader ablation — {off.goal_id}")
    return fig


def chart8_cross_goal(results_by_goal: dict) -> plt.Figure:
    """results_by_goal: {goal_id: ResultsFile} — same config across goals."""
    apply_thesis_style()
    goals = list(results_by_goal.keys())
    p = [results_by_goal[g].metrics.precision_final for g in goals]
    ci = [results_by_goal[g].metrics.precision_final_ci for g in goals]
    err_low = [p[i] - ci[i][0] for i in range(len(goals))]
    err_high = [ci[i][1] - p[i] for i in range(len(goals))]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(goals, p, yerr=[err_low, err_high], capsize=6)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Precision (95% Wilson CI)")
    ax.set_title("Cross-goal generalizability")
    return fig


def chart10_model_comparison(results_by_model: dict) -> plt.Figure:
    """results_by_model: {model_name: ResultsFile} — same goal across models."""
    apply_thesis_style()
    models = list(results_by_model.keys())
    p = [results_by_model[m].metrics.precision_final for m in models]
    cost = [results_by_model[m].metrics.cost_usd for m in models]
    lat = [results_by_model[m].metrics.latency_ms_median / 1000.0 for m in models]
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    axes[0].bar(models, p); axes[0].set_ylim(0, 1); axes[0].set_title("Precision"); axes[0].tick_params(axis="x", rotation=20)
    axes[1].bar(models, cost); axes[1].set_title("Cost (USD)"); axes[1].tick_params(axis="x", rotation=20)
    axes[2].bar(models, lat); axes[2].set_title("Median latency (s)"); axes[2].tick_params(axis="x", rotation=20)
    fig.suptitle("Model comparison")
    fig.tight_layout()
    return fig


def latex_figure_block(png_relative_path: str, caption: str, label: str) -> str:
    return (
        "\\begin{figure}[H]\n"
        "  \\centering\n"
        f"  \\includegraphics[width=0.85\\linewidth]{{{png_relative_path}}}\n"
        f"  \\caption{{{caption}}}\n"
        f"  \\label{{{label}}}\n"
        "\\end{figure}\n"
    )
