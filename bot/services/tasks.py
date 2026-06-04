"""Progressive / infinite task chains. Server-authoritative: progress is computed
from real metrics, claims are validated, and finished chains auto-generate harder
prestige tiers so there is always something to do (designed for 6–12 months)."""
from . import economy

TIER_LADDER = ["Bronze", "Silver", "Gold", "Platinum", "Diamond",
               "Reactor Elite", "Reactor Legend", "Reactor Oracle"]


def _tier_name(idx):
    return TIER_LADDER[idx - 1] if 1 <= idx <= len(TIER_LADDER) else "Reactor Oracle"


# chain: (code, name, category, icon, sequential, prestige, [ (title, metric, goal, reward) ... ])
CHAINS = [
    ("reactor_validation", "Reactor Validation", "reactor", "⚛️", True, True, [
        ("Validate 1,000 taps", "taps", 1000, 100),
        ("Validate 5,000 taps", "taps", 5000, 250),
        ("Validate 15,000 taps", "taps", 15000, 500),
        ("Validate 50,000 taps", "taps", 50000, 1000),
        ("Validate 100,000 taps", "taps", 100000, 2000),
        ("Validate 250,000 taps", "taps", 250000, 5000),
        ("Validate 500,000 taps", "taps", 500000, 10000),
        ("Validate 1,000,000 taps", "taps", 1000000, 25000),
    ]),
    ("power_surge", "Power Surge", "reactor", "⚡", True, True, [
        ("Reach x10 Surge", "surge", 10, 100),
        ("Reach x25 Surge", "surge", 25, 250),
        ("Reach x50 Surge", "surge", 50, 500),
        ("Reach x100 Surge", "surge", 100, 1000),
        ("Reach x250 Surge", "surge", 250, 2500),
        ("Reach x500 Surge", "surge", 500, 5000),
    ]),
    ("reactor_core", "Reactor Core Mastery", "upgrade", "🔧", True, False, [
        ("Upgrade Reactor Core to Lv5", "reactor_core", 5, 250),
        ("Upgrade Reactor Core to Lv10", "reactor_core", 10, 500),
        ("Upgrade Reactor Core to Lv20", "reactor_core", 20, 1500),
        ("Upgrade Reactor Core to Lv30", "reactor_core", 30, 3000),
        ("Upgrade Reactor Core to Lv50", "reactor_core", 50, 10000),
    ]),
    ("community", "Community Voice", "community", "💬", True, True, [
        ("Send 25 valid messages", "messages", 25, 100),
        ("Send 100 valid messages", "messages", 100, 300),
        ("Send 500 valid messages", "messages", 500, 1000),
        ("Send 1,000 valid messages", "messages", 1000, 2500),
        ("Send 5,000 valid messages", "messages", 5000, 10000),
        ("Send 10,000 valid messages", "messages", 10000, 25000),
    ]),
    ("quiz", "Quiz Scholar", "quiz", "🧠", True, True, [
        ("25 Correct Answers", "quiz_correct", 25, 250),
        ("100 Correct Answers", "quiz_correct", 100, 1000),
        ("250 Correct Answers", "quiz_correct", 250, 3000),
        ("500 Correct Answers", "quiz_correct", 500, 7500),
        ("1,000 Correct Answers", "quiz_correct", 1000, 20000),
    ]),
    ("puzzle", "Intelligence Solver", "puzzle", "🧩", True, True, [
        ("Solve 10 Puzzles", "puzzles", 10, 500),
        ("Solve 50 Puzzles", "puzzles", 50, 2000),
        ("Solve 100 Puzzles", "puzzles", 100, 5000),
        ("Solve 200 Puzzles", "puzzles", 200, 15000),
    ]),
    ("social", "Social Operator", "social", "📡", False, False, [
        ("Join Telegram Channel", "social_telegram_official", 1, 30),
        ("Join Telegram Group", "social_telegram_global", 1, 35),
        ("Submit Proof", "social_proof", 1, 50),
        ("Follow X", "social_x", 1, 50),
        ("Subscribe YouTube", "social_youtube", 1, 50),
    ]),
    ("elite", "Elite Reactor Missions", "elite", "🏅", True, False, [
        ("Reach Reactor Cadet", "level", 2, 500),
        ("Reach Reactor Operator", "level", 4, 2500),
        ("Reach Reactor Engineer", "level", 6, 10000),
        ("Reach Reactor Commander", "level", 8, 50000),
        ("Reach Reactor Oracle", "level", 10, 250000),
    ]),
    # Hidden achievement (revealed only when claimable).
    ("hidden_nightowl", "Hidden: Reactor Insomniac", "hidden", "🦉", False, False, [
        ("Solve 25 puzzles (secret)", "puzzles", 25, 1000),
    ]),
]


async def ensure_seed(pool):
    async with pool.acquire() as con:
        for sort, (code, name, cat, icon, seq, prestige, tiers) in enumerate(CHAINS):
            hidden = code.startswith("hidden_")
            cid = await con.fetchval(
                """INSERT INTO task_chains(code,name,category,icon,sequential,prestige,hidden,sort)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8)
                   ON CONFLICT (code) DO UPDATE SET name=$2 RETURNING id""",
                code, name, cat, icon, seq, prestige, hidden, sort)
            for i, (title, metric, goal, reward) in enumerate(tiers, start=1):
                await con.execute(
                    """INSERT INTO task_definitions(chain_id,tier_index,title,metric,goal,reward,tier_name)
                       VALUES($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (chain_id,tier_index) DO NOTHING""",
                    cid, i, title, metric, goal, reward, _tier_name(i))


async def count_chains(pool):
    async with pool.acquire() as con:
        return await con.fetchval("SELECT count(*) FROM task_chains") or 0


# ---------------- Metrics (server-side truth) ----------------
async def _metrics(pool, user_id):
    async with pool.acquire() as con:
        taps = await con.fetchval("SELECT total_taps FROM tap_state WHERE user_id=$1", user_id) or 0
        surge = await con.fetchval("SELECT best_combo FROM tap_state WHERE user_id=$1", user_id) or 0
        core = await con.fetchval(
            "SELECT level FROM user_upgrades WHERE user_id=$1 AND code='reactor_core'", user_id) or 0
        messages = await con.fetchval(
            "SELECT count(*) FROM group_activity WHERE user_id=$1 AND kind='message' AND scored", user_id) or 0
        quiz_correct = await con.fetchval(
            "SELECT count(*) FROM quiz_attempts WHERE user_id=$1 AND correct", user_id) or 0
        puzzles = await con.fetchval(
            "SELECT count(DISTINCT puzzle_id) FROM puzzle_attempts WHERE user_id=$1 AND correct", user_id) or 0
        referrals = await con.fetchval(
            "SELECT count(*) FROM referrals WHERE referrer_id=$1 AND status='activated'", user_id) or 0
        points = await con.fetchval("SELECT points FROM users WHERE id=$1", user_id) or 0
        plats = {r["platform"] for r in await con.fetch(
            "SELECT DISTINCT platform FROM proof_submissions WHERE user_id=$1 AND status='approved'", user_id)}
    return {
        "taps": taps, "surge": surge, "reactor_core": core, "messages": messages,
        "quiz_correct": quiz_correct, "puzzles": puzzles, "referrals": referrals,
        "level": economy.level_for(points),
        "social_telegram_official": 1 if "telegram_official" in plats else 0,
        "social_telegram_global": 1 if "telegram_global" in plats else 0,
        "social_x": 1 if "x" in plats else 0,
        "social_youtube": 1 if "youtube" in plats else 0,
        "social_proof": 1 if plats else 0,
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
            status = "completed" if is_claimed else None
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
            # hide locked details for hidden chains
            tasks.append({
                "id": d["id"], "tier_index": d["tier_index"], "title": d["title"],
                "tier_name": d["tier_name"], "metric": d["metric"], "goal": d["goal"],
                "reward": d["reward"], "progress": min(cur, d["goal"]),
                "status": status, "claimed": is_claimed,
            })
        # In sequential chains, only surface up to (and incl.) the current active tier + completed.
        if ch["sequential"]:
            visible = [t for t in tasks if t["status"] in ("completed", "claimable", "active")]
            # include the immediate next locked tier as a teaser
            locked = [t for t in tasks if t["status"] == "locked"]
            if locked:
                visible.append({**locked[0], "title": "🔒 " + locked[0]["title"]})
            tasks = visible
        if ch["hidden"]:
            # only show hidden chain once its task is claimable/claimed
            if not any(t["status"] in ("claimable", "completed") for t in tasks):
                continue
        out.append({
            "code": ch["code"], "name": ch["name"], "category": ch["category"],
            "icon": ch["icon"], "sequential": ch["sequential"], "period": ch["period"],
            "tasks": tasks,
        })
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
        # sequential: all earlier tiers must be claimed
        if ch["sequential"]:
            prev = await con.fetchval(
                """SELECT count(*) FROM task_definitions td
                   WHERE td.chain_id=$1 AND td.tier_index < $2
                     AND td.id NOT IN (SELECT task_id FROM task_claims WHERE user_id=$3)""",
                d["chain_id"], d["tier_index"], user_id)
            if prev > 0:
                return {"error": "locked"}

    m = await _metrics(pool, user_id)
    if m.get(d["metric"], 0) < d["goal"]:
        return {"error": "incomplete", "progress": m.get(d["metric"], 0), "goal": d["goal"]}

    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO task_claims(user_id, task_id, reward) VALUES($1,$2,$3) ON CONFLICT DO NOTHING",
            user_id, task_id, d["reward"])
    await economy.award_points(pool, user_id, d["reward"], "task", f"task:{task_id}:{user_id}", redis=redis)

    # Infinite prestige: if this was the last tier of a prestige chain, generate the next.
    unlocked = None
    if ch["sequential"] and ch["prestige"]:
        unlocked = await _maybe_prestige(pool, ch["id"], d)
    return {"ok": True, "reward": d["reward"], "tier_name": d["tier_name"],
            "title": d["title"], "new_tier": unlocked}


async def _maybe_prestige(pool, chain_id, last_def):
    async with pool.acquire() as con:
        maxidx = await con.fetchval("SELECT max(tier_index) FROM task_definitions WHERE chain_id=$1", chain_id)
        if last_def["tier_index"] != maxidx:
            return None
        new_idx = maxidx + 1
        goal = int(last_def["goal"] * 3)
        reward = int(last_def["reward"] * 2)
        verb = {"taps": "Validate", "surge": "Reach x", "messages": "Send",
                "quiz_correct": "Answer", "puzzles": "Solve"}.get(last_def["metric"], "Reach")
        title = f"Prestige {new_idx - 7 if new_idx > 8 else ''}: {verb} {goal:,}".replace("  ", " ")
        await con.execute(
            """INSERT INTO task_definitions(chain_id,tier_index,title,metric,goal,reward,tier_name)
               VALUES($1,$2,$3,$4,$5,$6,'Reactor Oracle') ON CONFLICT (chain_id,tier_index) DO NOTHING""",
            chain_id, new_idx, title.strip(), last_def["metric"], goal, reward)
    return {"title": title.strip(), "goal": goal, "reward": reward}
