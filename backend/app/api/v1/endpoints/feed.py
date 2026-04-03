from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from datetime import date, timedelta, datetime, timezone
import uuid

from app.db.database import get_db
from app.db.models import User, UserPaper, Paper
from app.schemas.api_schemas import PaperResponse, FeedStatsResponse, RejectRequest, StatusResponse
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/", response_model=List[PaperResponse])
async def get_feed(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Deep executing SQLAlchemy structural joins yielding cleanly packed Pydantic Responses for UI dashboards."""
    result = await session.execute(
        select(UserPaper, Paper)
        .join(Paper, UserPaper.paper_id == Paper.id)
        .where(UserPaper.user_id == user.id)
        .where(UserPaper.status == "feed")
        .order_by(UserPaper.created_at.desc())
        .limit(50)
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

@router.get("/stats", response_model=FeedStatsResponse)
async def get_feed_stats(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Outputs real statistics from DB for the current user's pipeline run."""
    # Yesterday's date range (pipeline scrapes previous day's papers)
    yesterday = date.today() - timedelta(days=1)
    day_start = datetime(yesterday.year, yesterday.month, yesterday.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    # Total papers scraped (ingested into Paper table from yesterday)
    scraped_result = await session.execute(
        select(func.count(Paper.id))
        .where(Paper.published_at >= day_start)
        .where(Paper.published_at < day_end)
    )
    total_scraped = scraped_result.scalar() or 0

    # Papers evaluated by agent for this user (all UserPaper records created today)
    today_start = datetime(date.today().year, date.today().month, date.today().day, tzinfo=timezone.utc)
    evaluated_result = await session.execute(
        select(func.count(UserPaper.id))
        .where(UserPaper.user_id == user.id)
        .where(UserPaper.created_at >= today_start)
    )
    evaluated = evaluated_result.scalar() or 0

    # Recommended = papers that passed the agent pipeline (status='feed', created today)
    recommended_result = await session.execute(
        select(func.count(UserPaper.id))
        .where(UserPaper.user_id == user.id)
        .where(UserPaper.status == "feed")
        .where(UserPaper.created_at >= today_start)
    )
    recommended = recommended_result.scalar() or 0

    return FeedStatsResponse(
        total_scraped_today=total_scraped,
        evaluated_by_agent=evaluated,
        recommended_today=recommended
    )

@router.post("/{user_paper_id}/accept", response_model=StatusResponse)
async def accept_paper(
    user_paper_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Moves a feed paper into the user's accepted library."""
    result = await session.execute(
        select(UserPaper)
        .where(UserPaper.id == uuid.UUID(user_paper_id))
        .where(UserPaper.user_id == user.id)
    )
    user_paper = result.scalars().first()
    if not user_paper:
        raise HTTPException(status_code=404, detail="UserPaper not found.")

    user_paper.status = "accepted"
    await session.commit()
    return StatusResponse(status="accepted")

@router.post("/{user_paper_id}/reject", response_model=StatusResponse)
async def reject_paper(
    user_paper_id: str,
    body: RejectRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Rejects a feed paper and stores user feedback comment for memory summarizer."""
    from app.worker.celery_app import run_memory_summarizer

    result = await session.execute(
        select(UserPaper)
        .where(UserPaper.id == uuid.UUID(user_paper_id))
        .where(UserPaper.user_id == user.id)
    )
    user_paper = result.scalars().first()
    if not user_paper:
        raise HTTPException(status_code=404, detail="UserPaper not found.")

    user_paper.status = "rejected"
    user_paper.user_comment = body.comment
    await session.commit()

    run_memory_summarizer.delay(str(user.id), body.comment)

    return StatusResponse(status="rejected")
