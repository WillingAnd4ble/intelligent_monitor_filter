import uuid
import jwt
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import User
from app.core.config import settings

async def get_current_user(
    session: AsyncSession = Depends(get_db),
    access_token: str | None = Cookie(None)
) -> User:
    """Security Exception enforcing strictly HttpOnly Cookie extraction avoiding localStorage vulnerabilities."""
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization Cookie"
        )
    
    try:
        payload = jwt.decode(
            access_token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token architecture.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credentials validation failed.")
    
    # Query Database mapping directly 
    result = await session.execute(select(User).where(User.id == uuid.UUID(user_id_str)))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User record not tracked.")
    return user
