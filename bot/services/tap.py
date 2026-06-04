"""Tap-to-earn reactor economy. Server-authoritative: the frontend never sets rewards.

ZLN-XP is the existing users.points ledger (so leaderboard/anti-cheat are unified).
Reactor Energy is a separate per-user resource in tap_state.
"""
import datetime as dt
from . import economy

BASE = {
    "points_per_tap": 1,
    "max_energy": 1000,
    "recharge_rate": 1,     # energy per second
    "passive_rate": 0,      # ZLN-XP per hour
    "combo_mult": 1.0,
}

MAX_TAPS_PER_REQ = 50
RATE_WINDOW_SEC = 3
RATE_MAX_REQS = 15          # max tap POSTs per 3s window (anti auto-clicker)
PASSIVE_CAP_HOURS = 8
COMBO_TTL = 5


def _now():
    return dt.datetime.now(dt.timezone.utc)


async def effective_stats(pool, user_id):
    async with pool.acquire() as con:
        rows = await con.fetch(
            """SELECT u.stat, u.base_effect, COALESCE(uu.level,0) AS level
               FROM upgrades u LEFT JOIN user_upgrades uu
                 ON uu.code=u.code AND uu.user_id=$1""",
            user_id,
        )
    stats = dict(BASE)
    for r in rows:
        stats[r["stat"]] = BASE[r["stat"]] + float(r["base_effect"]) * r["level"]
    stats["points_per_tap"] = int(stats["points_per_tap"])
    stats["max_energy"] = int(stats["max_energy"])
    stats["recharge_rate"] = max(1, int(stats["recharge_rate"]))
    stats["passive_rate"] = int(stats["passive_rate"])
    return stats


async def _ensure(con, user_id):
    await con.execute("INSERT INTO tap_state(user_id) VALUES($1) ON CONFLICT DO NOTHING", user_id)


async def get_state(pool, user_id):
    stats = await effective_stats(pool, user_id)
    async with pool.acquire() as con:
        await _ensure(con, user_id)
        st = await con.fetchrow("SELECT * FROM tap_state WHERE user_id=$1", user_id)

        # Lazy energy regen.
        elapsed = (_now() - st["last_energy_ts"]).total_seconds()
        energy = min(stats["max_energy"], st["energy_balance"] + int(stats["recharge_rate"] * elapsed))

        # Daily tap counter reset.
        daily = st["daily_taps"]
        if st["daily_date"] != dt.date.today():
            daily = 0

        if energy != st["energy_balance"] or daily != st["daily_taps"]:
            await con.execute(
                "UPDATE tap_state SET energy_balance=$1, last_energy_ts=now(), "
                "daily_taps=$2, daily_date=CURRENT_DATE WHERE user_id=$3",
                energy, daily, user_id,
            )

        # Passive (Validator Yield) pending, capped at 8h.
        passive_secs = min((_now() - st["last_passive_ts"]).total_seconds(), PASSIVE_CAP_HOURS * 3600)
        pending = int(stats["passive_rate"] * passive_secs / 3600)
        points = await con.fetchval("SELECT points FROM users WHERE id=$1", user_id)

    full_secs = max(0, (stats["max_energy"] - energy) / stats["recharge_rate"])
    return {
        "zp": points,
        "energy": energy,
        "max_energy": stats["max_energy"],
        "energy_per_tap": 1,
        "points_per_tap": stats["points_per_tap"],
        "recharge_rate": stats["recharge_rate"],
        "passive_rate": stats["passive_rate"],
        "combo_mult": round(stats["combo_mult"], 2),
        "passive_pending": pending,
        "passive_cap_hours": PASSIVE_CAP_HOURS,
        "seconds_to_full": int(full_secs),
        "total_taps": st["total_taps"],
        "total_energy_generated": st["total_energy_generated"],
        "best_combo": st["best_combo"],
        "daily_taps": st["daily_taps"] if st["daily_date"] == dt.date.today() else 0,
    }


def _combo_tier(combo):
    if combo >= 100:
        return "overdrive", 2.0
    if combo >= 50:
        return "surge", 1.5
    if combo >= 10:
        return "combo", 1.2
    return None, 1.0


async def tap(pool, redis, user_id, taps, nonce):
    taps = max(1, min(int(taps), MAX_TAPS_PER_REQ))

    # Idempotency: a given nonce is processed once.
    if not await redis.set(f"tapn:{user_id}:{nonce}", "1", nx=True, ex=120):
        st = await get_state(pool, user_id)
        return {**st, "earned": 0, "duplicate": True}

    # Anti auto-clicker: cap requests per rolling window.
    cnt = await redis.incr(f"taprl:{user_id}")
    if cnt == 1:
        await redis.expire(f"taprl:{user_id}", RATE_WINDOW_SEC)
    if cnt > RATE_MAX_REQS:
        st = await get_state(pool, user_id)
        return {**st, "earned": 0, "rate_limited": True}

    stats = await effective_stats(pool, user_id)
    async with pool.acquire() as con:
        await _ensure(con, user_id)
        st = await con.fetchrow("SELECT * FROM tap_state WHERE user_id=$1", user_id)
        elapsed = (_now() - st["last_energy_ts"]).total_seconds()
        energy = min(stats["max_energy"], st["energy_balance"] + int(stats["recharge_rate"] * elapsed))

    allowed = min(taps, energy)
    if allowed <= 0:
        out = await get_state(pool, user_id)
        return {**out, "earned": 0, "combo": 0, "combo_tier": None}

    combo = await redis.incr(f"combo:{user_id}")
    await redis.expire(f"combo:{user_id}", COMBO_TTL)
    tier, surge = _combo_tier(combo)
    base_zp = allowed * stats["points_per_tap"]
    zp = int(round(base_zp * (1 + (surge - 1) * stats["combo_mult"])))

    async with pool.acquire() as con:
        await con.execute(
            "UPDATE tap_state SET energy_balance=$1, last_energy_ts=now(), "
            "total_taps=total_taps+$2, total_energy_generated=total_energy_generated+$3, "
            "daily_taps=CASE WHEN daily_date=CURRENT_DATE THEN daily_taps ELSE 0 END + $2, "
            "daily_date=CURRENT_DATE, best_combo=GREATEST(best_combo,$4) WHERE user_id=$5",
            energy - allowed, allowed, zp, combo, user_id,
        )
        await con.execute(
            "INSERT INTO tap_events(user_id, taps, zp, combo, nonce) VALUES($1,$2,$3,$4,$5)",
            user_id, allowed, zp, combo, nonce,
        )

    await economy.award_points(pool, user_id, zp, "tap", f"tap:{nonce}", redis=redis)
    await redis.set(f"combomax:{user_id}", str(combo), ex=86400) if combo else None

    out = await get_state(pool, user_id)
    return {**out, "earned": zp, "combo": combo, "combo_tier": tier}


async def claim_passive(pool, redis, user_id):
    stats = await effective_stats(pool, user_id)
    async with pool.acquire() as con:
        await _ensure(con, user_id)
        st = await con.fetchrow("SELECT last_passive_ts FROM tap_state WHERE user_id=$1", user_id)
        secs = min((_now() - st["last_passive_ts"]).total_seconds(), PASSIVE_CAP_HOURS * 3600)
        amount = int(stats["passive_rate"] * secs / 3600)
        if amount <= 0:
            return {"claimed": 0, "reason": "nothing_to_claim"}
        await con.execute("UPDATE tap_state SET last_passive_ts=now() WHERE user_id=$1", user_id)
        await con.execute("INSERT INTO passive_rewards(user_id, amount) VALUES($1,$2)", user_id, amount)
    await economy.award_points(pool, user_id, amount, "passive",
                               f"passive:{user_id}:{int(_now().timestamp())}", redis=redis)
    return {"claimed": amount}
