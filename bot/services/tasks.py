"""Progressive / infinite task chains. Server-authoritative: progress is computed
from real metrics, claims are validated, and finished chains auto-generate harder
prestige tiers so there is always something to do (designed for 6–12 months)."""
from . import economy

# Hard cap: no normal mission/task may reward more than this many ZLN-XP.
# (Only tiers explicitly flagged legendary_admin_only may exceed it — none do today.)
MISSION_REWARD_CAP = 500
MISSION_REWARD_MIN = 10


def clamp_reward(reward, legendary_admin_only=False):
    r = int(reward or 0)
    if legendary_admin_only:
        return max(0, r)
    return max(0, min(r, MISSION_REWARD_CAP))


TIER_LADDER = ["Bronze", "Silver", "Gold", "Platinum", "Diamond",
               "Reactor Elite", "Reactor Legend", "Reactor Oracle"]


def _tier_name(idx):
    return TIER_LADDER[idx - 1] if 1 <= idx <= len(TIER_LADDER) else "Reactor Oracle"


# chain: (code, name, category, icon, sequential, prestige, [tier...])
# tier: (title, metric, goal, reward[, tier_name])
CHAINS = [
    # ---- Rewards rebalanced LOW + capped at 500 ZLN-XP (no thousands). ----
    ("reactor_validation", "Validate Energy", "reactor", "⚛️", True, True, [
        ("Validate 1,000 taps", "taps", 1000, 20, "Bronze"),
        ("Validate 5,000 taps", "taps", 5000, 40, "Bronze"),
        ("Validate 10,000 taps", "taps", 10000, 75, "Bronze"),
        ("Validate 25,000 taps", "taps", 25000, 125, "Silver"),
        ("Validate 50,000 taps", "taps", 50000, 200, "Silver"),
        ("Validate 100,000 taps", "taps", 100000, 300, "Gold"),
        ("Validate 250,000 taps", "taps", 250000, 400, "Gold"),
        ("Validate 500,000 taps", "taps", 500000, 500, "Platinum"),
        ("Validate 1,000,000 taps", "taps", 1000000, 500, "Platinum"),
        ("Validate 5,000,000 taps", "taps", 5000000, 500, "Reactor Elite"),
        ("Validate 10,000,000 taps", "taps", 10000000, 500, "Reactor Elite"),
    ]),
    ("power_surge", "Power Surge", "reactor", "⚡", True, True, [
        ("Reach x10 combo", "surge", 10, 25),
        ("Reach x25 combo", "surge", 25, 50),
        ("Reach x50 combo", "surge", 50, 75),
        ("Reach x100 combo", "surge", 100, 100),
        ("Reach x250 combo", "surge", 250, 200),
        ("Reach x500 combo", "surge", 500, 300),
        ("Reach x1000 combo", "surge", 1000, 500),
    ]),
    ("reactor_core", "Reactor Core", "upgrade", "⚛️", True, False, [
        ("Reactor Core Lv5", "reactor_core", 5, 50),
        ("Reactor Core Lv10", "reactor_core", 10, 100),
        ("Reactor Core Lv20", "reactor_core", 20, 200),
        ("Reactor Core Lv35", "reactor_core", 35, 350),
        ("Reactor Core Lv50", "reactor_core", 50, 500),
    ]),
    ("battery_chain", "Battery Pack", "upgrade", "🔋", True, False, [
        ("Battery Pack Lv5", "battery_pack", 5, 40),
        ("Battery Pack Lv10", "battery_pack", 10, 80),
        ("Battery Pack Lv25", "battery_pack", 25, 200),
        ("Battery Pack Lv50", "battery_pack", 50, 400),
    ]),
    ("solar_chain", "Solar Amplifier", "upgrade", "☀️", True, False, [
        ("Solar Amplifier Lv5", "solar_amplifier", 5, 40),
        ("Solar Amplifier Lv10", "solar_amplifier", 10, 80),
        ("Solar Amplifier Lv25", "solar_amplifier", 25, 200),
        ("Solar Amplifier Lv50", "solar_amplifier", 50, 400),
    ]),
    ("quantum_chain", "Quantum Reactor", "upgrade", "🧪", True, False, [
        ("Quantum Reactor Lv5", "quantum_reactor", 5, 75),
        ("Quantum Reactor Lv10", "quantum_reactor", 10, 150),
        ("Quantum Reactor Lv25", "quantum_reactor", 25, 300),
        ("Quantum Reactor Lv50", "quantum_reactor", 50, 500),
    ]),
    ("community", "Community Voice", "community", "💬", True, True, [
        ("Send 25 valid messages", "messages", 25, 25),
        ("Send 100 valid messages", "messages", 100, 75),
        ("Send 250 valid messages", "messages", 250, 125),
        ("Send 500 valid messages", "messages", 500, 200),
        ("Send 1,000 valid messages", "messages", 1000, 400),
        ("Send 2,500 valid messages", "messages", 2500, 500),
    ]),
    ("replies", "Helpful Operator", "community", "↩️", True, True, [
        ("Reply to 10 users", "replies", 10, 50),
        ("Reply to 50 users", "replies", 50, 150),
        ("Reply to 100 users", "replies", 100, 300),
    ]),
    ("discussion", "Discussion Leader", "community", "🗣️", True, True, [
        ("Participate 3 times", "discussion", 3, 30),
        ("Participate 10 times", "discussion", 10, 100),
        ("Participate 25 times", "discussion", 25, 250),
    ]),
    ("quiz", "Quiz Scholar", "quiz", "🧠", True, True, [
        ("Get 10 correct answers", "quiz_correct", 10, 25),
        ("Get 50 correct answers", "quiz_correct", 50, 75),
        ("Get 100 correct answers", "quiz_correct", 100, 150),
        ("Get 500 correct answers", "quiz_correct", 500, 300),
        ("3-day streak", "login_streak", 3, 25),
        ("7-day streak", "login_streak", 7, 50),
        ("30-day streak", "login_streak", 30, 100),
    ]),
    ("puzzle", "Intelligence Solver", "puzzle", "🧩", True, True, [
        ("Solve 1 puzzle", "puzzles", 1, 25),
        ("Solve 5 puzzles", "puzzles", 5, 50),
        ("Solve 20 puzzles", "puzzles", 20, 150),
        ("Solve 50 puzzles", "puzzles", 50, 300),
        ("Solve 100 puzzles", "puzzles", 100, 500),
        ("Solve 250 puzzles", "puzzles", 250, 500),
        ("Solve a weekly mystery", "puzzles_legendary", 1, 200),
        ("Solve 3 elite mysteries", "puzzles_legendary", 3, 500),
    ]),
    ("social", "Social Operator", "social", "📡", False, False, [
        ("Join Telegram Channel", "social_telegram_official", 1, 30),
        ("Join Telegram Group", "social_telegram_global", 1, 35),
        ("Subscribe YouTube", "social_youtube", 1, 50),
        ("Follow X", "social_x", 1, 40),
        ("Follow Instagram", "social_instagram", 1, 40),
        ("Complete all socials", "social_count", 5, 100),
    ]),
]


async def ensure_seed(pool):
    async with pool.acquire() as con:
        for sort, (code, name, cat, icon, seq, prestige, tiers) in enumerate(CHAINS):
            hidden = code.startswith("hidden_")
            cid = await con.fetchval(
                """INSERT INTO task_chains(code,name,category,icon,sequential,prestige,hidden,sort)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8)
                   ON CONFLICT (code) DO UPDATE SET name=$2, icon=$4, category=$3 RETURNING id""",
                code, name, cat, icon, seq, prestige, hidden, sort)
            for i, tier in enumerate(tiers, start=1):
                title, metric, goal, reward = tier[0], tier[1], tier[2], tier[3]
                reward = clamp_reward(reward)        # hard cap: never above 500 ZLN-XP
                tname = tier[4] if len(tier) > 4 else _tier_name(i)
                # Upsert so re-seeding applies updated goals/titles — but NEVER overwrite a
                # reward an admin changed in the dashboard (admin_overridden guard).
                await con.execute(
                    """INSERT INTO task_definitions(chain_id,tier_index,title,metric,goal,reward,tier_name)
                       VALUES($1,$2,$3,$4,$5,$6,$7)
                       ON CONFLICT (chain_id,tier_index)
                       DO UPDATE SET title=$3, metric=$4, goal=$5, tier_name=$7,
                         reward = CASE WHEN COALESCE(task_definitions.admin_overridden, FALSE)
                                       THEN task_definitions.reward ELSE $6 END""",
                    cid, i, title, metric, goal, reward, tname)


async def count_chains(pool):
    async with pool.acquire() as con:
        return await con.fetchval("SELECT count(*) FROM task_chains") or 0


# ---------------- Admin: Mission Rewards editor ----------------
async def admin_list_tasks(pool):
    async with pool.acquire() as con:
        rows = await con.fetch(
            "SELECT td.id, td.title, td.goal, td.metric, td.reward, td.active, "
            "td.legendary_admin_only, tc.name AS chain, tc.icon, tc.sort "
            "FROM task_definitions td JOIN task_chains tc ON tc.id=td.chain_id "
            "ORDER BY tc.sort, td.tier_index")
    return [dict(r) for r in rows]


async def admin_set_reward(pool, task_id, reward):
    """Set a task reward, enforcing the hard cap server-side. Marks it admin_overridden
    so the boot re-seed won't reset it."""
    async with pool.acquire() as con:
        leg = await con.fetchval(
            "SELECT legendary_admin_only FROM task_definitions WHERE id=$1", task_id)
        if leg is None:
            return None
        r = clamp_reward(reward, bool(leg))
        await con.execute(
            "UPDATE task_definitions SET reward=$1, admin_overridden=TRUE WHERE id=$2", r, task_id)
    return r


async def admin_set_active(pool, task_id, active):
    async with pool.acquire() as con:
        await con.execute("UPDATE task_definitions SET active=$1 WHERE id=$2", bool(active), task_id)
    return bool(active)


# ---------------- Metrics (server-side truth) ----------------
async def _metrics(pool, user_id):
    async with pool.acquire() as con:
        ts = await con.fetchrow("SELECT total_taps, best_combo FROM tap_state WHERE user_id=$1", user_id)
        taps = (ts["total_taps"] if ts else 0) or 0
        surge = (ts["best_combo"] if ts else 0) or 0
        upg = {r["code"]: r["level"] for r in await con.fetch(
            "SELECT code, level FROM user_upgrades WHERE user_id=$1", user_id)}
        messages = await con.fetchval(
            "SELECT count(*) FROM group_activity WHERE user_id=$1 AND kind='message' AND scored", user_id) or 0
        replies = await con.fetchval(
            "SELECT count(*) FROM group_activity WHERE user_id=$1 AND kind='reply' AND scored", user_id) or 0
        discussion = await con.fetchval(
            "SELECT count(*) FROM group_activity WHERE user_id=$1 AND kind='discussion' AND scored", user_id) or 0
        quiz_attempts = await con.fetchval(
            "SELECT count(*) FROM quiz_attempts WHERE user_id=$1", user_id) or 0
        quiz_correct = await con.fetchval(
            "SELECT count(*) FROM quiz_attempts WHERE user_id=$1 AND correct", user_id) or 0
        login_streak = await con.fetchval("SELECT streak_count FROM users WHERE id=$1", user_id) or 0
        puzzles = await con.fetchval(
            "SELECT count(DISTINCT puzzle_id) FROM puzzle_attempts WHERE user_id=$1 AND correct", user_id) or 0
        puzzles_leg = await con.fetchval(
            """SELECT count(DISTINCT a.puzzle_id) FROM puzzle_attempts a JOIN puzzles p ON p.id=a.puzzle_id
               WHERE a.user_id=$1 AND a.correct AND p.difficulty='legendary'""", user_id) or 0
        referrals = await con.fetchval(
            "SELECT count(*) FROM referrals WHERE referrer_id=$1 AND status='activated'", user_id) or 0
        points = await con.fetchval("SELECT points FROM users WHERE id=$1", user_id) or 0
        plats = {r["platform"] for r in await con.fetch(
            "SELECT DISTINCT platform FROM proof_submissions WHERE user_id=$1 AND status='approved'", user_id)}
    return {
        "taps": taps, "surge": surge,
        "reactor_core": upg.get("reactor_core", 0), "battery_pack": upg.get("battery_pack", 0),
        "solar_amplifier": upg.get("solar_amplifier", 0), "quantum_reactor": upg.get("quantum_reactor", 0),
        "messages": messages, "replies": replies, "discussion": discussion,
        "quiz_attempts": quiz_attempts, "quiz_correct": quiz_correct, "login_streak": login_streak,
        "puzzles": puzzles, "puzzles_legendary": puzzles_leg, "referrals": referrals,
        "level": economy.level_for(points),
        "social_telegram_official": 1 if "telegram_official" in plats else 0,
        "social_telegram_global": 1 if "telegram_global" in plats else 0,
        "social_x": 1 if "x" in plats else 0,
        "social_youtube": 1 if "youtube" in plats else 0,
        "social_instagram": 1 if "instagram" in plats else 0,
        "social_proof": 1 if plats else 0,
        "social_count": len(plats),
    }


# ---------------- List ----------------
async def list_chains(pool, user_id):
    m = await _metrics(pool, user_id)
    async with pool.acquire() as con:
        chains = await con.fetch("SELECT * FROM task_chains WHERE active ORDER BY sort")
        defs = await con.fetch("SELECT * FROM task_definitions WHERE active ORDER BY chain_id, tier_index")
        claimed = {r["task_id"] for r in await con.fetch(
            "SELECT task_id FROM task_claims WHERE user_id=$1", user_id)}

    by_chain = {}
    for d in defs:
        by_chain.setdefault(d["chain_id"], []).append(d)

    out, total_tasks, total_done = [], 0, 0
    for ch in chains:
        tiers = by_chain.get(ch["id"], [])
        tasks, active_found = [], False
        for d in tiers:
            cur = m.get(d["metric"], 0)
            is_claimed = d["id"] in claimed
            done = cur >= d["goal"]
            if ch["sequential"]:
                if is_claimed:
                    status = "completed"
                elif not active_found:
                    status = "claimable" if done else "active"
                    active_found = True
                else:
                    status = "locked"
            else:
                status = "completed" if is_claimed else ("claimable" if done else "active")
            total_tasks += 1
            if is_claimed:
                total_done += 1
            tasks.append({
                "id": d["id"], "tier_index": d["tier_index"], "title": d["title"],
                "tier_name": d["tier_name"], "metric": d["metric"], "goal": d["goal"],
                "reward": d["reward"], "progress": min(cur, d["goal"]),
                "status": status, "claimed": is_claimed})
        if ch["sequential"]:
            visible = [t for t in tasks if t["status"] in ("completed", "claimable", "active")]
            locked = [t for t in tasks if t["status"] == "locked"]
            if locked:
                visible.append({**locked[0], "title": "🔒 " + locked[0]["title"]})
            tasks = visible
        if ch["hidden"] and not any(t["status"] in ("claimable", "completed") for t in tasks):
            continue
        out.append({"code": ch["code"], "name": ch["name"], "category": ch["category"],
                    "icon": ch["icon"], "sequential": ch["sequential"], "period": ch["period"],
                    "tasks": tasks})
    pct = round(100 * total_done / total_tasks) if total_tasks else 0
    return {"chains": out, "completion_percent": pct, "completed": total_done, "total": total_tasks}


# ---------------- Claim ----------------
async def claim(pool, redis, user_id, task_id):
    async with pool.acquire() as con:
        d = await con.fetchrow("SELECT * FROM task_definitions WHERE id=$1 AND active", task_id)
        if not d:
            return {"error": "not_found"}
        ch = await con.fetchrow("SELECT * FROM task_chains WHERE id=$1", d["chain_id"])
        if await con.fetchval("SELECT 1 FROM task_claims WHERE user_id=$1 AND task_id=$2", user_id, task_id):
            return {"error": "already_claimed"}
        if ch["sequential"]:
            prev = await con.fetchval(
                """SELECT count(*) FROM task_definitions td WHERE td.chain_id=$1 AND td.tier_index < $2
                     AND td.id NOT IN (SELECT task_id FROM task_claims WHERE user_id=$3)""",
                d["chain_id"], d["tier_index"], user_id)
            if prev > 0:
                return {"error": "locked"}

    m = await _metrics(pool, user_id)
    if m.get(d["metric"], 0) < d["goal"]:
        return {"error": "incomplete", "progress": m.get(d["metric"], 0), "goal": d["goal"]}

    # Hard cap enforced again at claim time (defends against any stale/oversized DB value).
    reward = clamp_reward(d["reward"], bool(d.get("legendary_admin_only")))
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO task_claims(user_id, task_id, reward) VALUES($1,$2,$3) ON CONFLICT DO NOTHING",
            user_id, task_id, reward)
    # Idempotent: ref_id is unique per (user, task) so a re-claim never double-pays.
    # award_points may level the user up but NEVER awards extra XP for leveling (no loop).
    await economy.award_points(pool, user_id, reward, "task", f"task:{task_id}:{user_id}", redis=redis)

    unlocked = None
    if ch["sequential"] and ch["prestige"]:
        unlocked = await _maybe_prestige(pool, ch["id"], d)
    return {"ok": True, "reward": reward, "tier_name": d["tier_name"],
            "title": d["title"], "new_tier": unlocked}


async def _maybe_prestige(pool, chain_id, last_def):
    async with pool.acquire() as con:
        maxidx = await con.fetchval("SELECT max(tier_index) FROM task_definitions WHERE chain_id=$1", chain_id)
        if last_def["tier_index"] != maxidx:
            return None
        new_idx = maxidx + 1
        goal = int(last_def["goal"] * 3)
        # Prestige goals keep growing, but rewards STAY capped (no reward inflation).
        reward = clamp_reward(int(last_def["reward"]) + 50)
        verb = {"taps": "Validate", "surge": "Reach x", "messages": "Send",
                "quiz_correct": "Answer", "puzzles": "Solve", "replies": "Reply to",
                "discussion": "Participate"}.get(last_def["metric"], "Reach")
        title = f"Prestige: {verb} {goal:,}".replace("Reach x", "Reach x")
        await con.execute(
            """INSERT INTO task_definitions(chain_id,tier_index,title,metric,goal,reward,tier_name)
               VALUES($1,$2,$3,$4,$5,$6,'Reactor Oracle') ON CONFLICT (chain_id,tier_index) DO NOTHING""",
            chain_id, new_idx, title, last_def["metric"], goal, reward)
    return {"title": title, "goal": goal, "reward": reward}
