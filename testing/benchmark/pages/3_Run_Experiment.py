"""Page 3 — Run Experiment: configure cascade toggles, run, save result."""

import os
import sys
from pathlib import Path

import streamlit as st

_BENCH = Path(__file__).resolve().parents[1]
if str(_BENCH.parent) not in sys.path:
    sys.path.insert(0, str(_BENCH.parent))

from benchmark.lib import paths, runner, pricing
from benchmark.lib.schemas import GoalFile, CandidatesFile, LabelsFile, RunConfig

st.title("3 — Run Experiment")


def list_goal_ids() -> list[str]:
    p = paths.data_root() / "goals"
    return sorted([f.stem for f in p.glob("*.json")]) if p.exists() else []


goal_ids = list_goal_ids()
if not goal_ids:
    st.info("No frozen goals yet.")
    st.stop()

goal_id = st.selectbox("Goal", goal_ids)
gf = GoalFile.model_validate_json(paths.goal_path(goal_id).read_text(encoding="utf-8"))
labels_p = paths.labels_path(goal_id)
if not labels_p.exists():
    st.error(f"No labels for {goal_id}. Label some papers on Page 2 first.")
    st.stop()
lf = LabelsFile.model_validate_json(labels_p.read_text(encoding="utf-8"))
cf = CandidatesFile.model_validate_json(paths.candidates_path(goal_id, "rrf").read_text(encoding="utf-8"))

st.caption(f"{len(lf.labels)} labeled / {len(cf.papers)} candidates")

st.subheader("Preset experiments")
cols = st.columns(5)
preset = None
if cols[0].button("Exp 1 — Model selection"): preset = "exp1"
if cols[1].button("Exp 2 — Critique ablation"): preset = "exp2"
if cols[2].button("Exp 3 — Memory effect"): preset = "exp3"
if cols[3].button("Exp 4 — K curve"): preset = "exp4"
if cols[4].button("Exp 5 — Deep Reader"): preset = "exp5"

st.subheader("Toggle config")

model_choices = [
    # Direct providers
    "gpt-4o-mini",
    "claude-haiku-4-5-20251001",
    "gpt-5.4-nano-2026-03-17",
    # OpenRouter — any id with '/' is auto-routed via OPENROUTER_API_KEY.
    "google/gemini-2.5-flash",
    "google/gemini-3-flash-preview",
    "google/gemini-3.1-flash-lite-preview",
    "deepseek/deepseek-v4-flash",
    "qwen/qwen3.6-flash",
    "(custom — type below)",
]
default_model = "gpt-4o-mini"
critique_default = True
deep_reader_default = True
memory_default = "empty"
k_default = 10

if preset == "exp1":
    st.info("Exp 1 — run once per model, comparing precision/cost/latency. Pick a model below and click Run, then repeat for the other two.")
elif preset == "exp2":
    st.info("Exp 2 — run with Critique=ON, then again with Critique=OFF.")
elif preset == "exp3":
    st.info("Exp 3 — run with memory='empty', then again with memory='seeded'.")
elif preset == "exp4":
    st.info("Exp 4 — run for K ∈ {5, 10, 15, 30}.")
elif preset == "exp5":
    st.info("Exp 5 — run with Deep Reader=ON, then again with Deep Reader=OFF.")

model_pick = st.selectbox("Model", model_choices, index=model_choices.index(default_model))
if model_pick == "(custom — type below)":
    model = st.text_input("Custom model id (OpenRouter or otherwise)", value="").strip()
    if not model:
        st.info("Type a model id above before running.")
else:
    model = model_pick
critique = st.checkbox("Critique enabled", value=critique_default)
deep_reader = st.checkbox("Deep Reader enabled", value=deep_reader_default)
memory = st.selectbox("Feedback memory", ["empty", "seeded"], index=0 if memory_default == "empty" else 1)
k = st.selectbox("deep_scan_limit K", [5, 10, 15, 30], index=[5, 10, 15, 30].index(k_default))

config = RunConfig(model=model, evaluator=True, critique=critique,
                   deep_reader=deep_reader, feedback_memory=memory, deep_scan_limit=k)

st.subheader("Cost preview")
n_papers = len(lf.labels)
est_in = n_papers * 400
est_out = n_papers * 50
if critique:
    est_in += int(n_papers * 0.2 * 600)
    est_out += int(n_papers * 0.2 * 40)
if deep_reader:
    n_dr = min(k, n_papers)
    est_in += n_dr * 5000
    est_out += n_dr * 200
est_cost = pricing.compute_cost_usd(model, est_in, est_out)
cap = float(os.environ.get("BENCHMARK_COST_CAP_USD", "5.00"))
st.write(f"Estimated worst-case cost (assuming 100% cache miss): **${est_cost:.3f}**")
st.write(f"Hard cap: ${cap:.2f}")

over_cap = est_cost > cap
override = False
if over_cap:
    override = st.checkbox(f"I acknowledge cost may exceed ${cap:.2f} and want to proceed anyway")

run_disabled = over_cap and not override
if st.button("Run", disabled=run_disabled):
    with st.spinner("Running cascade — first run may take several minutes (subsequent are cached)..."):
        criteria_text = [c.text for c in gf.distilled_criteria]
        result = runner.run(goal_id=goal_id, config=config, candidates=cf,
                            labels=lf, criteria=criteria_text,
                            dataset_id=gf.dataset_id)
        out_path = runner.save_result(result)
    st.success(f"Saved {out_path}"
               + (f" (dataset: {gf.dataset_id})" if gf.dataset_id else ""))
    st.json(result.metrics.model_dump())
