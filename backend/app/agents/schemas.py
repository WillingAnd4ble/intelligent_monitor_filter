from pydantic import BaseModel, Field
from typing import TypedDict, List, Optional, Literal

class AgentState(TypedDict):
    """The rolling data structure traversing identical context across the Node Graph."""
    user_id: str
    user_intent: str 
    distilled_criteria: List[str] 
    content_interest: List[str] 
    feedback_memory: str 
    
    # Paper Pipeline State tracking parameters
    current_paper_id: str
    raw_abstract: str
    pdf_url: Optional[str]
    extracted_pdf_text: Optional[str] 
    sectioned_text: Optional[str] 
    
    # Core Arbitrage Logs
    evaluator_decision: Literal["accept", "borderline", "reject"]
    evaluator_reasonbook: str 
    critique_decision: bool
    critique_reasonbook: Optional[str]
    final_explanation: Optional[str]
    agent_score: Optional[float]


# --- Explicit Node Definition Contracts ---

class EvaluatorOutput(BaseModel):
    decision: Literal["accept", "borderline", "reject"]
    reasonbook: str = Field(description="Step-by-step reasoning trace")

class SectionOutput(BaseModel):
    sectioned_text: str = Field(description="Strict slice containing solely interested contexts")

class CritiqueOutput(BaseModel):
    decision: bool = Field(description="Final binary truth resolution based on feedback_memory.")
    reasonbook: str

class ExplainerOutput(BaseModel):
    explanation: str = Field(description="Concise 3-sentence justification highlighting goal overlap")

class RankerOutput(BaseModel):
    score: float = Field(description="Score from 0.0 to 10.0 tracking qualitative relevance intensity")

class MemoryOutput(BaseModel):
    summarized_feedback: str = Field(description="A consolidated paragraph capturing what the user implicitly dislikes.")
