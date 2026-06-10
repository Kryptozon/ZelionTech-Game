"""Redis ZSET leaderboards (all-time + weekly) and weekly reset."""
from datetime import datetime, timezone

ALL = "lb:all"
WEEK = "lb:week"


async def ensure_seed(pool, redis):
    """On first boot, seed the all-time ZSET from Ranking XP (leaderboard balance)."""
    if await redis.exists(ALL):
        return
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT id, ranking_xp FROM users WHERE ranking_xp > 0")
    if rows:
        mapping = {str(r["id"]): r["ranking_xp"] for r in rows}
        await redis.zadd(ALL, mapping)


async def top(redis, key, n=10):
    data = await redis.zrevrange(key, 0, n - 1, withscores=True)
    return [(int(member), int(score)) for member, score in data]


async def rank(redis, key, user_id):
    r = await redis.zrevrank(key, str(user_id))
    return (r + 1) if r is not None else None


async def score(redis, key, user_id):
    s = await redis.zscore(key, str(user_id))
    return int(s) if s is not None else 0


def current_week_key():
    iso = datetime.now(timezone.utc).isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


async def snapshot_and_reset_week(pool, redis):
    """Persist the weekly board to history, then clear it. Returns top-3 [(uid, score)]."""
    period = current_week_key()
    data = await redis.zrevrange(WEEK, 0, -1, withscores=True)
    async with pool.acquire() as con:
        for i, (member, sc) in enumerate(data):
            await con.execute(
                "INSERT INTO leaderboard_snapshots(user_id, board, period_key, score, rank) "
                "VALUES($1,'weekly',$2,$3,$4) ON CONFLICT (user_id, board, period_key) DO NOTHING",
                int(member), period, int(sc), i + 1,
            )
        await con.execute(
            "INSERT INTO events(kind, detail) VALUES('weekly_reset', $1)",
            f'{{"period": "{period}", "entries": {len(data)}}}',
        )
    await redis.delete(WEEK)
    return [(int(m), int(s)) for m, s in data[:3]]
