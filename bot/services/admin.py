import asyncpg


async def stats(pool: asyncpg.Pool):
    async with pool.acquire() as con:
        total = await con.fetchval("SELECT count(*) FROM users")
        active_24h = await con.fetchval(
            "SELECT count(*) FROM users WHERE last_daily_claim > now() - interval '1 day'"
        )
        new_24h = await con.fetchval(
            "SELECT count(*) FROM users WHERE created_at > now() - interval '1 day'"
        )
        pending = await con.fetchval("SELECT count(*) FROM proof_submissions WHERE status='pending'")
        activated_refs = await con.fetchval(
            "SELECT count(*) FROM referrals WHERE status='activated'"
        )
        banned = await con.fetchval("SELECT count(*) FROM bans")
    return {
        "total": total, "active_24h": active_24h, "new_24h": new_24h,
        "pending_proofs": pending, "activated_refs": activated_refs, "banned": banned,
    }


async def ban_user(pool: asyncpg.Pool, user_id: int, admin_id: int, reason: str):
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO bans(user_id, reason, banned_by) VALUES($1,$2,$3) "
            "ON CONFLICT (user_id) DO UPDATE SET reason=$2, banned_by=$3, created_at=now()",
            user_id, reason, admin_id,
        )
        await con.execute("UPDATE users SET status='banned' WHERE id=$1", user_id)
        await con.execute(
            "INSERT INTO admin_actions(admin_id, action, target_id, detail) VALUES($1,'ban',$2,$3)",
            admin_id, user_id, '{"reason": "%s"}' % reason.replace('"', "'"),
        )


async def shadow_set(pool: asyncpg.Pool, user_id: int, admin_id: int, on: bool):
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO users(id) VALUES($1) ON CONFLICT (id) DO NOTHING", user_id
        )
        await con.execute("UPDATE users SET shadow_banned=$1 WHERE id=$2", on, user_id)
        await con.execute(
            "INSERT INTO admin_actions(admin_id, action, target_id, detail) VALUES($1,$2,$3,'{}')",
            admin_id, "shadow_on" if on else "shadow_off", user_id,
        )


async def unban_user(pool: asyncpg.Pool, user_id: int, admin_id: int):
    async with pool.acquire() as con:
        await con.execute("DELETE FROM bans WHERE user_id=$1", user_id)
        await con.execute("UPDATE users SET status='active' WHERE id=$1", user_id)
        await con.execute(
            "INSERT INTO admin_actions(admin_id, action, target_id, detail) VALUES($1,'unban',$2,'{}')",
            admin_id, user_id,
        )


async def grant_points(pool: asyncpg.Pool, user_id: int, amount: int, admin_id: int, redis=None):
    from .economy import award_points
    import time
    res = await award_points(pool, user_id, amount, "admin_grant",
                             f"grant:{admin_id}:{int(time.time())}", redis=redis)
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO admin_actions(admin_id, action, target_id, detail) VALUES($1,'grant',$2,$3)",
            admin_id, user_id, '{"amount": %d}' % amount,
        )
    return res


async def all_user_ids(pool: asyncpg.Pool):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT id FROM users WHERE status='active'")
    return [r["id"] for r in rows]


async def export_users_csv(pool: asyncpg.Pool) -> str:
    async with pool.acquire() as con:
        rows = await con.fetch(
            "SELECT id, username, level, points, streak_count, referred_by, status, created_at "
            "FROM users ORDER BY points DESC"
        )
    lines = ["id,username,level,points,streak,referred_by,status,created_at"]
    for r in rows:
        lines.append(
            f"{r['id']},{r['username'] or ''},{r['level']},{r['points']},{r['streak_count']},"
            f"{r['referred_by'] or ''},{r['status']},{r['created_at']}"
        )
    return "\n".join(lines)
