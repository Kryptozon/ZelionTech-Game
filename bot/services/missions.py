from datetime import datetime, timezone, timedelta
import asyncpg


async def list_social(pool: asyncpg.Pool):
    async with pool.acquire() as con:
        return await con.fetch(
            "SELECT * FROM missions WHERE category='social' AND is_active ORDER BY id"
        )


async def list_learn(pool: asyncpg.Pool):
    async with pool.acquire() as con:
        return await con.fetch(
            "SELECT * FROM missions WHERE category='learn' AND is_active ORDER BY id"
        )


async def get_mission(pool: asyncpg.Pool, mission_id: int):
    async with pool.acquire() as con:
        return await con.fetchrow("SELECT * FROM missions WHERE id=$1", mission_id)


async def social_mission_state(pool: asyncpg.Pool, user_id: int, mission_id: int):
    """Returns 'approved' | 'pending' | 'rejected' | 'none' for a social mission."""
    async with pool.acquire() as con:
        row = await con.fetchrow(
            "SELECT status FROM proof_submissions WHERE user_id=$1 AND mission_id=$2 "
            "ORDER BY created_at DESC LIMIT 1",
            user_id, mission_id,
        )
    return row["status"] if row else "none"


async def quiz_eligible(pool: asyncpg.Pool, user_id: int, mission_id: int):
    async with pool.acquire() as con:
        row = await con.fetchrow(
            "SELECT next_eligible_at FROM mission_completions WHERE user_id=$1 AND mission_id=$2 "
            "ORDER BY completed_at DESC LIMIT 1",
            user_id, mission_id,
        )
    if not row or not row["next_eligible_at"]:
        return True
    return datetime.now(timezone.utc) >= row["next_eligible_at"]


async def record_completion(pool: asyncpg.Pool, user_id: int, mission_id: int, cooldown_sec: int):
    nxt = datetime.now(timezone.utc) + timedelta(seconds=cooldown_sec)
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO mission_completions(user_id, mission_id, next_eligible_at) VALUES($1,$2,$3)",
            user_id, mission_id, nxt,
        )
