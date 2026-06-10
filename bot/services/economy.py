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
            # Game XP (points) AND Ranking XP rise together during normal play; they
            # diverge only via admin adjustments (game-xp vs ranking-xp) and spending.
            row = await con.fetchrow(
                "UPDATE users SET points = points + $1, ranking_xp = ranking_xp + $1 "
                "WHERE id=$2 RETURNING points, level",
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


# ---------------- Admin XP management ----------------
async def admin_set_game_xp(pool, user_id, delta, redis=None):
    """Adjust ONLY Game XP (users.points) — spendable in-game balance. Clamps at 0 and
    recomputes level. Does NOT change Ranking XP or leaderboard position.
    Returns {old, new, level, rank_name} or None if the user doesn't exist."""
    delta = int(delta)
    async with pool.acquire() as con:
        async with con.transaction():
            row = await con.fetchrow("SELECT points, level FROM users WHERE id=$1 FOR UPDATE", user_id)
            if not row:
                return None
            old = int(row["points"] or 0)
            new = max(0, old + delta)
            applied = new - old
            ref = f"admin_game_xp:{user_id}:{int(_now().timestamp() * 1000)}"
            await con.execute(
                "INSERT INTO points_ledger(user_id, amount, reason, ref_id) VALUES($1,$2,'admin_game_xp',$3)",
                user_id, applied, ref)
            new_level = level_for(new)
            await con.execute("UPDATE users SET points=$1, level=$2 WHERE id=$3", new, new_level, user_id)
    if redis is not None and new_level != int(row["level"] or 1):
        await redis.delete(f"taphr:{user_id}")      # capacity cache on level change
    return {"old": old, "new": new, "applied": applied,
            "level": new_level, "rank_name": rank_name(new_level)}


async def admin_set_ranking_xp(pool, user_id, delta, redis=None):
    """Adjust ONLY Ranking XP (leaderboard position). Clamps at 0 and refreshes the
    Redis leaderboards. Does NOT touch Game XP / level. Returns {old, new} or None."""
    delta = int(delta)
    async with pool.acquire() as con:
        async with con.transaction():
            row = await con.fetchrow("SELECT ranking_xp FROM users WHERE id=$1 FOR UPDATE", user_id)
            if not row:
                return None
            old = int(row["ranking_xp"] or 0)
            new = max(0, old + delta)
            await con.execute("UPDATE users SET ranking_xp=$1 WHERE id=$2", new, user_id)
    applied = new - old
    if redis is not None:
        # All-time board mirrors ranking_xp exactly.
        if new > 0:
            await redis.zadd(LB_ALL, {str(user_id): new})
        else:
            await redis.zrem(LB_ALL, str(user_id))
        # Weekly board: shift by the applied delta, floored at 0.
        wk = await redis.zscore(LB_WEEK, str(user_id))
        wk_new = max(0, (int(wk) if wk is not None else 0) + applied)
        if wk_new > 0:
            await redis.zadd(LB_WEEK, {str(user_id): wk_new})
        else:
            await redis.zrem(LB_WEEK, str(user_id))
    return {"old": old, "new": new, "applied": applied}


async def reseed_rankings(pool, redis):
    """Recalculate the all-time leaderboard ZSET from users.ranking_xp."""
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT id, ranking_xp FROM users WHERE ranking_xp > 0")
    await redis.delete(LB_ALL)
    if rows:
        await redis.zadd(LB_ALL, {str(r["id"]): int(r["ranking_xp"]) for r in rows})
    return {"users": len(rows)}


# Per-user game-progress tables wiped on a full account reset (all have a user_id column).
RESET_TABLES = [
    "points_ledger", "tap_events", "tap_state", "user_tap_missions", "user_upgrades",
    "user_task_progress", "user_task_unlocks", "task_claims", "puzzle_attempts",
    "quiz_attempts", "daily_quiz_sessions", "group_activity", "user_group_missions",
    "passive_rewards", "mission_completions", "proof_submissions", "social_accounts",
]


async def _clear_user_redis(redis, user_id):
    keys = [f"burst:{user_id}", f"combo:{user_id}", f"gflood:{user_id}", f"quizcd:{user_id}",
            f"quizstreak:{user_id}", f"quizwrong:{user_id}", f"tapcd:{user_id}",
            f"taphr:{user_id}", f"tps:{user_id}"]
    try:
        await redis.delete(*keys)
    except Exception:
        pass
    for pat in (f"dupmsg:{user_id}:*", f"gmis:{user_id}:*", f"pzcd:{user_id}:*",
                f"pzwrong:{user_id}:*", f"tapmis:{user_id}:*", f"tapn:{user_id}:*",
                f"tapwk:{user_id}:*", f"upg:{user_id}:*", f"passive:{user_id}:*"):
        try:
            async for k in redis.scan_iter(match=pat, count=300):
                await redis.delete(k)
        except Exception:
            pass
    await redis.zrem(LB_ALL, str(user_id))
    await redis.zrem(LB_WEEK, str(user_id))


async def reset_account(pool, user_id, redis=None):
    """Reset a user to starter state WITHOUT deleting the account. Keeps id, username,
    first_name, created_at, status, referred_by. Returns the pre-reset snapshot or None."""
    async with pool.acquire() as con:
        row = await con.fetchrow("SELECT points, level FROM users WHERE id=$1", user_id)
        if not row:
            return None
        snap = {"old_xp": int(row["points"] or 0), "old_level": int(row["level"] or 1),
                "old_rank": rank_name(int(row["level"] or 1))}
        async with con.transaction():
            for t in RESET_TABLES:
                await con.execute(f"DELETE FROM {t} WHERE user_id=$1", user_id)
            # Reset progression on the kept account record (Game XP + Ranking XP).
            await con.execute(
                "UPDATE users SET points=0, ranking_xp=0, level=1, streak_count=0, "
                "last_daily_claim=NULL WHERE id=$1", user_id)
            # Restore starter energy.
            await con.execute(
                "INSERT INTO energy(user_id,current,max_cap,regen_rate,updated_at) "
                "VALUES($1,100,100,5,now()) "
                "ON CONFLICT (user_id) DO UPDATE SET current=100, max_cap=100, regen_rate=5, updated_at=now()",
                user_id)
    if redis is not None:
        await _clear_user_redis(redis, user_id)     # heat, cooldowns, capacity, streaks, board score
    return snap


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
