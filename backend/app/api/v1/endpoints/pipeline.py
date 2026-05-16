from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
from app.worker.celery_app import (
    run_full_pipeline, trigger_goal_distiller, celery_app,
)
from app.api.deps import get_current_user
from app.db.database import AsyncSessionLocal
from app.db.models import User, UserSettings
from app.schemas.api_schemas import PipelineStatusResponse

router = APIRouter()


@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_pipeline(
    user: User = Depends(get_current_user),
    date: str | None = Query(
        None,
        description="Optional YYYY-MM-DD — fetch papers from that UTC day instead of the default window.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    ),
):
    """Run the full pipeline now. Chain GoalDistiller first if criteria are missing."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserSettings).where(UserSettings.user_id == user.id)
        )
        user_settings = result.scalars().first()

    # Build the optional window from ?date=
    since_iso = until_iso = None
    if date is not None:
        try:
            day = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD")
        since_iso = day.isoformat()
        until_iso = (day + timedelta(days=1) - timedelta(seconds=1)).isoformat()

    if user_settings and user_settings.filtering_goal and not user_settings.distilled_criteria:
        from celery import chain
        task = chain(
            trigger_goal_distiller.si(str(user.id)),
            run_full_pipeline.si(str(user.id), since_iso, until_iso),
        ).apply_async()
        return {"task_id": task.id}

    task = run_full_pipeline.delay(str(user.id), since_iso, until_iso)
    return {"task_id": task.id}

@router.get("/{task_id}/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    task_id: str,
    user: User = Depends(get_current_user)
):
    """Returns current state of a Celery pipeline task."""
    result = celery_app.AsyncResult(task_id)
    progress = 0
    stage = ""
    if isinstance(result.info, dict):
        progress = result.info.get("progress", 0)
        stage = result.info.get("stage", "")
    elif result.state == "SUCCESS":
        progress = 100
        stage = "Complete"
    return PipelineStatusResponse(
        task_id=task_id,
        state=result.state,
        progress=progress,
        stage=stage,
    )

@router.post("/{task_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_pipeline(
    task_id: str,
    user: User = Depends(get_current_user)
):
    """Cancels a LangGraph Celery task by revoking it."""
    celery_app.control.revoke(task_id, terminate=True)
    return {"status": "cancelled"}
