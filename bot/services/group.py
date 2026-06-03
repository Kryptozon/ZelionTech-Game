"""Phase 2: group activity rewards (messages + reactions) with caps & anti-flood."""
from ..config import settings
from . import economy


async def _scored_today(pool, user_id, kind) -> int:
    async with pool.acquire() as con:
        return await con.fetchval(
            "SELECT count(*) FROM group_activity WHERE user_id=$1 AND kind=$2 "
            "AND scored=true AND created_at > now() - interval '1 day'",
            user_id, kind,
        )


async def reward_message(pool, redis, user_id, chat_id, message_id, text) -> bool:
    """Returns True if points were awarded. Applies quality filter, anti-flood, daily cap."""
    if not text or len(text.strip()) < settings.GROUP_MSG_MIN_LEN or text.startswith("/"):
        return False
    # Anti-flood: max 1 scored message per 60s.
    if not await redis.set(f"gflood:{user_id}", "1", nx=True, ex=60):
        return False
    if await _scored_today(pool, user_id, "message") >= settings.GROUP_MSG_DAILY_CAP:
        return False
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO group_activity(user_id, chat_id, kind, scored) VALUES($1,$2,'message',true)",
            user_id, chat_id,
        )
    await economy.award_points(pool, user_id, settings.GROUP_MSG_XP, "group_msg",
                               f"gm:{chat_id}:{message_id}", redis=redis, surge=True)
    return True


async def reward_reaction(pool, redis, user_id, chat_id, message_id) -> bool:
    if await _scored_today(pool, user_id, "reaction") >= settings.GROUP_REACT_DAILY_CAP:
        return False
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO group_activity(user_id, chat_id, kind, scored) VALUES($1,$2,'reaction',true)",
            user_id, chat_id,
        )
    await economy.award_points(pool, user_id, settings.GROUP_REACT_XP, "group_react",
                               f"gr:{chat_id}:{message_id}:{user_id}", redis=redis, surge=True)
    return True
