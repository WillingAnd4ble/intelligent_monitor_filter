from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.db.database import get_db
from app.db.models import User, UserPaper, Paper, PaperExplanation, UserSettings
from app.schemas.api_schemas import PaperResponse, ExplanationResponse, StatusResponse
from app.api.deps import get_current_user
from app.core.config import settings
from app.agents.schemas import ExplainerOutput

router = APIRouter()

@router.get("/", response_model=List[PaperResponse])
async def get_library(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Fetches specifically tracked local limits explicitly isolated bypassing regular feeds."""
    result = await session.execute(
        select(UserPaper, Paper)
        .join(Paper, UserPaper.paper_id == Paper.id)
        .where(UserPaper.user_id == user.id)
        .where(UserPaper.status == "accepted")
        .order_by(UserPaper.created_at.desc())
    )
    
    rows = result.all()
    
    response = []
    for user_paper, paper in rows:
        response.append(
            PaperResponse(
                user_paper_id=str(user_paper.id),
                paper_id=paper.id,
                title=paper.title,
                authors=paper.authors,
                abstract=paper.abstract,
                agent_score=user_paper.agent_score,
                agent_explanation=user_paper.agent_explanation,
                source_url=paper.source_url
            )
        )

    return response

@router.post("/{user_paper_id}/explain", response_model=ExplanationResponse)
async def explain_paper(
    user_paper_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Generates or returns cached explanation at user's library_explanation_level."""
    # Verify ownership
    result = await session.execute(
        select(UserPaper, Paper)
        .join(Paper, UserPaper.paper_id == Paper.id)
        .where(UserPaper.id == uuid.UUID(user_paper_id))
        .where(UserPaper.user_id == user.id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="UserPaper not found.")
    user_paper, paper = row

    # Get user's preferred explanation level
    settings_result = await session.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    user_settings = settings_result.scalars().first()
    level = user_settings.library_explanation_level if user_settings else "professional"

    # Check cache
    cached = await session.execute(
        select(PaperExplanation)
        .where(PaperExplanation.user_paper_id == uuid.UUID(user_paper_id))
        .where(PaperExplanation.level == level)
    )
    existing = cached.scalars().first()
    if existing:
        return ExplanationResponse(
            user_paper_id=user_paper_id,
            level=existing.level,
            explanation=existing.explanation
        )

    # Generate via LLM
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7, api_key=settings.OPENAI_API_KEY)
    structured = llm.with_structured_output(ExplainerOutput)

    level_instructions = {
        "professional": "Write for an expert researcher. Use precise technical language.",
        "student": "Write for a university student. Explain key concepts clearly.",
        "kid": "Write for a curious 12-year-old. Use simple language and analogies."
    }

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "Explain why this paper is relevant to the user. "
            "{level_instruction} "
            "Keep it to 3-4 sentences maximum."
        )),
        ("human", "Title: {title}\n\nAbstract: {abstract}")
    ])

    chain = prompt | structured
    result = chain.invoke({
        "level_instruction": level_instructions.get(level, level_instructions["professional"]),
        "title": paper.title,
        "abstract": paper.abstract
    })

    # Cache the result
    new_explanation = PaperExplanation(
        user_paper_id=uuid.UUID(user_paper_id),
        level=level,
        explanation=result.explanation
    )
    session.add(new_explanation)
    await session.commit()

    return ExplanationResponse(
        user_paper_id=user_paper_id,
        level=level,
        explanation=result.explanation
    )

@router.delete("/{user_paper_id}", response_model=StatusResponse)
async def remove_from_library(
    user_paper_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Removes a UserPaper record from the user's library."""
    result = await session.execute(
        select(UserPaper)
        .where(UserPaper.id == uuid.UUID(user_paper_id))
        .where(UserPaper.user_id == user.id)
    )
    user_paper = result.scalars().first()
    if not user_paper:
        raise HTTPException(status_code=404, detail="UserPaper not found.")

    await session.delete(user_paper)
    await session.commit()
    return StatusResponse(status="deleted")
