from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from datetime import date, timedelta, datetime, timezone  # used by debug endpoint
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
        .order_by(
            UserPaper.is_top_pick.desc().nullslast(),  # Recommended block first
            UserPaper.agent_score.desc().nullslast(),  # then highest grade
            UserPaper.created_at.desc(),               # stable tie-breaker
        )
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
                source_url=paper.source_url,
                is_top_pick=user_paper.is_top_pick or False
            )
        )
        
    return response

@router.get("/stats", response_model=FeedStatsResponse)
async def get_feed_stats(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Outputs all-time statistics for this user."""
    # Total papers in the database
    scraped_result = await session.execute(select(func.count(Paper.id)))
    total_scraped = scraped_result.scalar() or 0

    # All papers evaluated by agent for this user (all UserPaper records ever)
    evaluated_result = await session.execute(
        select(func.count(UserPaper.id))
        .where(UserPaper.user_id == user.id)
    )
    evaluated = evaluated_result.scalar() or 0

    # Recommended = papers currently in feed
    recommended_result = await session.execute(
        select(func.count(UserPaper.id))
        .where(UserPaper.user_id == user.id)
        .where(UserPaper.status == "feed")
    )
    recommended = recommended_result.scalar() or 0

    return FeedStatsResponse(
        total_scraped_today=total_scraped,
        evaluated_by_agent=evaluated,
        recommended_today=recommended
    )


@router.get("/stats/debug", response_model=FeedStatsResponse)
async def get_feed_stats_debug(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    target_date: str | None = None,
    last_days: int | None = None,
):
    """Debug stats endpoint. Use ?target_date=2026-04-01 or ?last_days=7"""
    if target_date:
        d = date.fromisoformat(target_date)
        day_start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)
    elif last_days:
        day_start = datetime(
            *(date.today() - timedelta(days=last_days)).timetuple()[:3],
            tzinfo=timezone.utc,
        )
        day_end = datetime(date.today().year, date.today().month, date.today().day, tzinfo=timezone.utc) + timedelta(days=1)
    else:
        day_start = datetime(2026, 4, 1, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

    scraped_result = await session.execute(
        select(func.count(Paper.id))
        .where(Paper.published_at >= day_start)
        .where(Paper.published_at < day_end)
    )
    total_scraped = scraped_result.scalar() or 0

    evaluated_result = await session.execute(
        select(func.count(UserPaper.id))
        .where(UserPaper.user_id == user.id)
        .where(UserPaper.created_at >= day_start)
        .where(UserPaper.created_at < day_end)
    )
    evaluated = evaluated_result.scalar() or 0

    recommended_result = await session.execute(
        select(func.count(UserPaper.id))
        .where(UserPaper.user_id == user.id)
        .where(UserPaper.status == "feed")
        .where(UserPaper.created_at >= day_start)
        .where(UserPaper.created_at < day_end)
    )
    recommended = recommended_result.scalar() or 0

    return FeedStatsResponse(
        total_scraped_today=total_scraped,
        evaluated_by_agent=evaluated,
        recommended_today=recommended,
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
