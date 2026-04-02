# Agent Architecture Specification
**Project:** Agent-based Information System for Personalized arXiv Publication Monitoring

This document details the LangGraph agent state, the precise node Input/Output contracts defined via Pydantic, and the core LLM prompts guiding the inference engine. These constructs are critical for ensuring the AI evaluates papers deterministically and objectively.

---

## 1. LangGraph State Schema
The pipeline relies on a rolling state dictionary passed across each node, allowing dynamic routing and history logging.
```python
from pydantic import BaseModel, Field
from typing import TypedDict, List, Optional, Literal

class AgentState(TypedDict):
    user_id: str
    user_intent: str # Raw goal from settings
    distilled_criteria: List[str] # Input to pipeline
    content_interest: List[str] 
    feedback_memory: str 
    
    # Paper Pipeline State
    current_paper_id: str
    raw_abstract: str
    extracted_pdf_text: Optional[str] 
    sectioned_text: Optional[str] 
    
    # Decisions & Logs
    evaluator_decision: Literal["accept", "borderline", "reject"]
    evaluator_reasonbook: str 
    critique_decision: bool
    critique_reasonbook: Optional[str]
    final_explanation: Optional[str]
    agent_score: Optional[float]
```

---

## 2. Background Standalone Agents
These agents run strictly asynchronously upon UI events, and are NOT present inside the daily per-paper loop pipeline.

### 2.1 `GoalDistiller`
**Purpose:** Breaks the unstructured NLP user goal into a strict list of boolean criteria.
**Trigger:** Runs ONLY asynchronously when a user updates their goals via `/api/v1/settings`.
**System Prompt:**
> "Convert the user's natural language research goal into a strict, logical list of 3-5 boolean inclusion and exclusion criteria."

### 2.2 `MemorySummarizer` 
**Trigger:** Runs asynchronously when a user rejects a paper. Merges the rejection comment into the global `feedback_memory`.
**Output Contract:**
```python
class MemoryOutput(BaseModel):
    summarized_feedback: str = Field(description="A consolidated paragraph capturing what the user implicitly dislikes.")
```
**System Prompt:**
> "You are an AI alignment engineer. Extract the core critique from the user's latest rejection comment: '{user_comment}'. Merge this seamlessly into the user's existing historical avoidance profile: '{feedback_memory}'. Output a single, consolidated paragraph dictating precisely what topics, methodologies, or scopes the user strictly avoids."

---

## 3. Daily Pipeline LangGraph Nodes & Conditional Routing

### 3.1 Node: `Evaluator`
**Purpose:** Evaluates the `sectioned_text` (or `raw_abstract` during the fast funnel lookup) against the user's precise goals.
**Output Contract:** 
```python
class EvaluatorOutput(BaseModel):
    decision: Literal["accept", "borderline", "reject"]
    reasonbook: str = Field(description="Step-by-step reasoning trace")
```

### 3.2 Node: `PDFExtractor` & `SectionClassifier`
**Purpose:** Once accepted by early evaluations, the heavy PDF parser runs (via `pypdfium` locally, or `Marker`/`MinerU` hosted on `Modal.com` GPU compute) to extract text.
**Output Contract:**
```python
class SectionOutput(BaseModel):
    sectioned_text: str = Field(description="Strict slice containing solely interested contexts")
```

### 3.3 Node: `Critique`
**Purpose:** Double-checks the Evaluator's borderline trace explicitly against historical user feedback.
**Input:** `evaluator_reasonbook`, `feedback_memory`
**Output Contract:** 
```python
class CritiqueOutput(BaseModel):
    decision: bool = Field(description="Final binary truth resolution based on feedback_memory.")
    reasonbook: str
```
**System Prompt:**
> "The previous AI was unsure about this paper for the following reasons: {evaluator_reasonbook}. However, the user historically dislikes these traits: {feedback_memory}. If the paper prominently features what the user dislikes, resolve the uncertainty as FALSE. Otherwise TRUE."

### 3.4 Node: `Explainer`
**Purpose:** Generates the natural language summary for the UI.
**Input:** Final approved text, `user_intent`
**Output Contract:** 
```python
class ExplainerOutput(BaseModel):
    explanation: str = Field(description="Concise 3-sentence justification highlighting goal overlap")
```

### 3.5 Node: `Ranker`
**Purpose:** Quantitatively scores the paper's relevancy intensity.
**Input:** `sectioned_text`, `distilled_criteria`
**Output Contract:**
```python
class RankerOutput(BaseModel):
    score: float = Field(description="Score from 0.0 to 10.0 tracking qualitative relevance intensity")
```

### 3.6 Formal Routing Logic (LangGraph Conditional Edges)
- **Evaluator Edge**:
  - `reject` -> **End**. Skip paper completely.
  - `borderline` -> Route specifically to **Critique** node for validation against memory.
  - `accept` -> Route directly to **PDFExtractor**. Token save bypassing Critique logic entirely.
- **Critique Edge**:
  - `False` -> **End**. Skip paper.
  - `True` -> Route to **PDFExtractor** and then sequentially into **Explainer** and **Ranker**.
