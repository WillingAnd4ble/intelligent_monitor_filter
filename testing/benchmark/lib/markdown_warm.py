"""Pre-warm Marker full-text extractions into a local markdown cache.

For each labeled paper in a goal, fetch its full text via the backend's
Modal-Marker pipeline once, store at testing/data/markdown/{paper_id}.md.
The runner reads from this cache before falling back to the prod DB or
the abstract.
"""

import asyncio
import sys
from pathlib import Path
from typing import Callable, List, Optional

# Make backend importable
_BACKEND = Path(__file__).resolve().parents[3] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.worker.modal_client import marker_extract_pdf  # type: ignore

from benchmark.lib import paths
from benchmark.lib.schemas import CandidatesFile, LabelsFile


def has_local_markdown(paper_id: str) -> bool:
    p = paths.markdown_path(paper_id)
    return p.exists() and p.stat().st_size > 0


def read_local_markdown(paper_id: str) -> Optional[str]:
    p = paths.markdown_path(paper_id)
    if not p.exists():
        return None
    txt = p.read_text(encoding="utf-8")
    return txt or None


def _write_markdown(paper_id: str, markdown: str) -> None:
    p = paths.markdown_path(paper_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(markdown, encoding="utf-8")


async def _extract(pdf_url: str) -> str:
    """Returns markdown or empty string on failure."""
    if not pdf_url:
        return ""
    try:
        return await marker_extract_pdf(pdf_url)
    except Exception:
        return ""


def prewarm_for_goal(goal_id: str,
                     progress: Optional[Callable[[str, int, int, str], None]] = None) -> dict:
    """Walk every labeled paper in the goal; warm any without local markdown.

    Returns counts: {warmed, already_cached, failed, missing_pdf}.
    The progress callback (paper_id, current, total, status) lets the UI
    report per-paper outcomes without us depending on Streamlit.
    """
    labels_p = paths.labels_path(goal_id)
    if not labels_p.exists():
        raise FileNotFoundError(f"No labels for {goal_id} — label some papers first.")
    cands_p = paths.candidates_path(goal_id, "rrf")
    if not cands_p.exists():
        raise FileNotFoundError(f"No RRF candidates for {goal_id}.")

    lf = LabelsFile.model_validate_json(labels_p.read_text(encoding="utf-8"))
    cf = CandidatesFile.model_validate_json(cands_p.read_text(encoding="utf-8"))
    by_id = {p.paper_id: p for p in cf.papers}

    targets: List[str] = list(lf.labels.keys())
    counts = {"warmed": 0, "already_cached": 0, "failed": 0, "missing_pdf": 0}

    for i, pid in enumerate(targets):
        paper = by_id.get(pid)
        if has_local_markdown(pid):
            counts["already_cached"] += 1
            if progress:
                progress(pid, i + 1, len(targets), "already_cached")
            continue
        if paper is None or not paper.pdf_url:
            counts["missing_pdf"] += 1
            if progress:
                progress(pid, i + 1, len(targets), "missing_pdf")
            continue
        if progress:
            progress(pid, i + 1, len(targets), "warming")
        md = asyncio.run(_extract(paper.pdf_url))
        if md:
            _write_markdown(pid, md)
            counts["warmed"] += 1
            if progress:
                progress(pid, i + 1, len(targets), "warmed")
        else:
            counts["failed"] += 1
            if progress:
                progress(pid, i + 1, len(targets), "failed")

    return counts
