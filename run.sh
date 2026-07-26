#!/usr/bin/env bash
# Quick-start: run the SAT exam backend with SQLite (no Docker/PostgreSQL needed)
set -e

cd "$(dirname "$0")"

# 1. Create venv if not exists
if [ ! -d .venv ]; then
    echo ">>> Creating virtualenv..."
    python3 -m venv .venv
fi

# 2. Install deps (add aiosqlite for SQLite support)
source .venv/bin/activate
pip install -q aiosqlite

# 3. Set SQLite URL
export DATABASE_URL="sqlite+aiosqlite:///./sat_exam.db"

# 4. Create tables
echo ">>> Creating database tables..."
python3 -c "
import asyncio
from sqlalchemy import text
from app.database import engine, Base
from app.models import *  # noqa

async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Tables created.')
asyncio.run(init())
"

# 5. Seed skill vocabulary
echo ">>> Seeding skill vocabulary..."
python3 -c "
import asyncio, sys
sys.path.insert(0, '.')
from scripts.seed_skills import seed_skills
asyncio.run(seed_skills())
"

# 6. Create admin user
echo ">>> Creating admin user..."
python3 -c "
import asyncio
from app.database import AsyncSessionLocal
from app.models import User
from app.auth.utils import hash_password

async def create_admin():
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.email == 'admin@sat-exam.com'))
        if result.scalar_one_or_none():
            print('Admin already exists.')
            return
        admin = User(
            email='admin@sat-exam.com',
            password_hash=hash_password('admin123'),
            role='admin',
            display_name='Admin',
        )
        db.add(admin)
        await db.commit()
        print('Admin created: admin@sat-exam.com / admin123')

asyncio.run(create_admin())
"

# 7. Start server
echo ""
echo "============================================"
echo "  SAT Exam API running at http://localhost:8000"
echo "  API docs: http://localhost:8000/api/docs"
echo "  Login: admin@sat-exam.com / admin123"
echo "============================================"
echo ""
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
