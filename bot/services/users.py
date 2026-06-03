import asyncpg


async def ensure_user(pool: asyncpg.Pool, user_id: int, username: str, first_name: str):
    """Upsert user + energy row. Returns user record."""
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """INSERT INTO users(id, username, first_name)
                   VALUES($1,$2,$3)
                   ON CONFLICT (id) DO UPDATE SET username=$2, first_name=$3""",
                user_id, username, first_name,
            )
            await con.execute(
                "INSERT INTO energy(user_id) VALUES($1) ON CONFLICT (user_id) DO NOTHING",
                user_id,
            )
        return await con.fetchrow("SELECT * FROM users WHERE id=$1", user_id)


async def get_user(pool: asyncpg.Pool, user_id: int):
    async with pool.acquire() as con:
        return await con.fetchrow("SELECT * FROM users WHERE id=$1", user_id)


async def is_banned(pool: asyncpg.Pool, user_id: int) -> bool:
    async with pool.acquire() as con:
        return await con.fetchval("SELECT 1 FROM bans WHERE user_id=$1", user_id) is not None


async def set_referrer(pool: asyncpg.Pool, invitee_id: int, referrer_id: int):
    """Create a pending referral once, only for brand-new invitees."""
    if invitee_id == referrer_id:
        return
    async with pool.acquire() as con:
        ref_exists = await con.fetchval("SELECT 1 FROM users WHERE id=$1", referrer_id)
        if not ref_exists:
            return
        already = await con.fetchval("SELECT 1 FROM referrals WHERE invitee_id=$1", invitee_id)
        if already:
            return
        await con.execute("UPDATE users SET referred_by=$1 WHERE id=$2", referrer_id, invitee_id)
        await con.execute(
            "INSERT INTO referrals(referrer_id, invitee_id, status) VALUES($1,$2,'pending') "
            "ON CONFLICT (invitee_id) DO NOTHING",
            referrer_id, invitee_id,
        )


async def referral_stats(pool: asyncpg.Pool, user_id: int):
    async with pool.acquire() as con:
        activated = await con.fetchval(
            "SELECT count(*) FROM referrals WHERE referrer_id=$1 AND status='activated'", user_id
        )
        pending = await con.fetchval(
            "SELECT count(*) FROM referrals WHERE referrer_id=$1 AND status='pending'", user_id
        )
    return activated, pending
