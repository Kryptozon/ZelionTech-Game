import asyncpg


async def top(pool: asyncpg.Pool, limit=10):
    # Leaderboard ranks by Ranking XP, not Game XP.
    async with pool.acquire() as con:
        return await con.fetch(
            "SELECT id, username, first_name, ranking_xp AS points FROM users "
            "WHERE status='active' ORDER BY ranking_xp DESC, id ASC LIMIT $1",
            limit,
        )


async def user_rank(pool: asyncpg.Pool, user_id: int):
    async with pool.acquire() as con:
        return await con.fetchval(
            "SELECT rank FROM (SELECT id, RANK() OVER (ORDER BY ranking_xp DESC, id ASC) AS rank "
            "FROM users WHERE status='active') t WHERE id=$1",
            user_id,
        )


async def names_for(pool: asyncpg.Pool, ids):
    """Map a list of user ids -> display names (preserves input order)."""
    if not ids:
        return {}
    async with pool.acquire() as con:
        rows = await con.fetch(
            "SELECT id, username, first_name FROM users WHERE id = ANY($1::bigint[])", ids
        )
    return {r["id"]: (r["username"] or r["first_name"] or str(r["id"])) for r in rows}


async def referral_top(pool: asyncpg.Pool, limit=10):
    async with pool.acquire() as con:
        return await con.fetch(
            "SELECT u.username, u.first_name, count(r.*) AS refs FROM referrals r "
            "JOIN users u ON u.id=r.referrer_id WHERE r.status='activated' "
            "GROUP BY u.id ORDER BY refs DESC LIMIT $1",
            limit,
        )
