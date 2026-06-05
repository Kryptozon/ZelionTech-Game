"""Energy, XP/points ledger, levels, daily claim, referral activation.

Phase 3 additions:
  * surge multiplier (Redis) applied to engagement awards
  * shadow-ban (DB flag) silently zeroes real points
  * Redis ZSET leaderboards updated on every real award
"""
from datetime import datetime, timezone, timedelta
import asyncpg

RANKS = {1: "⚡ Spark", 2: "🔋 Charge", 3: "☢️ Reactor", 4: "🌐 Grid", 5: "🔮 Oracle",
         6: "🌌 Oracle II", 7: "🌠 Singularity", 8: "💫 Ascendant", 9: "🛸 Apex", 10: "👑 Zelion Master"}

# Harder level curve: cumulative XP to BE at `level` = BASE_XP * (level-1)^1.8
# (≈ L2:250, L3:870, L4:1805, L5:3027, L6:4524 ... grows steeply, anti-farm).
BASE_XP = 250
LEVEL_EXP = 1.8

DAILY_TABLE = {1: (50, 10), 2: (55, 15), 3: (60, 20), 4: (70, 25), 5: (80, 35), 6: (90, 45)}
DAILY_MAX = (100, 60)

REFERRAL_XP = 150
REFERRAL_ENERGY_BOOST = 50
REFERRAL_ACTIVATION_MIN_XP = 50
REFERRAL_ACTIVATION_MIN_AGE_H = 24
REFERRAL_DAILY_CAP = 20

LB_ALL = "lb:all"
LB_WEEK = "lb:week"


def _now():
    return datetime.now(timezone.utc)


def xp_threshold(level: int) -> int:
    """Cumulative XP required to reach `level` (level 1 = 0)."""
    if level <= 1:
        return 0
    return round(BASE_XP * (level - 1) ** LEVEL_EXP)


def level_for(points: int) -> int:
    lvl = 1
    while lvl < 999 and xp_threshold(lvl + 1) <= points:
        lvl += 1
    return lvl


def next_threshold(points: int):
    lvl = level_for(points)
    return (lvl + 1, xp_threshold(lvl + 1))


def rank_name(level: int) -> str:
    return RANKS.get(level, RANKS[10] if level > 10 else "⚡ Spark")


# ---------------- helpers ----------------
async def _is_shadow(pool: asyncpg.Pool, user_id: int) -> bool:
    async with pool.acquire() as con:
        return bool(await con.fetchval("SELECT shadow_banned FROM users WHERE id=$1", user_id))


async def _surge_mult(redis) -> int:
    if redis is None:
        return 1
    v = await redis.get("surge:mult")
    try:
        return int(v) if v else 1
    except (TypeError, ValueError):
        return 1


# ---------------- Points ----------------
async def award_points(pool, user_id, amount, reason, ref_id, redis=None, surge=False):
    """Idempotent award. Applies surge (if requested) and shadow-ban.
    Updates Redis ZSETs for real (>0) awards. Returns rich result dict."""
    shadow = await _is_shadow(pool, user_id)
    mult = await _surge_mult(redis) if surge else 1
    final = 0 if shadow else int(amount * mult)

    async with pool.acquire() as con:
        async with con.transaction():
            try:
                await con.execute(
                    "INSERT INTO points_ledger(user_id, amount, reason, ref_id) VALUES($1,$2,$3,$4)",
                    user_id, final, reason, ref_id,
                )
            except asyncpg.UniqueViolationError:
                row = await con.fetchrow("SELECT level FROM users WHERE id=$1", user_id)
                return {"ok": False, "leveled": False, "level": row["level"] if row else 1,
                        "awarded": 0, "shadow": shadow, "multiplier": mult}
            row = await con.fetchrow(
                "UPDATE users SET points = points + $1 WHERE id=$2 RETURNING points, level",
                final, user_id,
            )
            new_level = level_for(row["points"])
            leveled = new_level > row["level"]
            if leveled:
                await con.execute("UPDATE users SET level=$1 WHERE id=$2", new_level, user_id)

    if redis is not None and final > 0:
        await redis.zincrby(LB_ALL, final, str(user_id))
        await redis.zincrby(LB_WEEK, final, str(user_id))
    # Level-up perk: refill the hourly reactor capacity to maximum.
    if leveled and redis is not None:
        await redis.delete(f"taphr:{user_id}")

    return {"ok": True, "leveled": leveled, "level": new_level,
            "awarded": final, "shadow": shadow, "multiplier": mult}


async def deduct_points(pool, user_id, amount, reason, ref_id):
    """Penalty: subtract ZLN-XP but NEVER below 0; never lowers level. Idempotent."""
    amount = abs(int(amount))
    async with pool.acquire() as con:
        cur = await con.fetchval("SELECT points FROM users WHERE id=$1", user_id) or 0
        take = min(cur, amount)
        if take <= 0:
            return {"deducted": 0, "balance": cur}
        try:
            await con.execute(
                "INSERT INTO points_ledger(user_id, amount, reason, ref_id) VALUES($1,$2,$3,$4)",
                user_id, -take, reason, ref_id)
        except asyncpg.UniqueViolationError:
            return {"deducted": 0, "balance": cur}
        newbal = await con.fetchval(
            "UPDATE users SET points = GREATEST(0, points - $1) WHERE id=$2 RETURNING points",
            take, user_id)
    return {"deducted": take, "balance": newbal}


# ---------------- Energy ----------------
async def get_energy(pool, user_id) -> int:
    async with pool.acquire() as con:
        r = await con.fetchrow(
            "SELECT current, max_cap, regen_rate, updated_at FROM energy WHERE user_id=$1", user_id
        )
        if not r:
            return 0
        hours = (_now() - r["updated_at"]).total_seconds() / 3600
        regenerated = min(r["max_cap"], r["current"] + int(r["regen_rate"] * hours))
        if regenerated > r["current"]:
            await con.execute(
                "UPDATE energy SET current=$1, updated_at=now() WHERE user_id=$2", regenerated, user_id
            )
        return regenerated


async def energy_status(pool, user_id):
    cur = await get_energy(pool, user_id)
    async with pool.acquire() as con:
        cap = await con.fetchval("SELECT max_cap FROM energy WHERE user_id=$1", user_id)
    return cur, cap or 100


async def spend_energy(pool, user_id, cost) -> bool:
    if cost <= 0:
        return True
    cur = await get_energy(pool, user_id)
    if cur < cost:
        return False
    async with pool.acquire() as con:
        await con.execute(
            "UPDATE energy SET current = current - $1, updated_at=now() WHERE user_id=$2", cost, user_id
        )
    return True


async def add_energy(pool, user_id, amount):
    async with pool.acquire() as con:
        await con.execute(
            "UPDATE energy SET current = LEAST(max_cap, current + $1), updated_at=now() WHERE user_id=$2",
            amount, user_id,
        )


# ---------------- Daily claim ----------------
async def claim_daily(pool, user_id, redis=None):
    async with pool.acquire() as con:
        u = await con.fetchrow("SELECT last_daily_claim, streak_count FROM users WHERE id=$1", user_id)
        now = _now()
        if u["last_daily_claim"]:
            delta = now - u["last_daily_claim"]
            if delta < timedelta(hours=24):
                left = timedelta(hours=24) - delta
                return {"status": "cooldown", "seconds": int(left.total_seconds())}
            streak = u["streak_count"] + 1 if delta < timedelta(hours=48) else 1
        else:
            streak = 1

        energy_amt, xp_amt = DAILY_TABLE.get(streak, DAILY_MAX)
        await con.execute("UPDATE users SET last_daily_claim=now(), streak_count=$1 WHERE id=$2",
                          streak, user_id)
        await con.execute(
            "UPDATE energy SET current = LEAST(max_cap, current + $1), updated_at=now() WHERE user_id=$2",
            energy_amt, user_id,
        )

    res = await award_points(pool, user_id, xp_amt, "daily", now.strftime("%Y-%m-%d"),
                             redis=redis, surge=True)
    return {"status": "ok", "energy": energy_amt, "xp": xp_amt, "streak": streak, "award": res}


# ---------------- Referral activation ----------------
async def maybe_activate_referral(pool, invitee_id, redis=None):
    async with pool.acquire() as con:
        r = await con.fetchrow(
            "SELECT * FROM referrals WHERE invitee_id=$1 AND status='pending'", invitee_id
        )
        if not r:
            return None
        if r["referrer_id"] == invitee_id:
            await con.execute("UPDATE referrals SET status='rejected' WHERE id=$1", r["id"])
            return None

        inv = await con.fetchrow("SELECT points, created_at FROM users WHERE id=$1", invitee_id)
        if inv["points"] < REFERRAL_ACTIVATION_MIN_XP:
            return None
        if (_now() - inv["created_at"]) < timedelta(hours=REFERRAL_ACTIVATION_MIN_AGE_H):
            return None

        recent = await con.fetchval(
            "SELECT count(*) FROM referrals WHERE referrer_id=$1 AND status='activated' "
            "AND activated_at > now() - interval '1 day'",
            r["referrer_id"],
        )
        if recent >= REFERRAL_DAILY_CAP:
            return None

        await con.execute(
            "UPDATE referrals SET status='activated', reward_given=true, activated_at=now() WHERE id=$1",
            r["id"],
        )

    await add_energy(pool, r["referrer_id"], REFERRAL_ENERGY_BOOST)
    await award_points(pool, r["referrer_id"], REFERRAL_XP, "referral", f"ref:{invitee_id}", redis=redis)
    from . import analytics
    await analytics.log_event(pool, r["referrer_id"], "referral_activated", {"invitee": invitee_id})
    return r["referrer_id"]
