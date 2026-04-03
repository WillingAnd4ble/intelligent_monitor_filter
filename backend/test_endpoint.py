import asyncio
import urllib.request
import json
import sys
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import User, UserSettings

async def setup_db():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email=="test20@test.com"))
        user = result.scalars().first()
        if user:
            res_s = await session.execute(select(UserSettings).where(UserSettings.user_id==user.id))
            st = res_s.scalars().first()
            if st:
                st.distilled_criteria = ["Must map directly to distributed worker abstractions", "Focus on Agent architectures"]
                st.filtering_goal = "Agent Orchestration"
            await session.commit()
            return user.id
    return None

try:
    asyncio.run(setup_db())
except Exception as e:
    print("DB Setup err", e)
    sys.exit(1)

req = urllib.request.Request("http://127.0.0.1:8000/auth/login", data=json.dumps({"email":"test20@test.com","password":"test"}).encode(), headers={'Content-Type': 'application/json'}, method='POST')
access_token = None
try:
    with urllib.request.urlopen(req) as f:
        # Passlib fix allowed login so 200 OK should pass here perfectly
        headers = f.info().get_all('Set-Cookie')
        for h in headers:
            if "access_token=" in h:
                access_token = h.split(';')[0]
except Exception as e:
    print("Login err:", getattr(e, 'read', lambda: str(e))())

if access_token:
    req2 = urllib.request.Request("http://127.0.0.1:8000/api/v1/pipeline/trigger", data=b'', headers={'Cookie': access_token}, method='POST')
    try:
        with urllib.request.urlopen(req2) as f2:
            print("Trigger Response:", f2.status, f2.read().decode())
    except Exception as e:
        print("Trigger err:", getattr(e, 'read', lambda: str(e))())
