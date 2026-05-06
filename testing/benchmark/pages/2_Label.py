"""Page 2 — Label: paper-at-a-time UI with frozen criteria checkboxes."""

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

_BENCH = Path(__file__).resolve().parents[1]
if str(_BENCH.parent) not in sys.path:
    sys.path.insert(0, str(_BENCH.parent))

from benchmark.lib import paths
from benchmark.lib.schemas import GoalFile, CandidatesFile, LabelsFile, PaperLabel


st.title("2 — Label")


def list_goal_ids() -> list[str]:
    p = paths.data_root() / "goals"
    if not p.exists():
        return []
    return sorted([f.stem for f in p.glob("*.json")])


def load_labels(goal_id: str) -> LabelsFile:
    lp = paths.labels_path(goal_id)
    if lp.exists():
        return LabelsFile.model_validate_json(lp.read_text(encoding="utf-8"))
    return LabelsFile(goal_id=goal_id, labeler="user", labels={})


def save_labels(lf: LabelsFile) -> None:
    paths.ensure_subdirs()
    paths.labels_path(lf.goal_id).write_text(lf.model_dump_json(indent=2), encoding="utf-8")


goal_ids = list_goal_ids()
if not goal_ids:
    st.info("No frozen goals yet. Go to Page 1 to create one.")
    st.stop()

goal_id = st.selectbox("Goal", goal_ids)
gf = GoalFile.model_validate_json(paths.goal_path(goal_id).read_text(encoding="utf-8"))
cp_path = paths.candidates_path(goal_id, "rrf")
if not cp_path.exists():
    st.error(f"Missing {cp_path}. Pull RRF candidates on Page 1.")
    st.stop()
cf = CandidatesFile.model_validate_json(cp_path.read_text(encoding="utf-8"))
lf = load_labels(goal_id)

st.success(
    f"Labels auto-save to `{paths.labels_path(goal_id)}` after every Save & Next. "
    "Close the tab anytime — your progress is preserved."
)

st.session_state.setdefault(f"session_start_{goal_id}", time.time())
elapsed = int(time.time() - st.session_state[f"session_start_{goal_id}"])
mm, ss = divmod(elapsed, 60)
st.caption(f"Session: {mm:02d}:{ss:02d}")

total = len(cf.papers)
done = len(lf.labels)
borderline = sum(1 for v in lf.labels.values() if v.borderline)
st.progress(done / max(total, 1), text=f"{done}/{total} labeled")
if done > 0 and borderline / done > 0.30:
    st.warning(f"Borderline > 30% ({borderline}/{done}). Consider re-reading criteria or adding one to disambiguate.")
if done > 0 and done % 20 == 0:
    st.info(f"You've labeled {done}. Consider a short break before continuing — labeling fatigue introduces noise.")

unlabeled = [p for p in cf.papers if p.paper_id not in lf.labels]
if not unlabeled:
    st.success("All papers labeled!")
    summary = lf.summary()
    st.write(summary.model_dump())
    st.stop()

idx = st.number_input("Paper index", 0, len(unlabeled) - 1, 0)
paper = unlabeled[idx]

st.subheader(paper.title)
st.caption(", ".join(paper.authors[:5]) + ("..." if len(paper.authors) > 5 else ""))
st.write(paper.abstract)
if paper.pdf_url:
    st.markdown(f"[Open PDF]({paper.pdf_url})")
st.markdown(f"[Open on arXiv](https://arxiv.org/abs/{paper.paper_id})")

st.divider()
st.markdown("**Tick which criteria this paper satisfies:**")
satisfied: list[str] = []
for c in gf.distilled_criteria:
    if st.checkbox(c.text, key=f"crit_{paper.paper_id}_{c.id}"):
        satisfied.append(c.id)

borderline_flag = st.checkbox("Borderline — exclude from precision", key=f"bord_{paper.paper_id}")
notes = st.text_area("Notes (optional)", key=f"notes_{paper.paper_id}")

if st.button("Save & Next"):
    threshold = gf.scoring_rule.threshold
    score = 1 if (len(satisfied) >= threshold and not borderline_flag) else 0
    lf.labels[paper.paper_id] = PaperLabel(
        criteria_satisfied=satisfied,
        ground_truth_score=score,
        borderline=borderline_flag,
        notes=notes or None,
        labeled_at=datetime.now(timezone.utc),
    )
    save_labels(lf)
    st.rerun()

with st.expander("Danger zone — discard labels for this goal"):
    st.caption(
        "Use this if you realize the goal was vague or wrong and want to abandon "
        "the labeled set. The goal file itself stays frozen — only the labels JSON "
        "is removed."
    )
    confirm = st.text_input(
        f"Type the goal_id to confirm deletion ({goal_id})",
        key=f"confirm_delete_{goal_id}",
    )
    if st.button("Delete labels file", type="primary"):
        if confirm == goal_id:
            lp = paths.labels_path(goal_id)
            if lp.exists():
                lp.unlink()
                st.success(f"Deleted {lp}. Goal file preserved.")
                st.rerun()
            else:
                st.info("No labels file to delete.")
        else:
            st.error("goal_id did not match — nothing deleted.")
