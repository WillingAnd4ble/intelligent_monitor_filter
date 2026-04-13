from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from app.worker.celery_app import trigger_agent_discovery, trigger_goal_distiller, celery_app
from app.api.deps import get_current_user
from app.db.database import AsyncSessionLocal
from app.db.models import User, UserSettings
from app.schemas.api_schemas import PipelineStatusResponse

router = APIRouter()

@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_pipeline(user: User = Depends(get_current_user)):
    """
    Hit by Vercel cron or manual UI button.
    Runs GoalDistiller first if distilled_criteria is missing, then kicks off Discovery.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserSettings).where(UserSettings.user_id == user.id)
        )
        user_settings = result.scalars().first()

    # Chain distiller → discovery on the Celery worker if criteria are missing
    if user_settings and user_settings.filtering_goal and not user_settings.distilled_criteria:
        from celery import chain
        task = chain(
            trigger_goal_distiller.si(str(user.id)),
            trigger_agent_discovery.si(str(user.id))
        ).apply_async()
        return {"task_id": task.id}

    task = trigger_agent_discovery.delay(str(user.id))
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
