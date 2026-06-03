"""Quiz game logic: difficulty unlock, XP tiers, streak bonuses, ranks,
daily challenge, history, admin review."""
import json
import datetime as dt
from . import economy

WRONG_COOLDOWN_SEC = 30

# XP by difficulty tier (req #6): easy=5, medium=10, hard=20, expert=35
XP_BY_DIFF = {1: 5, 2: 10, 3: 20, 4: 35, 5: 35}

# Streak bonuses (req #7): 3->+10, 5->+25, 10->special rank (+big bonus)
STREAK_BONUS = {3: 10, 5: 25, 10: 50}

# Quiz ranks (req #8) by lifetime correct answers.
QUIZ_RANKS = [
    (0, "Reactor Cadet"),
    (10, "Energy Validator"),
    (30, "Grid Architect"),
    (75, "ZEV Operator"),
    (150, "Infrastructure Elite"),
    (300, "Zelion Master"),
]

DAILY_SIZE = 5
DAILY_BONUS = 50


def _opts(row):
    o = row["options"]
    return json.loads(o) if isinstance(o, str) else o


def _max_difficulty_for_level(level: int) -> int:
    return max(1, min(level, 4))   # L1->beginner ... L4+->expert


# ---------------- Ranks ----------------
def rank_for(correct_count: int):
    name, nxt = QUIZ_RANKS[0][1], None
    for i, (req, label) in enumerate(QUIZ_RANKS):
        if correct_count >= req:
            name = label
            nxt = QUIZ_RANKS[i + 1] if i + 1 < len(QUIZ_RANKS) else None
    return name, nxt


async def quiz_rank(pool, user_id):
    async with pool.acquire() as con:
        correct = await con.fetchval(
            "SELECT count(*) FROM quiz_attempts WHERE user_id=$1 AND correct", user_id
        ) or 0
    name, nxt = rank_for(correct)
    return {"correct": correct, "rank": name,
            "next_rank": (nxt[1] if nxt else None),
            "next_at": (nxt[0] if nxt else None)}


# ---------------- Serve ----------------
async def next_question(pool, redis, user_id):
    cd = await redis.ttl(f"quizcd:{user_id}")
    if cd and cd > 0:
        return {"cooldown": cd}

    async with pool.acquire() as con:
        level = await con.fetchval("SELECT level FROM users WHERE id=$1", user_id) or 1
        maxd = _max_difficulty_for_level(level)
        row = await con.fetchrow(
            """SELECT * FROM quiz_questions
               WHERE status='approved' AND difficulty <= $2
                 AND id NOT IN (SELECT question_id FROM quiz_attempts WHERE user_id=$1)
               ORDER BY difficulty DESC, times_asked ASC, random() LIMIT 1""",
            user_id, maxd,
        )
        if not row:
            row = await con.fetchrow(
                "SELECT * FROM quiz_questions WHERE status='approved' AND difficulty <= $1 "
                "ORDER BY times_asked ASC, random() LIMIT 1", maxd,
            )
        if not row:
            return {"empty": True}
        await con.execute("UPDATE quiz_questions SET times_asked=times_asked+1 WHERE id=$1", row["id"])

    return _question_payload(row, level)


def _question_payload(row, level):
    return {
        "id": row["id"], "question": row["question"], "options": _opts(row),
        "difficulty": row["difficulty"], "tier": row["tier"], "qtype": row["qtype"],
        "category": row["category"], "reward": XP_BY_DIFF.get(row["difficulty"], 10),
        "source_url": row["source_url"], "source_type": row["source_type"],
        "unlocked_level": level,
    }


# ---------------- Answer ----------------
async def submit_answer(pool, redis, user_id, question_id, chosen_index):
    async with pool.acquire() as con:
        q = await con.fetchrow("SELECT * FROM quiz_questions WHERE id=$1 AND status='approved'", question_id)
        if not q:
            return {"error": "question_not_found"}
        already = await con.fetchval(
            "SELECT correct FROM quiz_attempts WHERE user_id=$1 AND question_id=$2", user_id, question_id
        )
        if already is not None:
            return {"error": "already_answered"}

    correct = (chosen_index == q["correct_index"])
    base = XP_BY_DIFF.get(q["difficulty"], 10)
    awarded, streak, bonus, special = 0, 0, 0, False

    if correct:
        streak = await redis.incr(f"quizstreak:{user_id}")
        await redis.expire(f"quizstreak:{user_id}", 86400)
        bonus = STREAK_BONUS.get(streak, 0)
        if streak == 10:
            special = True
        awarded = base + bonus
        res = await economy.award_points(pool, user_id, awarded, "quiz_ai",
                                         f"q:{question_id}", redis=redis, surge=True)
    else:
        await redis.delete(f"quizstreak:{user_id}")
        await redis.set(f"quizcd:{user_id}", "1", ex=WRONG_COOLDOWN_SEC)
        res = {"leveled": False, "level": None}

    async with pool.acquire() as con:
        await con.execute(
            """INSERT INTO quiz_attempts(user_id, question_id, chosen_index, correct, awarded)
               VALUES($1,$2,$3,$4,$5) ON CONFLICT (user_id, question_id) DO NOTHING""",
            user_id, question_id, chosen_index, correct, awarded,
        )

    rank = await quiz_rank(pool, user_id)
    return {
        "correct": correct, "correct_index": q["correct_index"],
        "base": base, "bonus": bonus, "awarded": awarded, "streak": streak, "special": special,
        "explanation": q["explanation"], "source_url": q["source_url"], "source_type": q["source_type"],
        "cooldown": 0 if correct else WRONG_COOLDOWN_SEC,
        "leveled": res.get("leveled", False), "level": res.get("level"),
        "rank": rank["rank"],
    }


# ---------------- Daily challenge ----------------
async def _todays_question_ids(pool):
    today = dt.date.today()
    async with pool.acquire() as con:
        row = await con.fetchval("SELECT question_ids FROM daily_challenges WHERE challenge_date=$1", today)
        if row:
            return json.loads(row) if isinstance(row, str) else row
        # Deterministic pick seeded by the date so everyone gets the same set.
        seed = int(today.strftime("%Y%m%d"))
        ids = [r["id"] for r in await con.fetch(
            "SELECT id FROM quiz_questions WHERE status='approved' "
            "ORDER BY (id * $1) % 100000, id LIMIT $2", seed, DAILY_SIZE,
        )]
        if ids:
            await con.execute(
                "INSERT INTO daily_challenges(challenge_date, question_ids) VALUES($1,$2) "
                "ON CONFLICT (challenge_date) DO NOTHING",
                today, json.dumps(ids),
            )
        return ids


async def daily_status(pool, redis, user_id):
    ids = await _todays_question_ids(pool)
    if not ids:
        return {"empty": True, "questions": []}
    async with pool.acquire() as con:
        level = await con.fetchval("SELECT level FROM users WHERE id=$1", user_id) or 1
        rows = await con.fetch("SELECT * FROM quiz_questions WHERE id = ANY($1::bigint[])", ids)
        answered = {r["question_id"]: r["correct"] for r in await con.fetch(
            "SELECT question_id, correct FROM quiz_attempts WHERE user_id=$1 AND question_id = ANY($2::bigint[])",
            user_id, ids,
        )}
    qs = []
    for r in sorted(rows, key=lambda x: ids.index(x["id"])):
        p = _question_payload(r, level)
        p["answered"] = r["id"] in answered
        p["was_correct"] = answered.get(r["id"])
        qs.append(p)

    done = all(q["answered"] for q in qs)
    key = f"dailydone:{user_id}:{dt.date.today()}"
    claimed = bool(await redis.get(key))
    reward = 0
    if done and not claimed:
        if await redis.set(key, "1", nx=True, ex=172800):
            await economy.award_points(pool, user_id, DAILY_BONUS, "quiz_daily",
                                       f"daily:{dt.date.today()}", redis=redis)
            reward = DAILY_BONUS
            claimed = True
    return {"date": str(dt.date.today()), "questions": qs, "completed": done,
            "bonus": DAILY_BONUS, "reward_just_paid": reward, "claimed": claimed}


# ---------------- History / admin ----------------
async def history(pool, user_id, limit=20):
    async with pool.acquire() as con:
        rows = await con.fetch(
            """SELECT a.correct, a.awarded, a.created_at, q.question, q.difficulty, q.tier,
                      q.qtype, q.category, q.source_url
               FROM quiz_attempts a JOIN quiz_questions q ON q.id=a.question_id
               WHERE a.user_id=$1 ORDER BY a.created_at DESC LIMIT $2""",
            user_id, limit,
        )
    return [dict(r) for r in rows]


async def admin_list(pool, status="pending", limit=50):
    async with pool.acquire() as con:
        return await con.fetch(
            "SELECT * FROM quiz_questions WHERE status=$1 ORDER BY created_at DESC LIMIT $2",
            status, limit,
        )


async def set_status(pool, qid, status, admin_id=None):
    async with pool.acquire() as con:
        await con.execute("UPDATE quiz_questions SET status=$1 WHERE id=$2", status, qid)
        if admin_id is not None:
            await con.execute(
                "INSERT INTO admin_actions(admin_id, action, target_id, detail) VALUES($1,$2,$3,$4)",
                admin_id, f"quiz_{status}", qid, "{}",
            )


async def analytics(pool):
    async with pool.acquire() as con:
        total = await con.fetchval("SELECT count(*) FROM quiz_questions")
        approved = await con.fetchval("SELECT count(*) FROM quiz_questions WHERE status='approved'")
        pending = await con.fetchval("SELECT count(*) FROM quiz_questions WHERE status='pending'")
        by_cat = await con.fetch(
            "SELECT category, count(*) c FROM quiz_questions WHERE status='approved' GROUP BY category ORDER BY c DESC"
        )
        attempts_24h = await con.fetchval(
            "SELECT count(*) FROM quiz_attempts WHERE created_at > now() - interval '1 day'"
        )
        accuracy = await con.fetchval(
            "SELECT round(100.0*avg(case when correct then 1 else 0 end),1) FROM quiz_attempts "
            "WHERE created_at > now() - interval '7 days'"
        )
    return {"total": total, "approved": approved, "pending": pending,
            "by_category": [dict(r) for r in by_cat],
            "attempts_24h": attempts_24h, "accuracy_7d": accuracy}
