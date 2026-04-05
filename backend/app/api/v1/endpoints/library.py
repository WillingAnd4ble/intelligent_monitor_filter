from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from app.db.database import get_db
from app.db.models import User, UserPaper, Paper, PaperExplanation, UserSettings
from app.schemas.api_schemas import PaperResponse, ExplainResponse, StatusResponse
from app.api.deps import get_current_user

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


@router.post("/{user_paper_id}/explain", response_model=ExplainResponse)
async def explain_paper(
    user_paper_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Generates or returns cached deep explanation at user's library_explanation_level.

    If cached, returns immediately. Otherwise dispatches a Celery task and returns task_id
    for the frontend to poll via the /explain/status endpoint.
    """
    # Verify ownership + accepted status
    result = await session.execute(
        select(UserPaper, Paper)
        .join(Paper, UserPaper.paper_id == Paper.id)
        .where(UserPaper.id == uuid.UUID(user_paper_id))
        .where(UserPaper.user_id == user.id)
        .where(UserPaper.status == "accepted")
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Accepted paper not found in your library.")

    # Get user's preferred explanation level + content_interest
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
        return ExplainResponse(
            status="ready",
            level=existing.level,
            explanation=existing.explanation
        )

    # Dispatch Celery task
    from app.worker.celery_app import generate_deep_explanation
    task = generate_deep_explanation.delay(user_paper_id, str(user.id))

    return ExplainResponse(
        status="processing",
        task_id=task.id
    )


@router.get("/{user_paper_id}/explain/status", response_model=ExplainResponse)
async def explain_status(
    user_paper_id: str,
    task_id: str = Query(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Poll endpoint for async deep explanation generation."""
    # Get user's preferred level
    settings_result = await session.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    user_settings = settings_result.scalars().first()
    level = user_settings.library_explanation_level if user_settings else "professional"

    # Check if result appeared in cache since POST was made
    cached = await session.execute(
        select(PaperExplanation)
        .where(PaperExplanation.user_paper_id == uuid.UUID(user_paper_id))
        .where(PaperExplanation.level == level)
    )
    existing = cached.scalars().first()
    if existing:
        return ExplainResponse(
            status="ready",
            level=existing.level,
            explanation=existing.explanation
        )

    # Check Celery task state
    from app.worker.celery_app import celery_app
    result = celery_app.AsyncResult(task_id)

    if result.state in ("PENDING", "STARTED"):
        return ExplainResponse(status="processing")

    if result.state == "FAILURE":
        return ExplainResponse(status="error", detail="Explanation generation failed")

    if result.state == "SUCCESS":
        # Task finished — result should be in cache now, re-check
        cached2 = await session.execute(
            select(PaperExplanation)
            .where(PaperExplanation.user_paper_id == uuid.UUID(user_paper_id))
            .where(PaperExplanation.level == level)
        )
        existing2 = cached2.scalars().first()
        if existing2:
            return ExplainResponse(
                status="ready",
                level=existing2.level,
                explanation=existing2.explanation
            )
        return ExplainResponse(status="error", detail="Task completed but explanation not found")

    # Unknown state
    return ExplainResponse(status="processing")


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
