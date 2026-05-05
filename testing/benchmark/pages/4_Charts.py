"""Page 4 — Charts: render thesis-ready figures, export PNG + LaTeX."""

import io
import sys
from pathlib import Path

import streamlit as st

_BENCH = Path(__file__).resolve().parents[1]
if str(_BENCH.parent) not in sys.path:
    sys.path.insert(0, str(_BENCH.parent))

from benchmark.lib import charts, paths
from benchmark.lib.schemas import ResultsFile

st.title("4 — Charts")


def list_results() -> list[ResultsFile]:
    rdir = paths.data_root() / "results"
    if not rdir.exists():
        return []
    out = []
    for f in sorted(rdir.glob("*.json")):
        try:
            out.append(ResultsFile.model_validate_json(f.read_text(encoding="utf-8")))
        except Exception as e:
            st.warning(f"Skipped {f.name}: {e}")
    return out


def fig_to_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    buf.seek(0)
    return buf.read()


def export_block(chart_id: str, fig, default_caption: str) -> None:
    cap = st.text_input(f"Caption for {chart_id}", value=default_caption, key=f"cap_{chart_id}")
    label = st.text_input(f"Label for {chart_id}", value=f"fig:{chart_id}", key=f"lbl_{chart_id}")
    png_bytes = fig_to_bytes(fig)
    rel_path = f"figures/{chart_id}.png"
    st.download_button("Export PNG (300dpi)", data=png_bytes, file_name=f"{chart_id}.png", mime="image/png", key=f"dl_{chart_id}")
    latex = charts.latex_figure_block(rel_path, cap, label)
    st.code(latex, language="latex")


all_results = list_results()
if not all_results:
    st.info("No results yet. Run an experiment on Page 3.")
    st.stop()

chart_choice = st.selectbox("Chart", [
    "Chart 1 — Precision by stage (one run)",
    "Chart 3 — Precision × Cost scatter (multi-run)",
    "Chart 5 — Deep Reader ablation (2 runs)",
    "Chart 8 — Cross-goal (multi-goal, same config)",
    "Chart 10 — Model comparison (3 runs)",
])

run_labels = [f"{r.run_id}" for r in all_results]

if chart_choice.startswith("Chart 1"):
    pick = st.selectbox("Run", run_labels)
    r = all_results[run_labels.index(pick)]
    fig = charts.chart1_precision_by_stage(r)
    st.pyplot(fig)
    export_block("chart1_precision_by_stage", fig,
                 f"Precision by stage for {r.goal_id} using {r.config.model}.")

elif chart_choice.startswith("Chart 3"):
    picks = st.multiselect("Runs", run_labels, default=run_labels[:4])
    rs = [all_results[run_labels.index(p)] for p in picks]
    if rs:
        fig = charts.chart3_precision_cost_scatter(rs)
        st.pyplot(fig)
        export_block("chart3_precision_cost", fig, "Precision–cost frontier across K values.")

elif chart_choice.startswith("Chart 5"):
    off_pick = st.selectbox("Deep Reader OFF run", run_labels, key="dr_off")
    on_pick = st.selectbox("Deep Reader ON run", run_labels, key="dr_on")
    off = all_results[run_labels.index(off_pick)]
    on = all_results[run_labels.index(on_pick)]
    fig = charts.chart5_deep_reader_ablation(off, on)
    st.pyplot(fig)
    export_block("chart5_deep_reader_ablation", fig,
                 f"Deep Reader ablation on {off.goal_id}.")

elif chart_choice.startswith("Chart 8"):
    picks = st.multiselect("One run per goal", run_labels)
    rs = [all_results[run_labels.index(p)] for p in picks]
    by_goal = {r.goal_id: r for r in rs}
    if len(by_goal) >= 2:
        fig = charts.chart8_cross_goal(by_goal)
        st.pyplot(fig)
        export_block("chart8_cross_goal", fig,
                     "Cross-goal precision comparison.")
    else:
        st.info("Pick at least one run per goal.")

elif chart_choice.startswith("Chart 10"):
    picks = st.multiselect("Three runs (same goal, different models)", run_labels)
    rs = [all_results[run_labels.index(p)] for p in picks]
    by_model = {r.config.model: r for r in rs}
    if len(by_model) >= 2:
        fig = charts.chart10_model_comparison(by_model)
        st.pyplot(fig)
        export_block("chart10_model_comparison", fig,
                     f"Model comparison on {rs[0].goal_id}.")
    else:
        st.info("Pick at least 2 different-model runs.")
