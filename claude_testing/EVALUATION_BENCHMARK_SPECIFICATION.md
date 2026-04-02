# Thesis Evaluation & Benchmarking Specification
**Project:** Agent-based Information System for Personalized arXiv Publication Monitoring

For an undergraduate thesis incorporating generative logic, quantitative viability is completely mandatory. This specifies a standalone Python utility natively evaluating your agent configurations independent of your production codebase.

---

## 1. Benchmarking Tool Architecture (`benchmark_pipeline.py`)
- **Framework:** `Streamlit`. Streamlit is selected over Gradio specifically for its native capability to plot `pandas` DataFrames, precision/recall curves, and token cost metric charts gracefully.
- **Execution Mode:** Eliminates network loops and OCR infrastructure entirely. Ingests a pre-downloaded, static local `.json` dataset.
- **Static Context:** The local `.json` file must contain *pre-extracted text blocks*, not raw PDFs. Forcing the benchmark to utilize Modal.com's OCR live makes testing non-deterministic and exposes the metrics to external transit latencies.

## 2. Ground Truth Dataset & Labeling Protocol
You must manually construct a local subset (`evaluation_dataset.json`) of ~100 papers. To ensure the evaluation is scientifically defensible, the ground truth labeling must map identically to your agent logic logic:
- **Labeling Protocol:** Execute the `GoalDistiller` on your baseline User test intent to acquire a rigid array of criteria (e.g., `["Requires LangGraph usage", "Strictly code implementations"]`). As the human researcher, you will read the 100 benchmark papers and assign `ground_truth_score: 1` ONLY if the paper truly satisfies *those exact distilled criteria*. All others receive `0`.
- **Distribution Profile:** ~30 Highly Relevant (`1`), ~30 Borderline edge-cases (`0`), ~40 Hard Theoretical Traps/Noise (`0`).

## 3. Evaluated Computational Metrics
1. **Precision:** `True Positives / (True Positives + False Positives)`. High precision validates that the AI effectively filters out all distracting noise.
2. **Recall:** `True Positives / (True Positives + False Negatives)`. Did the strict LangGraph Evaluator accidentally destroy relevant items?
3. **F1-Score:** The harmonic system balance metric correlating the two.
4. **Per-Stage Latency:** Logged stopwatch metrics plotting milliseconds.
5. **API Token Expenditure:** Cumulative summarization mapping strictly to actual financial API expenditures.

## 4. Required Thesis Validation Experiments

### Experiment 1: Pre-Filter Retrieval Efficacy (Lexical vs Semantic)
- **Goal:** This experiment measures strictly pre-filter *recall* operating solely *before* any LangGraph agents act. It compares standalone `BM25/tsvector` vs `tsvector + SPECTER2 RRF`.
- **Metric:** Calculate the pre-agent Recall delta proving semantic embeddings successfully target deep mathematical concept papers lacking exact keyword matches.

### Experiment 2: The Multi-Agent Efficacy (Evaluator alone vs. Evaluator + Critique)
- **Goal:** Strip out the `Critique` node and run the benchmark. Then, initialize a rigid `feedback_memory` attacking the "Hard Traps" and execute the `Critique` node sequentially.
- **Metric:** Calculate the overall Precision shift proving personalized user-feedback significantly slashes standard LLM-hallucinated False Positives across the funnel.

### Experiment 3: Longitudinal Feedback Shift (FR14 Simulation)
- **Goal:** Formally test the time-series effectiveness of the `MemorySummarizer`. Re-run the dataset identically. Run 1: Blank memory. Run 2: Fire off 5 simulated user rejections into the summarizer and rerun pipeline discovery.
- **Metric:** Track the exact percentage shift in recommendation output, providing definitive proof the system natively "learns and avoids" iteratively.

### Experiment 4: Context Size Economic Decay
- **Goal:** Configure the agent processing parameter utilizing solely short `raw_abstracts` against processing deeply utilizing the ~8000 token `SectionClassifier` OCR chunks.
- **Metric:** Financial log ($) matched vertically against the resulting F1 Score. The output is a curve establishing the true "Cost-to-Value Plateau".
