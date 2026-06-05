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


def _released_hints(row):
    n = row.get("released_hints", 0) if isinstance(row, dict) else (row["released_hints"] or 0)
    hints = [row["hint1"], row["hint2"], row["hint3"]]
    return [h for h in hints[:n] if h]


def _public(row, solved=False):
    closed = (row["status"] in ("closed", "skipped")) if "status" in row else False
    d = {
        "id": row["id"], "title": row["title"], "question": row["question"],
        "difficulty": row["difficulty"], "reward": row["reward"], "penalty": row["penalty"],
        "category": row["category"], "source": row["source"],
        "youtube_instruction": row["youtube_instruction"],
        "telegram_instruction": row["telegram_instruction"],
        "solved": solved, "closed": closed,
        # Admin may "release" hints; only released ones are revealed to players.
        "released_hints": _released_hints(row),
        "youtube_posted": bool(row["youtube_posted"]) if "youtube_posted" in row else False,
        "telegram_posted": bool(row["telegram_posted"]) if "telegram_posted" in row else False,
    }
    if solved:
        d["explanation"] = row["explanation"]
    return d  # NOTE: answer / unreleased hints / scripts are never included


async def _pick_daily(con, difficulties=("easy", "medium", "hard"), table_date=None):
    d = table_date or _today()
    existing = await con.fetchval("SELECT puzzle_id FROM daily_puzzle_sessions WHERE session_date=$1", d)
    if existing:
        return existing
    ids = [r["id"] for r in await con.fetch(
        "SELECT id FROM puzzles WHERE active=true AND difficulty = ANY($1::text[]) ORDER BY id",
        list(difficulties))]
    if not ids:
        return None
    idx = int(d.strftime("%Y%m%d")) % len(ids)
    pid = ids[idx]
    await con.execute(
        "INSERT INTO daily_puzzle_sessions(session_date, puzzle_id) VALUES($1,$2) "
        "ON CONFLICT (session_date) DO NOTHING", d, pid)
    return pid


async def daily(pool, redis, user_id):
    async with pool.acquire() as con:
        pid = await _pick_daily(con)
        if not pid:
            return {"empty": True}
        row = await con.fetchrow("SELECT * FROM puzzles WHERE id=$1", pid)
        solved = await con.fetchval(
            "SELECT 1 FROM puzzle_attempts WHERE user_id=$1 AND puzzle_id=$2 AND correct", user_id, pid)
    cd = await redis.ttl(f"pzcd:{user_id}:{pid}")
    wrong = int(await redis.get(f"pzwrong:{user_id}:{pid}") or 0)
    out = _public(row, solved=bool(solved))
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
    async with pool.acquire() as con:
        row = await con.fetchrow("SELECT * FROM puzzles WHERE id=$1 AND active=true", puzzle_id)
        if not row:
            return {"error": "not_found"}
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
    """status: active | closed | skipped. Closed/skipped puzzles are permanently removed
    from rotation (scarcity — no retroactive rewards)."""
    active = (status == "active")
    async with pool.acquire() as con:
        await con.execute("UPDATE puzzles SET status=$1, active=$2 WHERE id=$3", status, active, puzzle_id)


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
