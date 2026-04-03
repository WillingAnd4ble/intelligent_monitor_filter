from pydantic import BaseModel, Field
from typing import List, Optional

class LoginRequest(BaseModel):
    email: str
    password: str

class StatusResponse(BaseModel):
    status: str = "ok"

class SettingsUpdateRequest(BaseModel):
    categories: Optional[List[str]] = None
    topics: Optional[List[str]] = None
    authors: Optional[List[str]] = None
    filtering_goal: Optional[str] = None
    content_interest: Optional[List[str]] = None
    library_explanation_level: Optional[str] = None
    notification_time: Optional[str] = None
    pdf_parser_mode: Optional[str] = None

class PaperResponse(BaseModel):
    user_paper_id: str
    paper_id: str
    title: str
    authors: List[str]
    abstract: str
    agent_score: Optional[float] = None
    agent_explanation: Optional[str] = None
    source_url: Optional[str] = None

class FeedStatsResponse(BaseModel):
    total_scraped_today: int = 0
    evaluated_by_agent: int = 0
    recommended_today: int = 0

class RejectRequest(BaseModel):
    comment: str = Field(..., description="Required constraint explicitly feeding the Memory agent")

class ExplanationResponse(BaseModel):
    user_paper_id: str
    level: str
    explanation: str

class PipelineStatusResponse(BaseModel):
    task_id: str
    state: str
    progress: Optional[str] = None
