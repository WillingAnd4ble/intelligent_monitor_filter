"""Page 5 — Distiller Lab: test how different models + prompts distill a goal."""

import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

_BENCH = Path(__file__).resolve().parents[1]
if str(_BENCH.parent) not in sys.path:
    sys.path.insert(0, str(_BENCH.parent))

from benchmark.lib import distiller_lab, prompts
from benchmark.lib.distiller_lab import DistillerExperiment, ModelResult


st.title("5 — Distiller Lab")

st.caption(
    "Compare how different LLMs distill the same goal under the same (or edited) "
    "prompt. The canonical prod prompt lives in "
    "`backend/app/agents/distiller.py` and is mirrored as `prompts.DISTILLER_SYSTEM` "
    "/ `prompts.DISTILLER_HUMAN` here. Edits on this page are sandboxed — they do "
    "NOT change the prod prompt."
)

# --- inputs ---
with st.form("distiller_inputs"):
    raw_goal = st.text_area(
        "Goal text",
        value=("Practical methods for detecting and mitigating AI-generated "
               "phishing, deepfake voice attacks, and prompt-injection "
               "vulnerabilities in production LLM-based assistants."),
        height=140,
    )
    cats_str = st.text_input("Categories (comma-separated)", value="cs.AI, cs.CR")
    topics_str = st.text_input("Topics (comma-separated)", value="")
    interests_str = st.text_input("Content interests (comma-separated)", value="")

    model_choices = [
        "gpt-4o-mini",
        "claude-haiku-4-5-20251001",
        "gpt-5.4-nano-2026-03-17",
    ]
    selected_models = st.multiselect("Models", model_choices, default=model_choices)

    st.markdown("**Prompt (editable — sandboxed, does not affect prod)**")
    sys_prompt = st.text_area(
        "System prompt", value=prompts.DISTILLER_SYSTEM, height=200, key="sys_p"
    )
    hum_prompt = st.text_area(
        "Human prompt template", value=prompts.DISTILLER_HUMAN, height=140, key="hum_p"
    )
    if st.form_submit_button("Reset prompts to default"):
        st.session_state.sys_p = prompts.DISTILLER_SYSTEM
        st.session_state.hum_p = prompts.DISTILLER_HUMAN
        st.rerun()

    submitted = st.form_submit_button("Run distillation", type="primary")

if submitted:
    if not raw_goal.strip():
        st.error("Goal text is required.")
        st.stop()
    if not selected_models:
        st.error("Pick at least one model.")
        st.stop()

    cats = [c.strip() for c in cats_str.split(",") if c.strip()]
    tops = [t.strip() for t in topics_str.split(",") if t.strip()]
    ints = [i.strip() for i in interests_str.split(",") if i.strip()]

    results: dict[str, ModelResult] = {}
    bar = st.progress(0.0)
    status = st.empty()
    for i, model in enumerate(selected_models):
        status.write(f"Calling {model}…")
        r = distiller_lab.run_one(
            model=model,
            system_prompt=sys_prompt,
            human_prompt=hum_prompt,
            raw_goal=raw_goal,
            categories=cats,
            topics=tops,
            content_interest=ints,
        )
        results[model] = r
        bar.progress((i + 1) / len(selected_models))

    status.empty()

    # --- side-by-side display ---
    cols = st.columns(len(results))
    for col, (model, r) in zip(cols, results.items()):
        with col:
            st.subheader(model)
            if r.error:
                st.error(r.error)
                continue
            st.markdown("**Criteria**")
            for j, c in enumerate(r.distilled_criteria, 1):
                st.write(f"{j}. {c}")
            st.markdown("**Lexical query**")
            st.code(r.lexical_query)
            st.caption(
                f"in {r.tokens_in} / out {r.tokens_out} tokens | "
                f"{r.latency_ms:.0f} ms | ${r.cost_usd:.5f}"
            )

    # --- save ---
    st.divider()
    suggested = f"distiller_lab_{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%MZ')}"
    exp_id = st.text_input("experiment_id", value=suggested)
    if st.button("Save comparison"):
        exp = DistillerExperiment(
            experiment_id=exp_id,
            created_at=datetime.now(timezone.utc),
            raw_goal=raw_goal,
            categories=cats, topics=tops, content_interest=ints,
            system_prompt=sys_prompt, human_prompt=hum_prompt,
            results=results,
        )
        path = distiller_lab.save_experiment(exp)
        st.success(f"Saved {path}")

# --- past experiments browser ---
st.divider()
st.subheader("Past distiller experiments")
existing = distiller_lab.list_experiments()
if not existing:
    st.caption("No experiments saved yet.")
else:
    pick = st.selectbox("Open one", existing)
    if pick:
        exp = distiller_lab.load_experiment(pick)
        st.write(f"**Goal:** {exp.raw_goal}")
        st.caption(f"created: {exp.created_at} | models: {list(exp.results.keys())}")
        for model, r in exp.results.items():
            with st.expander(model):
                if r.error:
                    st.error(r.error)
                else:
                    for j, c in enumerate(r.distilled_criteria, 1):
                        st.write(f"{j}. {c}")
                    st.code(r.lexical_query)
                    st.caption(
                        f"in {r.tokens_in} / out {r.tokens_out} tokens | "
                        f"{r.latency_ms:.0f} ms | ${r.cost_usd:.5f}"
                    )
