from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import User, UserSettings
from app.schemas.api_schemas import SettingsUpdateRequest
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/", response_model=SettingsUpdateRequest)
async def fetch_user_settings(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Fetches custom profile parameters mapping purely off valid Context Cookie payloads."""
    result = await session.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    settings_obj = result.scalars().first()
    
    if not settings_obj:
        raise HTTPException(status_code=404, detail="Settings parameters are currently un-tracked.")
    return settings_obj

@router.put("/", response_model=SettingsUpdateRequest)
async def update_user_settings(
    settings_in: SettingsUpdateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Validates configuration properties injecting them natively securely avoiding malicious overwrite structures."""
    result = await session.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    settings_obj = result.scalars().first()
    
    if not settings_obj:
        raise HTTPException(status_code=404, detail="Settings missing.")
    
    # Executing dynamic exclude updates patching directly utilizing validated schema logic natively!
    update_data = settings_in.model_dump(exclude_unset=True)

    # Track whether filtering_goal changed to trigger distiller
    goal_changed = "filtering_goal" in update_data and update_data["filtering_goal"] != settings_obj.filtering_goal

    for key, value in update_data.items():
        setattr(settings_obj, key, value)

    await session.commit()
    await session.refresh(settings_obj)

    # Trigger GoalDistiller when filtering_goal is updated
    if goal_changed:
        from app.worker.celery_app import trigger_goal_distiller
        trigger_goal_distiller.delay(str(user.id))

    return settings_obj
