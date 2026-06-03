"""Tap missions / daily tasks with server-computed progress + claim."""
from . import economy


async def _progress(con, user_id):
    st = await con.fetchrow(
        "SELECT total_taps, total_energy_generated, best_combo FROM tap_state WHERE user_id=$1", user_id
    )
    upg = await con.fetchval(
        "SELECT COALESCE(sum(level),0) FROM user_upgrades WHERE user_id=$1", user_id
    ) or 0
    yields = await con.fetchval(
        "SELECT count(*) FROM passive_rewards WHERE user_id=$1", user_id
    ) or 0
    quiz = await con.fetchval(
        "SELECT count(*) FROM quiz_attempts WHERE user_id=$1 AND correct", user_id
    ) or 0
    return {
        "taps": (st["total_taps"] if st else 0),
        "energy": (st["total_energy_generated"] if st else 0),
        "combo": (st["best_combo"] if st else 0),
        "upgrade": upg,
        "yield": yields,
        "quiz": quiz,
    }


async def list_for_user(pool, user_id):
    async with pool.acquire() as con:
        missions = await con.fetch("SELECT * FROM tap_missions WHERE is_active ORDER BY id")
        claimed = {r["mission_id"] for r in await con.fetch(
            "SELECT mission_id FROM user_tap_missions WHERE user_id=$1", user_id)}
        prog = await _progress(con, user_id)
    out = []
    for m in missions:
        cur = prog.get(m["goal_type"], 0)
        done = cur >= m["goal"]
        out.append({
            "id": m["id"], "code": m["code"], "title": m["title"], "icon": m["icon"],
            "goal": m["goal"], "goal_type": m["goal_type"], "reward": m["reward"],
            "progress": min(cur, m["goal"]), "done": done,
            "claimed": m["id"] in claimed,
        })
    return out


async def claim(pool, redis, user_id, mission_id):
    async with pool.acquire() as con:
        m = await con.fetchrow("SELECT * FROM tap_missions WHERE id=$1 AND is_active", mission_id)
        if not m:
            return {"error": "not_found"}
        already = await con.fetchval(
            "SELECT 1 FROM user_tap_missions WHERE user_id=$1 AND mission_id=$2", user_id, mission_id)
        if already:
            return {"error": "already_claimed"}
        prog = await _progress(con, user_id)
        if prog.get(m["goal_type"], 0) < m["goal"]:
            return {"error": "incomplete", "progress": prog.get(m["goal_type"], 0), "goal": m["goal"]}
        await con.execute(
            "INSERT INTO user_tap_missions(user_id, mission_id) VALUES($1,$2) ON CONFLICT DO NOTHING",
            user_id, mission_id,
        )
    await economy.award_points(pool, user_id, m["reward"], "tap_mission",
                               f"tapmis:{user_id}:{mission_id}", redis=redis)
    return {"ok": True, "reward": m["reward"]}
