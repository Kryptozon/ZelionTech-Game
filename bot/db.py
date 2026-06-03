import os
import glob
import asyncpg
from .config import settings

BASE = os.path.dirname(os.path.dirname(__file__))
INIT_SQL_PATH = os.path.join(BASE, "db", "init.sql")
MIGRATIONS_DIR = os.path.join(BASE, "db", "migrations")


async def create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(settings.DATABASE_URL, min_size=1, max_size=10)


async def init_db(pool: asyncpg.Pool):
    """Run base schema + ordered migrations (all idempotent), then sync links."""
    files = []
    if os.path.exists(INIT_SQL_PATH):
        files.append(INIT_SQL_PATH)
    if os.path.isdir(MIGRATIONS_DIR):
        files.extend(sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))))

    async with pool.acquire() as con:
        for path in files:
            with open(path, "r", encoding="utf-8") as f:
                await con.execute(f.read())
    await _seed_links(pool)


async def _seed_links(pool: asyncpg.Pool):
    async with pool.acquire() as con:
        for platform, url in settings.LINKS.items():
            if url:
                await con.execute(
                    "UPDATE missions SET url=$1 WHERE platform=$2 AND category='social'",
                    url, platform,
                )
