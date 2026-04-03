import asyncio
from sqlalchemy import text
from app.db.database import AsyncSessionLocal

async def fix():
    async with AsyncSessionLocal() as s:
        try:
            await s.execute(text("ALTER TABLE papers ADD COLUMN search_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(abstract, ''))) STORED;"))
            await s.commit()
            print('DB TSVECTOR fixed successfully!')
        except Exception as e:
            print('DB TSVECTOR alter error:', e)

asyncio.run(fix())
