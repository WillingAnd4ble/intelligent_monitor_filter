import asyncio
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import User, UserSettings

async def fix():
    async with AsyncSessionLocal() as s:
        res = await s.execute(select(User).where(User.email=="test@test.com"))
        u = res.scalars().first()
        if u:
            # find settings
            s_res = await s.execute(select(UserSettings).where(UserSettings.user_id==u.id))
            st = s_res.scalars().first()
            if st:
                st.distilled_criteria = ["Must heavily feature multi-agent frameworks", "Focuses tightly on Large language models instead of pure robotics"]
                st.filtering_goal = "AI Agent Architectures"
                await s.commit()
                print("Seeded criteria for test@test.com!")
            else:
                print("No settings found for test@test.com!")
        else:
            print("No such user found")

asyncio.run(fix())
