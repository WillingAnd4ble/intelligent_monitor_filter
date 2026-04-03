from fastapi import APIRouter, Depends, status
from app.worker.celery_app import trigger_agent_discovery, celery_app
from app.api.deps import get_current_user
from app.db.models import User
from app.schemas.api_schemas import PipelineStatusResponse

router = APIRouter()

@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_pipeline(user: User = Depends(get_current_user)):
    """
    Hit by Vercel cron or manual UI button.
    Kicks off the heavy Discovery Celery Queue.
    """
    task = trigger_agent_discovery.delay(str(user.id))
    return {"task_id": task.id}

@router.get("/{task_id}/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    task_id: str,
    user: User = Depends(get_current_user)
):
    """Returns current state of a Celery pipeline task."""
    result = celery_app.AsyncResult(task_id)
    return PipelineStatusResponse(
        task_id=task_id,
        state=result.state,
        progress=str(result.info) if result.info else None
    )

@router.post("/{task_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_pipeline(
    task_id: str,
    user: User = Depends(get_current_user)
):
    """Cancels a LangGraph Celery task by revoking it."""
    celery_app.control.revoke(task_id, terminate=True)
    return {"status": "cancelled"}
