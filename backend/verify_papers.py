import asyncio
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import User, UserPaper

async def check():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(User).where(User.email=="test20@test.com"))
        user = res.scalars().first()
        if user:
            # Check papers
            p_res = await session.execute(select(UserPaper).where(UserPaper.user_id==user.id))
            papers = p_res.scalars().all()
            print(f"User test20 has {len(papers)} processed papers in DB!")
            for p in papers:
                print(f"- {p.paper_id} | status: {p.status} | score: {p.agent_score}")
        else:
            print("No test user found.")

asyncio.run(check())
