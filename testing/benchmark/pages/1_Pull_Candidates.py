"""Page 1 — Pull Candidates: distill goal, freeze criteria, pull retrievers."""

import asyncio
import sys
from pathlib import Path

import streamlit as st

# Make benchmark/lib importable
_BENCH = Path(__file__).resolve().parents[1]
if str(_BENCH.parent) not in sys.path:
    sys.path.insert(0, str(_BENCH.parent))

from benchmark.lib import distill, paths, pull
from benchmark.lib.schemas import Criterion


st.title("1 — Pull Candidates")

with st.form("goal_form"):
    goal_id = st.text_input("goal_id (slug, e.g. security_v1)")
    raw_goal = st.text_area("Raw filtering goal", height=160)
    top_k = st.number_input("Top K", min_value=5, max_value=100, value=30, step=5)
    distill_clicked = st.form_submit_button("Distill & Preview")

if distill_clicked:
    if not goal_id or not raw_goal:
        st.error("goal_id and raw_goal are required.")
    elif paths.goal_path(goal_id).exists():
        st.error(f"{goal_id}.json already exists — frozen goals are immutable. Use a new goal_id.")
    else:
        with st.spinner("Distilling..."):
            criteria, lexical_query = distill.distill(raw_goal=raw_goal)
        st.session_state.draft_criteria = [c.model_dump() for c in criteria]
        st.session_state.draft_lexical = lexical_query
        st.session_state.draft_goal_id = goal_id
        st.session_state.draft_raw_goal = raw_goal
        st.session_state.draft_top_k = int(top_k)

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
            with st.spinner("Re-distilling..."):
                criteria, lexical_query = distill.distill(raw_goal=st.session_state.draft_raw_goal)
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
                )
                st.success(f"Frozen: {paths.goal_path(gf.goal_id)}")

            with st.spinner("Computing SPECTER2 embedding..."):
                emb = asyncio.run(pull.embed_goal(st.session_state.draft_raw_goal, gf.goal_id))
                st.success(f"Embedding: {len(emb)} dims")

            for retriever in ("rrf", "bm25", "specter2"):
                with st.spinner(f"Pulling {retriever}..."):
                    cf = asyncio.run(pull.pull_and_save(
                        goal_id=gf.goal_id, retriever=retriever,
                        lexical_query=new_lex, goal_embedding=emb,
                        k=st.session_state.draft_top_k,
                    ))
                    st.success(f"{retriever}: {len(cf.papers)} papers → {paths.candidates_path(gf.goal_id, retriever)}")

            for k in ("draft_criteria", "draft_lexical", "draft_goal_id",
                      "draft_raw_goal", "draft_top_k"):
                st.session_state.pop(k, None)
            st.balloons()
