from pydantic import BaseModel, Field
from typing import TypedDict, List, Optional, Literal

class AgentState(TypedDict):
    """State for Phase 1 graph: evaluator + critique per paper."""
    user_id: str
    distilled_criteria: List[str]
    feedback_memory: str

    # Paper data
    current_paper_id: str
    raw_abstract: str
    pdf_url: Optional[str]

    # Agent outputs
    evaluator_decision: Literal["accept", "borderline", "reject"]
    evaluator_score: float
    evaluator_reasonbook: str
    critique_decision: bool
    critique_reasonbook: Optional[str]


# --- Phase 1: Evaluator ---

class EvaluatorOutput(BaseModel):
    decision: Literal["accept", "borderline", "reject"]
    score: float = Field(description="Relevance score from 1.0 to 10.0")
    reasonbook: str = Field(description="Step-by-step reasoning trace (internal, not shown to user)")


# --- Phase 1: Critique ---

class CritiqueOutput(BaseModel):
    decision: bool = Field(description="True = accept, False = reject")
    reasonbook: str


# --- Phase 2: Deep Reader ---

class DeepReaderOutput(BaseModel):
    decision: Literal["accept", "reject"]
    score: float = Field(description="Final relevance score from 1.0 to 10.0 based on full text")
    explanation: str = Field(description="2-3 sentence explanation of why this paper is relevant (shown to user in feed)")


# --- Memory Summarizer ---

class MemoryOutput(BaseModel):
    summarized_feedback: str = Field(description="A consolidated paragraph capturing what the user implicitly dislikes.")
