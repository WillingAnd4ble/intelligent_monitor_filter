# Ground Truth Dataset Construction Guide

This document explains step-by-step how to build `evaluation_dataset.json` — the 100-paper labeled dataset your benchmarks run against.

---

## Why You Need This

Your benchmark experiments compare agent decisions against **human labels**. Without a ground-truth dataset, there is no way to compute precision, recall, or F1. This dataset is the single most important artifact for your thesis evaluation chapter.

---

## Step 1: Define Your Test Persona

Pick ONE specific filtering goal that represents a realistic user. This will be your fixed test scenario across all experiments.

**Example persona:**
- Categories: `["cs.AI", "cs.MA"]`
- Topics: `["multi-agent systems", "LLM agents", "agent coordination"]`
- Content interest: `["methodology", "experiments"]`
- Filtering goal: `"Find papers on multi-agent systems that use Large Language Models for coordination and communication between agents"`

## Step 2: Run the Goal Distiller

Generate the exact criteria your agents will use. Run this in a Python shell from the `backend/` directory:

```python
import asyncio
from app.agents.distiller import run_goal_distiller

criteria = run_goal_distiller(
    categories=["cs.AI", "cs.MA"],
    topics=["multi-agent systems", "LLM agents"],
    content_interest=["methodology", "experiments"],
    filtering_goal="Find papers on multi-agent systems that use Large Language Models for coordination and communication between agents"
)

for c in criteria:
    print(f"  - {c}")
```

**Save these criteria.** They go in `evaluation_dataset.json` under `criteria_used_for_labeling` and you'll paste them into the Streamlit sidebar when running benchmarks.

## Step 3: Collect 100 Papers

Use the ArXiv scraper to fetch candidate papers:

```python
from app.worker.arxiv_scraper import fetch_arxiv_papers

papers = fetch_arxiv_papers("cat:cs.AI+OR+cat:cs.MA", max_results=200)
print(f"Fetched {len(papers)} papers")
```

Alternatively, scrape from the ArXiv website or use the `year_scrape` tool.

You need ~100 papers from these 200. Select them to match this distribution:

| Category | Count | Description |
|----------|-------|-------------|
| **Clearly Relevant** | ~30 | Papers that obviously satisfy ALL your distilled criteria |
| **Borderline** | ~30 | Papers that touch the topic but miss 1-2 criteria (e.g., multi-agent but no LLMs, or LLMs but single-agent) |
| **Hard Traps / Noise** | ~40 | Papers that look related at a glance but are actually about different things (robotics swarms, NLP without agents, pure theory) |

**Why this distribution matters:** If you only pick obvious papers, your precision will be artificially high. The borderline and hard-trap papers test whether the agent makes nuanced decisions.

## Step 4: Label Each Paper

For each of the 100 papers, read the abstract (and full text if available) and assign a binary label:

- `ground_truth: 1` — Paper satisfies ALL the distilled criteria from Step 2
- `ground_truth: 0` — Paper fails one or more criteria

**Labeling rules:**
- Be strict. If the paper is borderline, label it `0`. The criteria say "must" — borderline means it doesn't fully satisfy.
- If the paper mentions agents but means RL agents (not LLM agents), label `0`.
- If the paper has multi-agent LLM work but is purely theoretical with no experiments, and your criteria require experiments, label `0`.
- Tag each paper for later analysis: `"tags": ["borderline", "multi-agent-but-no-llm"]`

## Step 5: Get Full Text (Optional but Valuable)

For Experiment 4 (Context Size), you need the `full_text` field. Options:

1. **From PDF extraction:** If your MARKER pipeline works, extract text from arXiv PDFs
2. **From arXiv HTML:** Many recent papers have HTML versions at `https://arxiv.org/html/{paper_id}`
3. **Manual copy-paste:** Copy the text from the PDF for your 30 relevant papers at minimum
4. **Fallback:** If you only have abstracts, set `full_text` = abstract. Experiment 4 will still run but all context-size variants will produce the same results.

## Step 6: Build the JSON File

Create `evaluation_dataset.json` with this exact structure:

```json
{
  "criteria_used_for_labeling": [
    "Your criterion 1 from Step 2",
    "Your criterion 2",
    "..."
  ],
  "papers": [
    {
      "paper_id": "2404.12345",
      "title": "Paper Title Here",
      "abstract": "The paper abstract...",
      "full_text": "Full extracted text or same as abstract...",
      "ground_truth": 1,
      "tags": ["relevant", "multi-agent", "llm"]
    },
    {
      "paper_id": "2404.99999",
      "title": "Irrelevant Paper",
      "abstract": "...",
      "full_text": "...",
      "ground_truth": 0,
      "tags": ["hard_trap", "robotics"]
    }
  ]
}
```

## Step 7: Validate

Quick sanity check before running experiments:

```python
import json

with open("evaluation_dataset.json") as f:
    ds = json.load(f)

papers = ds["papers"]
relevant = sum(1 for p in papers if p["ground_truth"] == 1)
total = len(papers)

print(f"Total papers: {total}")
print(f"Relevant (1): {relevant}")
print(f"Irrelevant (0): {total - relevant}")
print(f"Ratio: {relevant/total:.0%} relevant")

# Check tag distribution
from collections import Counter
all_tags = [t for p in papers for t in p.get("tags", [])]
print(f"Tag distribution: {Counter(all_tags)}")

# Should see:
# Total papers: ~100
# Relevant: ~30  (25-35%)
# Tags should include: relevant, borderline, hard_trap
```

## Step 8: Run Benchmarks

```bash
# From the testing/ directory:

# Quick CLI run:
python benchmark/experiments.py --experiment 1 --dataset evaluation_dataset.json

# Full Streamlit dashboard:
streamlit run benchmark/benchmark_pipeline.py
```

---

## Common Mistakes to Avoid

1. **Labeling too generously.** If you label 60+ papers as relevant, your recall will be high but the benchmark won't detect false negatives. Keep relevant papers at ~30%.

2. **Not including hard traps.** If all irrelevant papers are obviously unrelated (e.g., biology papers in a CS dataset), the benchmark is too easy. Include papers that look related but aren't (e.g., "multi-agent robotics" for an "LLM agent" filter).

3. **Using different criteria for labeling vs benchmarking.** The criteria in `criteria_used_for_labeling` MUST match what you enter in the Streamlit sidebar. If they differ, your metrics are meaningless.

4. **Forgetting to save the criteria.** The specific criteria from the Goal Distiller are non-deterministic (small temperature variations). Run it once, save the output, and use those exact criteria everywhere.

---

## Recommended Tags

Use these tags to enable fine-grained analysis:

| Tag | Meaning |
|-----|---------|
| `relevant` | Satisfies all criteria (ground_truth=1) |
| `borderline` | Almost relevant but fails 1 criterion (ground_truth=0) |
| `hard_trap` | Looks related but isn't (ground_truth=0) |
| `noise` | Obviously unrelated (ground_truth=0) |
| `multi-agent` | Involves multiple agents |
| `single-agent` | Single agent only |
| `llm` | Uses Large Language Models |
| `rl-not-llm` | Uses RL but not LLMs |
| `robotics` | About physical robots |
| `theory-only` | No experiments |
| `has-code` | Includes code/implementation |
