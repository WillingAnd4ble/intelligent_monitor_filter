"""Benchmark harness — Streamlit entrypoint.

Run: streamlit run testing/benchmark/app.py
"""

import os
from pathlib import Path

import streamlit as st

# Make benchmark/lib and ../backend importable
_HERE = Path(__file__).resolve().parent
import sys
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

# Load .env.benchmark if present
_env = _HERE.parent / ".env.benchmark"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


from benchmark.lib import paths


st.set_page_config(page_title="arXiv Benchmark Harness", layout="wide")

st.title("arXiv Filtering — Benchmark Harness")

st.markdown(
    """
This is the Phase 1 evaluation tool for the agent-based arXiv filtering thesis.

**Workflow:**
1. **Pull Candidates** — paste a goal, distill, freeze criteria, pull RRF/BM25/SPECTER2 top-30.
2. **Label** — one paper at a time; check criteria boxes; saved incrementally.
3. **Run Experiment** — pick a model + toggles, run the cascade, results saved.
4. **Charts** — render figures for thesis, export PNG + LaTeX block.

Data files live under `testing/data/`. Frozen goal files and the cache manifest
are committed; labels, results, and the LLM cache are gitignored.
"""
)

paths.ensure_subdirs()

with st.expander("Environment & DB check"):
    db_url = os.environ.get("BENCHMARK_DB_URL")
    if not db_url:
        st.error("BENCHMARK_DB_URL is not set. Copy testing/.env.benchmark.example to testing/.env.benchmark.")
    else:
        st.success("BENCHMARK_DB_URL is configured.")

    if not os.environ.get("OPENAI_API_KEY"):
        st.warning("OPENAI_API_KEY not set — gpt-4o-mini and gpt-5.4-nano runs will fail.")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.warning("ANTHROPIC_API_KEY not set — claude-haiku-4-5 runs will fail.")

    st.write(f"Data root: `{paths.data_root()}`")

st.info("Pick a page from the left sidebar to begin.")
