from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta

from app.db.database import get_db
from app.db.models import User, UserSettings, FeedbackMemory
from app.schemas.api_schemas import LoginRequest, StatusResponse
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.config import settings

router = APIRouter()


@router.post("/register", response_model=StatusResponse)
async def register(response: Response, user_in: LoginRequest, session: AsyncSession = Depends(get_db)):
    """Registers users configuring base dependency variables dynamically returning pure DOM HttpOnly structures."""
    result = await session.execute(select(User).where(User.email == user_in.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Constraints violated: email currently utilized.")
    
    new_user = User(
        email=user_in.email,
        password_hash=get_password_hash(user_in.password)
    )
    session.add(new_user)
    # Yield native UUID for mapping references
    await session.flush() 
    
    # Init empty settings tracking natively assigning parameters gracefully
    blank_settings = UserSettings(user_id=new_user.id)
    blank_memory = FeedbackMemory(user_id=new_user.id)
    session.add(blank_settings)
    session.add(blank_memory)
    await session.commit()
    
    # Execute native Auth Flow payload limits natively skipping UI manipulation vulnerabilities 
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(new_user.id, expires_delta=access_token_expires)
    
    # Assign HttpOnly DOM boundaries cleanly bypassing LocalStorage targets 
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=False # Use True securely mapping HTTPS Prod natively
    )
    return {"status": "ok"}
@router.post("/login", response_model=StatusResponse)
async def login(response: Response, user_in: LoginRequest, session: AsyncSession = Depends(get_db)):
    """Validates parameters pushing Response Cookies structurally avoiding XSS mapping leaks!"""
    result = await session.execute(select(User).where(User.email == user_in.email))
    user = result.scalars().first()
    
    if not user or not verify_password(user_in.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Authentication failed.")
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(user.id, expires_delta=access_token_expires)
    
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=False
    )
    return {"status": "ok"}

@router.post("/logout", response_model=StatusResponse)
async def logout(response: Response):
    """Pulls standard delete bounds neutralizing session state globally."""
    response.delete_cookie("access_token")
    return {"status": "ok"}
