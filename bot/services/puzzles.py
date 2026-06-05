"""Zelion Intelligence puzzle game logic. Server-authoritative; answers never sent
to users. Anti-cheat: 5 wrong attempts/puzzle -> 15-min cooldown."""
import re
import datetime as dt
from . import economy

MAX_WRONG = 5
COOLDOWN_SEC = 900       # 15 min after too many wrong


def _norm(s):
    return re.sub(r"[^A-Z0-9]", "", str(s or "").upper())


def _today():
    return dt.date.today()


def _released_hint_count(row):
    """How many hints the admin has announced. We NEVER send hint TEXT to users —
    real hints live only on YouTube/TikTok; the app only announces a release count."""
    n = row.get("released_hints", 0) if isinstance(row, dict) else (row["released_hints"] or 0)
    hints = [row["hint1"], row["hint2"], row["hint3"]]
    return sum(1 for h in hints[:n] if h)


def _public(row, solved=False):
    closed = (row["status"] in ("closed", "skipped")) if "status" in row else False
    d = {
        "id": row["id"], "title": row["title"], "question": row["question"],
        "difficulty": row["difficulty"], "reward": row["reward"], "penalty": row["penalty"],
        "category": row["category"], "source": row["source"],
        "youtube_instruction": row["youtube_instruction"],
        "telegram_instruction": row["telegram_instruction"],
        "solved": solved, "closed": closed,
        # Only the COUNT of admin-announced hints — never the hint text itself.
        "released_hints": _released_hint_count(row),
        "youtube_posted": bool(row["youtube_posted"]) if "youtube_posted" in row else False,
        "telegram_posted": bool(row["telegram_posted"]) if "telegram_posted" in row else False,
    }
    if solved:
        d["explanation"] = row["explanation"]
    return d  # NOTE: answer / unreleased hints / scripts are never included


async def get_setting(pool, key, default=None):
    async with pool.acquire() as con:
        v = await con.fetchval("SELECT value FROM game_settings WHERE key=$1", key)
    return v if v is not None else default


async def set_setting(pool, key, value):
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO game_settings(key,value) VALUES($1,$2) "
            "ON CONFLICT (key) DO UPDATE SET value=$2", key, str(value))


async def daily(pool, redis, user_id):
    """Shows ONLY the puzzle an admin has manually released (the active pointer).
    Never auto-releases. One active puzzle at a time."""
    pid = await get_setting(pool, "active_puzzle")
    if not pid:
        return {"waiting": True, "message": "Waiting for admin to release the next puzzle."}
    pid = int(pid)
    async with pool.acquire() as con:
        row = await con.fetchrow("SELECT * FROM puzzles WHERE id=$1", pid)
        if not row:
            return {"waiting": True, "message": "Waiting for admin to release the next puzzle."}
        solved = await con.fetchval(
            "SELECT 1 FROM puzzle_attempts WHERE user_id=$1 AND puzzle_id=$2 AND correct", user_id, pid)
    if row["status"] == "skipped":
        return {"missed": True, "message": "❌ Puzzle Missed — this puzzle is no longer available."}
    cd = await redis.ttl(f"pzcd:{user_id}:{pid}")
    wrong = int(await redis.get(f"pzwrong:{user_id}:{pid}") or 0)
    out = _public(row, solved=bool(solved))   # _public marks 'closed' for closed/skipped status
    out["attempts_remaining"] = max(0, MAX_WRONG - wrong)
    out["cooldown_seconds"] = cd if cd and cd > 0 else 0
    return out


async def weekly(pool, redis, user_id):
    """Weekly Mystery Hunt — a legendary puzzle, rotates weekly."""
    async with pool.acquire() as con:
        ids = [r["id"] for r in await con.fetch(
            "SELECT id FROM puzzles WHERE active=true AND difficulty='legendary' ORDER BY id")]
        if not ids:
            return {"empty": True}
        wk = int(_today().strftime("%G%V")) % len(ids)
        row = await con.fetchrow("SELECT * FROM puzzles WHERE id=$1", ids[wk])
        solved = await con.fetchval(
            "SELECT 1 FROM puzzle_attempts WHERE user_id=$1 AND puzzle_id=$2 AND correct",
            user_id, row["id"])
    cd = await redis.ttl(f"pzcd:{user_id}:{row['id']}")
    wrong = int(await redis.get(f"pzwrong:{user_id}:{row['id']}") or 0)
    out = _public(row, solved=bool(solved))
    out["attempts_remaining"] = max(0, MAX_WRONG - wrong)
    out["cooldown_seconds"] = cd if cd and cd > 0 else 0
    return out


async def answer(pool, redis, user_id, puzzle_id, text):
    # Only the currently-released active puzzle can be answered.
    active = await get_setting(pool, "active_puzzle")
    if not active or int(active) != int(puzzle_id):
        return {"error": "not_active"}
    async with pool.acquire() as con:
        row = await con.fetchrow("SELECT * FROM puzzles WHERE id=$1", puzzle_id)
        if not row or row["status"] in ("closed", "skipped"):
            return {"error": "closed"}
        solved = await con.fetchval(
            "SELECT 1 FROM puzzle_attempts WHERE user_id=$1 AND puzzle_id=$2 AND correct", user_id, puzzle_id)
        if solved:
            return {"error": "already_solved"}

    if (await redis.ttl(f"pzcd:{user_id}:{puzzle_id}") or 0) > 0:
        cd = await redis.ttl(f"pzcd:{user_id}:{puzzle_id}")
        return {"error": "cooldown", "cooldown_seconds": cd}

    accepted = {_norm(row["answer"])}
    if row["accepted_variations"]:
        accepted |= {_norm(v) for v in row["accepted_variations"].split(",") if v.strip()}
    correct = _norm(text) in accepted
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO puzzle_attempts(user_id, puzzle_id, answer_text, correct, awarded) "
            "VALUES($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING",
            user_id, puzzle_id, str(text)[:120], correct, row["reward"] if correct else 0)

    if correct:
        await redis.delete(f"pzwrong:{user_id}:{puzzle_id}")
        await economy.award_points(pool, user_id, row["reward"], "puzzle",
                                   f"pz:{puzzle_id}:{user_id}", redis=redis)
        return {"correct": True, "awarded": row["reward"], "explanation": row["explanation"],
                "source": row["source"]}

    # wrong -> penalty + attempt tracking
    d = await economy.deduct_points(pool, user_id, row["penalty"], "puzzle_penalty",
                                    f"pzp:{puzzle_id}:{user_id}:{dt.datetime.utcnow().timestamp()}")
    wrong = await redis.incr(f"pzwrong:{user_id}:{puzzle_id}")
    await redis.expire(f"pzwrong:{user_id}:{puzzle_id}", 86400)
    locked = False
    if wrong >= MAX_WRONG:
        locked = True
        await redis.set(f"pzcd:{user_id}:{puzzle_id}", "1", ex=COOLDOWN_SEC)
    return {"correct": False, "penalty": d["deducted"],
            "attempts_remaining": max(0, MAX_WRONG - wrong), "locked": locked,
            "cooldown_seconds": COOLDOWN_SEC if locked else 0}


async def status(pool, redis, user_id):
    d = await daily(pool, redis, user_id)
    return {"solved": d.get("solved", False), "attempts_remaining": d.get("attempts_remaining", MAX_WRONG),
            "cooldown_seconds": d.get("cooldown_seconds", 0), "puzzle_id": d.get("id")}


async def history(pool, user_id, limit=20):
    async with pool.acquire() as con:
        rows = await con.fetch(
            """SELECT a.correct, a.awarded, a.created_at, p.title, p.difficulty, p.category
               FROM puzzle_attempts a JOIN puzzles p ON p.id=a.puzzle_id
               WHERE a.user_id=$1 ORDER BY a.created_at DESC LIMIT $2""", user_id, limit)
    return [dict(r) for r in rows]


async def leaderboard(pool, period="week", limit=10):
    window = {"week": "a.created_at >= date_trunc('week', now())",
              "month": "a.created_at >= date_trunc('month', now())"}.get(period, "true")
    async with pool.acquire() as con:
        rows = await con.fetch(
            f"""SELECT a.user_id, COALESCE(u.username, u.first_name, a.user_id::text) AS name,
                       SUM(a.awarded) AS score
                FROM puzzle_attempts a LEFT JOIN users u ON u.id=a.user_id
                WHERE a.correct AND {window}
                GROUP BY a.user_id, u.username, u.first_name ORDER BY score DESC LIMIT $1""", limit)
    return [{"name": r["name"], "score": int(r["score"] or 0)} for r in rows]


# ---------------- Admin ----------------
async def admin_list(pool, difficulty=None, limit=300):
    async with pool.acquire() as con:
        if difficulty:
            return [dict(r) for r in await con.fetch(
                "SELECT * FROM puzzles WHERE difficulty=$1 ORDER BY id LIMIT $2", difficulty, limit)]
        return [dict(r) for r in await con.fetch("SELECT * FROM puzzles ORDER BY id LIMIT $1", limit)]


async def set_active(pool, puzzle_id, active):
    async with pool.acquire() as con:
        await con.execute("UPDATE puzzles SET active=$1, status=$2 WHERE id=$3",
                          active, "active" if active else "closed", puzzle_id)


async def set_status(pool, puzzle_id, status):
    """status: active | closed | skipped. Keeps the active pointer so users see the
    Closed/Missed state until a new puzzle is released."""
    active = (status == "active")
    async with pool.acquire() as con:
        await con.execute("UPDATE puzzles SET status=$1, active=$2 WHERE id=$3", status, active, puzzle_id)


async def release_puzzle(pool, puzzle_id):
    """Manually make THIS puzzle the single live puzzle (admin only)."""
    async with pool.acquire() as con:
        # demote any previously-active puzzle so only one is live at a time
        await con.execute("UPDATE puzzles SET active=false WHERE status='active' AND id<>$1", puzzle_id)
        await con.execute("UPDATE puzzles SET status='active', active=true WHERE id=$1", puzzle_id)
    await set_setting(pool, "active_puzzle", puzzle_id)


async def admin_overview(pool):
    async with pool.acquire() as con:
        active = await con.fetchval("SELECT value FROM game_settings WHERE key='active_puzzle'")
        by_status = {r["status"]: r["c"] for r in await con.fetch(
            "SELECT status, count(*) c FROM puzzles GROUP BY status")}
        solved = await con.fetchval("SELECT count(*) FROM puzzle_attempts WHERE correct") or 0
        attempts = await con.fetchval("SELECT count(*) FROM puzzle_attempts") or 0
        active_title = None
        if active:
            active_title = await con.fetchval("SELECT title FROM puzzles WHERE id=$1", int(active))
    return {"active_puzzle": int(active) if active else None, "active_title": active_title,
            "by_status": by_status, "solved": solved, "missed": max(0, attempts - solved)}


async def release_hint(pool, puzzle_id, n):
    n = max(0, min(3, int(n)))
    async with pool.acquire() as con:
        await con.execute("UPDATE puzzles SET released_hints=GREATEST(released_hints,$1) WHERE id=$2",
                          n, puzzle_id)


async def mark_posted(pool, puzzle_id, platform):
    col = "youtube_posted" if platform == "youtube" else "telegram_posted"
    async with pool.acquire() as con:
        await con.execute(f"UPDATE puzzles SET {col}=true WHERE id=$1", puzzle_id)


async def get_hints(pool, puzzle_id):
    async with pool.acquire() as con:
        r = await con.fetchrow("SELECT * FROM puzzle_hints WHERE puzzle_id=$1", puzzle_id)
        a = await con.fetchval("SELECT answer FROM puzzles WHERE id=$1", puzzle_id)
    return {**(dict(r) if r else {}), "answer": a}


async def get_script(pool, puzzle_id):
    async with pool.acquire() as con:
        r = await con.fetchrow("SELECT * FROM puzzle_scripts WHERE puzzle_id=$1", puzzle_id)
    return dict(r) if r else {}
