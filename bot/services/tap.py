"""Balanced tap-to-earn reactor economy (anti-farm). Server-authoritative.

Mechanics: daily rewarded-tap cap by level, per-level energy cost, tap fatigue,
reactor overheat + cooldown, soft-capped points-per-tap, anti-autoclicker.
Live heat/fatigue/cooldown live in Redis; ZLN-XP is the users.points ledger.
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
MAX_TAPS_PER_SEC = 20       # anti auto-clicker (server-side ceiling)
COMBO_TTL = 5
PASSIVE_CAP_HOURS = 8

# Tap fatigue / overheat
BURST_TTL = 60             # rapid-tap window resets after 60s idle
FATIGUE_1 = 100            # 100% reward up to here
FATIGUE_2 = 200            # 75% reward
FATIGUE_3 = 300            # 50% reward, then overheat
COOLDOWN_SEC = 300         # 5 min cooldown after overheat

# Soft caps
PPT_SOFT = 10              # bonus above base before diminishing returns
PPT_HARD = 22             # hard cap on bonus (max points_per_tap = 23)

DAILY_CAP = {1: 300, 2: 500, 3: 800, 4: 1200, 5: 1800}


def _now():
    return dt.datetime.now(dt.timezone.utc)


def daily_cap(level: int) -> int:
    if level <= 5:
        return DAILY_CAP.get(level, 300)
    return 1800 + (level - 5) * 200           # slow, not infinite


def energy_per_tap(level: int) -> int:
    return 1 + (level - 1) // 3               # higher levels cost more energy/reward


def _fatigue(burst: int):
    """Return (multiplier, stage). stage 3 => overheat."""
    if burst >= FATIGUE_3:
        return 0.5, 3
    if burst >= FATIGUE_2:
        return 0.5, 2
    if burst >= FATIGUE_1:
        return 0.75, 1
    return 1.0, 0


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
        stats[r["stat"]] = stats.get(r["stat"], BASE[r["stat"]]) + float(r["base_effect"]) * r["level"]
    # Soft cap points-per-tap: diminishing returns past +10, hard cap at +22.
    bonus = stats["points_per_tap"] - BASE["points_per_tap"]
    if bonus > PPT_SOFT:
        bonus = PPT_SOFT + (bonus - PPT_SOFT) * 0.5
    bonus = min(bonus, PPT_HARD)
    stats["points_per_tap"] = int(BASE["points_per_tap"] + bonus)
    stats["max_energy"] = int(stats["max_energy"])
    stats["recharge_rate"] = max(1, int(stats["recharge_rate"]))
    stats["passive_rate"] = int(stats["passive_rate"])
    return stats


async def _ensure(con, user_id):
    await con.execute("INSERT INTO tap_state(user_id) VALUES($1) ON CONFLICT DO NOTHING", user_id)


async def _daily_taps(con, user_id):
    """Return today's rewarded-tap count, resetting on a new UTC day."""
    st = await con.fetchrow("SELECT daily_taps, daily_date FROM tap_state WHERE user_id=$1", user_id)
    if not st:
        return 0
    if st["daily_date"] != dt.date.today():
        await con.execute("UPDATE tap_state SET daily_taps=0, daily_date=CURRENT_DATE WHERE user_id=$1", user_id)
        return 0
    return st["daily_taps"]


async def _live(redis, user_id):
    """Read live heat/fatigue/cooldown from Redis."""
    cd = await redis.ttl(f"tapcd:{user_id}")
    cooldown = cd if cd and cd > 0 else 0
    burst = int(await redis.get(f"burst:{user_id}") or 0)
    mult, stage = _fatigue(burst)
    overheat = min(100, round(burst / FATIGUE_3 * 100)) if burst else 0
    if cooldown:
        overheat = 100
    return {"cooldown": cooldown, "burst": burst, "fatigue_mult": mult,
            "fatigue_stage": stage, "overheat": overheat}


async def get_state(pool, redis, user_id):
    stats = await effective_stats(pool, user_id)
    async with pool.acquire() as con:
        await _ensure(con, user_id)
        st = await con.fetchrow("SELECT * FROM tap_state WHERE user_id=$1", user_id)
        elapsed = (_now() - st["last_energy_ts"]).total_seconds()
        energy = min(stats["max_energy"], st["energy_balance"] + int(stats["recharge_rate"] * elapsed))
        if energy > st["energy_balance"]:
            await con.execute("UPDATE tap_state SET energy_balance=$1, last_energy_ts=now() WHERE user_id=$2",
                              energy, user_id)
        daily = await _daily_taps(con, user_id)
        passive_secs = min((_now() - st["last_passive_ts"]).total_seconds(), PASSIVE_CAP_HOURS * 3600)
        pending = int(stats["passive_rate"] * passive_secs / 3600)
        points = await con.fetchval("SELECT points FROM users WHERE id=$1", user_id)

    level = economy.level_for(points)
    cap = daily_cap(level)
    live = await _live(redis, user_id) if redis else {"cooldown": 0, "fatigue_mult": 1.0,
                                                      "fatigue_stage": 0, "overheat": 0}
    nxt = economy.next_threshold(points)
    return {
        "zp": points,
        "energy": energy, "max_energy": stats["max_energy"], "energy_per_tap": energy_per_tap(level),
        "points_per_tap": stats["points_per_tap"], "recharge_rate": stats["recharge_rate"],
        "passive_rate": stats["passive_rate"], "combo_mult": round(stats["combo_mult"], 2),
        "passive_pending": pending, "passive_cap_hours": PASSIVE_CAP_HOURS,
        "total_taps": st["total_taps"], "total_energy_generated": st["total_energy_generated"],
        "best_combo": st["best_combo"],
        # economy / limits
        "level": level, "next_level_xp": nxt[1], "level_xp_floor": economy.xp_threshold(level),
        "rank": economy.rank_name(level),
        "daily_tap_cap": cap, "daily_taps_used": daily, "daily_taps_remaining": max(0, cap - daily),
        "overheat_percent": live["overheat"], "cooldown_seconds": live["cooldown"],
        "fatigue_stage": live["fatigue_stage"], "fatigue_multiplier": live["fatigue_mult"],
    }


async def tap(pool, redis, user_id, taps, nonce):
    taps = max(1, min(int(taps), MAX_TAPS_PER_REQ))

    # Idempotency.
    if not await redis.set(f"tapn:{user_id}:{nonce}", "1", nx=True, ex=120):
        return {**await get_state(pool, redis, user_id), "awarded_points": 0, "valid_taps": 0, "duplicate": True}

    # Anti auto-clicker: per-second ceiling -> shadow-limit silently.
    sec = await redis.incr(f"tps:{user_id}")
    if sec == 1:
        await redis.expire(f"tps:{user_id}", 1)
    if sec > MAX_TAPS_PER_SEC:
        async with pool.acquire() as con:
            await con.execute("UPDATE tap_state SET suspicious_tap_score=suspicious_tap_score+1 WHERE user_id=$1", user_id)
        return {**await get_state(pool, redis, user_id), "awarded_points": 0, "valid_taps": 0, "rate_limited": True}

    # Cooldown (overheat) -> animation only.
    if (await redis.ttl(f"tapcd:{user_id}") or 0) > 0:
        return {**await get_state(pool, redis, user_id), "awarded_points": 0, "valid_taps": 0,
                "message": "⚠ Reactor overheating. Cooling cycle engaged."}

    stats = await effective_stats(pool, user_id)
    async with pool.acquire() as con:
        await _ensure(con, user_id)
        st = await con.fetchrow("SELECT * FROM tap_state WHERE user_id=$1", user_id)
        elapsed = (_now() - st["last_energy_ts"]).total_seconds()
        energy = min(stats["max_energy"], st["energy_balance"] + int(stats["recharge_rate"] * elapsed))
        points = await con.fetchval("SELECT points FROM users WHERE id=$1", user_id)
        daily = await _daily_taps(con, user_id)

    level = economy.level_for(points)
    cap = daily_cap(level)
    cost = energy_per_tap(level)
    daily_remaining = max(0, cap - daily)

    # Burst window drives fatigue + overheat.
    burst = await redis.incrby(f"burst:{user_id}", taps)
    await redis.expire(f"burst:{user_id}", BURST_TTL)
    fatigue_mult, stage = _fatigue(burst)
    if burst >= FATIGUE_3:                       # overheat -> cooldown
        await redis.set(f"tapcd:{user_id}", "1", ex=COOLDOWN_SEC)
        await redis.delete(f"burst:{user_id}")
        async with pool.acquire() as con:
            await con.execute("UPDATE tap_state SET cooldown_until=now()+interval '300 seconds', "
                              "overheat_value=100, fatigue_stage=3 WHERE user_id=$1", user_id)
        return {**await get_state(pool, redis, user_id), "awarded_points": 0, "valid_taps": 0,
                "message": "⚠ Reactor Overheating. Cooling cycle engaged."}

    if daily_remaining <= 0:                      # daily cap reached -> animation only
        return {**await get_state(pool, redis, user_id), "awarded_points": 0, "valid_taps": 0,
                "daily_cap_reached": True,
                "message": "Daily Reactor limit reached. Come back tomorrow or complete missions for bonus energy."}

    allowed_by_energy = energy // cost
    rewarded = min(taps, daily_remaining, allowed_by_energy)
    if rewarded <= 0:                             # no energy -> animation only
        return {**await get_state(pool, redis, user_id), "awarded_points": 0, "valid_taps": 0,
                "message": "No Reactor Energy. Wait for refill or claim daily energy."}

    combo = await redis.incr(f"combo:{user_id}")
    await redis.expire(f"combo:{user_id}", COMBO_TTL)
    surge = 2.0 if combo >= 100 else 1.5 if combo >= 50 else 1.2 if combo >= 10 else 1.0
    zp = int(round(rewarded * stats["points_per_tap"] * fatigue_mult
                   * (1 + (surge - 1) * stats["combo_mult"])))
    zp = max(0, zp)

    async with pool.acquire() as con:
        await con.execute(
            "UPDATE tap_state SET energy_balance=$1, last_energy_ts=now(), total_taps=total_taps+$2, "
            "total_energy_generated=total_energy_generated+$3, daily_taps=$4, daily_date=CURRENT_DATE, "
            "best_combo=GREATEST(best_combo,$5), overheat_value=$6, fatigue_stage=$7 WHERE user_id=$8",
            energy - rewarded * cost, rewarded, zp, daily + rewarded, combo,
            min(100, round(burst / FATIGUE_3 * 100)), stage, user_id)
        await con.execute("INSERT INTO tap_events(user_id, taps, zp, combo, nonce) VALUES($1,$2,$3,$4,$5)",
                          user_id, rewarded, zp, combo, nonce)

    if zp > 0:
        await economy.award_points(pool, user_id, zp, "tap", f"tap:{nonce}", redis=redis)

    out = await get_state(pool, redis, user_id)
    return {**out, "awarded_points": zp, "valid_taps": rewarded, "earned": zp,
            "combo": combo, "fatigue_multiplier": fatigue_mult}


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
