"""Reactor Lab — upgrade catalogue, cost scaling, purchase (server-validated)."""
from . import economy


def cost_for(base_cost, growth, level):
    return int(base_cost * (float(growth) ** level))


async def list_for_user(pool, user_id):
    async with pool.acquire() as con:
        rows = await con.fetch(
            """SELECT u.*, COALESCE(uu.level,0) AS level
               FROM upgrades u LEFT JOIN user_upgrades uu
                 ON uu.code=u.code AND uu.user_id=$1
               ORDER BY u.sort""",
            user_id,
        )
        points = await con.fetchval("SELECT points FROM users WHERE id=$1", user_id)
    out = []
    for r in rows:
        lvl = r["level"]
        maxed = lvl >= r["max_level"]
        cost = None if maxed else cost_for(r["base_cost"], r["cost_growth"], lvl)
        out.append({
            "code": r["code"], "name": r["name"], "description": r["description"],
            "icon": r["icon"], "stat": r["stat"], "level": lvl, "max_level": r["max_level"],
            "effect_per_level": float(r["base_effect"]),
            "next_cost": cost, "maxed": maxed, "affordable": (cost is not None and points >= cost),
        })
    return {"zp": points, "upgrades": out}


async def buy(pool, redis, user_id, code):
    async with pool.acquire() as con:
        u = await con.fetchrow("SELECT * FROM upgrades WHERE code=$1", code)
        if not u:
            return {"error": "unknown_upgrade"}
        lvl = await con.fetchval(
            "SELECT COALESCE(level,0) FROM user_upgrades WHERE user_id=$1 AND code=$2", user_id, code
        ) or 0
        if lvl >= u["max_level"]:
            return {"error": "maxed"}
        cost = cost_for(u["base_cost"], u["cost_growth"], lvl)
        points = await con.fetchval("SELECT points FROM users WHERE id=$1", user_id)
        if points < cost:
            return {"error": "insufficient_zp", "cost": cost, "zp": points}

    # Spend ZLN-XP via the idempotent ledger (negative entry), then bump level.
    spent = await economy.award_points(pool, user_id, -cost, "upgrade",
                                       f"upg:{user_id}:{code}:{lvl}", redis=redis)
    if not spent["ok"]:
        return {"error": "already_processed"}
    async with pool.acquire() as con:
        await con.execute(
            """INSERT INTO user_upgrades(user_id, code, level) VALUES($1,$2,1)
               ON CONFLICT (user_id, code) DO UPDATE SET level = user_upgrades.level + 1""",
            user_id, code,
        )
        new_level = await con.fetchval(
            "SELECT level FROM user_upgrades WHERE user_id=$1 AND code=$2", user_id, code
        )
    return {"ok": True, "code": code, "level": new_level, "spent": cost}
