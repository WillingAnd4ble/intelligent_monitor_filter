"""Page 1 — Pull Candidates: distill goal, freeze criteria, pull retrievers."""

import asyncio
import sys
from pathlib import Path

import streamlit as st

# Make benchmark/lib importable
_BENCH = Path(__file__).resolve().parents[1]
if str(_BENCH.parent) not in sys.path:
    sys.path.insert(0, str(_BENCH.parent))

from benchmark.lib import datasets, distill, paths, pull
from benchmark.lib.schemas import Criterion


st.title("1 — Pull Candidates")

# --- Dataset partition selection ---
with st.expander("Dataset partition", expanded=True):
    existing = datasets.list_datasets()
    options = ["(no partition — query whole papers table)"] + existing
    pick = st.selectbox("Bind this goal to a dataset", options)
    chosen_dataset_id = None if pick == options[0] else pick

    st.caption(
        "A dataset freezes which paper IDs all retrievers can return. "
        "Goals tied to the same dataset are exactly comparable, even months later."
    )

    with st.form("create_dataset_form"):
        new_id = st.text_input("New dataset_id (e.g. dataset_apr07_200)")
        new_desc = st.text_input("Short description")
        if st.form_submit_button("Snapshot current papers as new dataset"):
            if not new_id or not new_desc:
                st.error("dataset_id and description required.")
            else:
                try:
                    df = datasets.create_from_current_papers(new_id, new_desc)
                    st.success(f"Created {paths.dataset_path(df.dataset_id)} — {df.paper_count} papers.")
                except FileExistsError as e:
                    st.error(str(e))

DISTILL_MODEL_CHOICES = [
    "gpt-4o-mini",
    "claude-haiku-4-5-20251001",
    "gpt-5.4-nano-2026-03-17",
    "google/gemini-2.5-flash",
    "google/gemini-3-flash-preview",
    "google/gemini-3.1-flash-lite-preview",
    "deepseek/deepseek-v4-flash",
    "qwen/qwen3.6-flash",
]

with st.form("goal_form"):
    goal_id = st.text_input("goal_id (slug, e.g. security_v1)")
    raw_goal = st.text_area("Raw filtering goal", height=160)
    top_k = st.number_input("Top K", min_value=5, max_value=100, value=30, step=5)
    distill_model = st.selectbox(
        "Distillation model (also stamped on the frozen goal)",
        DISTILL_MODEL_CHOICES, index=0,
    )
    distill_clicked = st.form_submit_button("Distill & Preview")

if distill_clicked:
    if not goal_id or not raw_goal:
        st.error("goal_id and raw_goal are required.")
    elif paths.goal_path(goal_id).exists():
        st.error(f"{goal_id}.json already exists — frozen goals are immutable. Use a new goal_id.")
    else:
        with st.spinner(f"Distilling with {distill_model}..."):
            try:
                criteria, lexical_query = distill.distill(
                    raw_goal=raw_goal, model=distill_model
                )
            except Exception as e:
                st.error(f"Distillation failed: {e}")
                st.stop()
        st.session_state.draft_criteria = [c.model_dump() for c in criteria]
        st.session_state.draft_lexical = lexical_query
        st.session_state.draft_goal_id = goal_id
        st.session_state.draft_raw_goal = raw_goal
        st.session_state.draft_top_k = int(top_k)
        st.session_state.draft_distill_model = distill_model

if "draft_criteria" in st.session_state:
    st.subheader("Distilled criteria — edit if needed")
    edited = []
    for c in st.session_state.draft_criteria:
        new_text = st.text_input(f"Criterion {c['id']}", value=c["text"], key=f"crit_{c['id']}")
        edited.append({"id": c["id"], "text": new_text})
    new_lex = st.text_input("Lexical query (BM25)", value=st.session_state.draft_lexical, key="lex_q")

    col_a, col_b = st.columns([1, 3])
    with col_a:
        if st.button("Re-distill"):
            with st.spinner(f"Re-distilling with {st.session_state.draft_distill_model}..."):
                try:
                    criteria, lexical_query = distill.distill(
                        raw_goal=st.session_state.draft_raw_goal,
                        model=st.session_state.draft_distill_model,
                    )
                except Exception as e:
                    st.error(f"Re-distill failed: {e}")
                    st.stop()
            st.session_state.draft_criteria = [c.model_dump() for c in criteria]
            st.session_state.draft_lexical = lexical_query
            st.rerun()
    with col_b:
        if st.button("Freeze & Pull all three retrievers"):
            criteria_objs = [Criterion(**c) for c in edited]
            with st.spinner("Freezing goal..."):
                gf = distill.freeze(
                    goal_id=st.session_state.draft_goal_id,
                    raw_goal=st.session_state.draft_raw_goal,
                    criteria=criteria_objs,
                    lexical_query=new_lex,
                    distiller_model=st.session_state.draft_distill_model,
                    dataset_id=chosen_dataset_id,
                )
                st.success(f"Frozen: {paths.goal_path(gf.goal_id)}"
                           + (f" (dataset: {chosen_dataset_id})" if chosen_dataset_id else ""))

            with st.spinner("Computing SPECTER2 embedding..."):
                emb = asyncio.run(pull.embed_goal(st.session_state.draft_raw_goal, gf.goal_id))
                st.success(f"Embedding: {len(emb)} dims")

            allow_ids = (list(datasets.paper_ids_for(chosen_dataset_id))
                         if chosen_dataset_id else None)

            for retriever in ("rrf", "bm25", "specter2"):
                with st.spinner(f"Pulling {retriever}..."):
                    cf = asyncio.run(pull.pull_and_save(
                        goal_id=gf.goal_id, retriever=retriever,
                        lexical_query=new_lex, goal_embedding=emb,
                        k=st.session_state.draft_top_k,
                        paper_ids=allow_ids,
                    ))
                    st.success(f"{retriever}: {len(cf.papers)} papers → {paths.candidates_path(gf.goal_id, retriever)}")

            for k in ("draft_criteria", "draft_lexical", "draft_goal_id",
                      "draft_raw_goal", "draft_top_k", "draft_distill_model"):
                st.session_state.pop(k, None)
            st.balloons()
