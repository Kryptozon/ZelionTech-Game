"""Quiz game logic: serve next question, score answers, history, admin review."""
import json
from . import economy

WRONG_COOLDOWN_SEC = 30
BASE_POINTS_PER_DIFFICULTY = 10   # difficulty 3 => 30 pts
STREAK_BONUS = 5                  # per consecutive correct, capped
STREAK_CAP = 5


def _opts(row):
    o = row["options"]
    return json.loads(o) if isinstance(o, str) else o


async def next_question(pool, redis, user_id: int):
    """Pick an approved question at/below the user's unlocked difficulty, not yet attempted."""
    cd = await redis.ttl(f"quizcd:{user_id}")
    if cd and cd > 0:
        return {"cooldown": cd}

    async with pool.acquire() as con:
        level = await con.fetchval("SELECT level FROM users WHERE id=$1", user_id) or 1
        row = await con.fetchrow(
            """SELECT * FROM quiz_questions
               WHERE status='approved' AND difficulty <= $2
                 AND id NOT IN (SELECT question_id FROM quiz_attempts WHERE user_id=$1)
               ORDER BY difficulty DESC, times_asked ASC, random() LIMIT 1""",
            user_id, level,
        )
        if not row:
            # fall back to least-asked approved question (allow repeats if exhausted)
            row = await con.fetchrow(
                """SELECT * FROM quiz_questions WHERE status='approved' AND difficulty <= $1
                   ORDER BY times_asked ASC, random() LIMIT 1""",
                level,
            )
        if not row:
            return {"empty": True}

        await con.execute("UPDATE quiz_questions SET times_asked = times_asked + 1 WHERE id=$1", row["id"])

    reward = row["difficulty"] * BASE_POINTS_PER_DIFFICULTY
    return {
        "id": row["id"],
        "question": row["question"],
        "options": _opts(row),
        "difficulty": row["difficulty"],
        "reward": reward,
        "source_url": row["source_url"],
        "unlocked_level": level,
    }


async def submit_answer(pool, redis, user_id: int, question_id: int, chosen_index: int):
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
    awarded = 0
    streak = 0

    if correct:
        streak = await redis.incr(f"quizstreak:{user_id}")
        await redis.expire(f"quizstreak:{user_id}", 86400)
        bonus = min(streak, STREAK_CAP) * STREAK_BONUS
        base = q["difficulty"] * BASE_POINTS_PER_DIFFICULTY
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
               VALUES($1,$2,$3,$4,$5)
               ON CONFLICT (user_id, question_id) DO NOTHING""",
            user_id, question_id, chosen_index, correct, awarded,
        )

    return {
        "correct": correct,
        "correct_index": q["correct_index"],
        "awarded": awarded,
        "streak": streak,
        "explanation": q["explanation"],
        "source_url": q["source_url"],
        "cooldown": 0 if correct else WRONG_COOLDOWN_SEC,
        "leveled": res.get("leveled", False),
        "level": res.get("level"),
    }


async def history(pool, user_id: int, limit=20):
    async with pool.acquire() as con:
        rows = await con.fetch(
            """SELECT a.correct, a.awarded, a.created_at, q.question, q.difficulty, q.source_url
               FROM quiz_attempts a JOIN quiz_questions q ON q.id=a.question_id
               WHERE a.user_id=$1 ORDER BY a.created_at DESC LIMIT $2""",
            user_id, limit,
        )
    return [dict(r) for r in rows]


# ---------------- Admin ----------------
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


async def manual_add(pool, question, options, correct_index, explanation, difficulty, source_url, admin_id):
    async with pool.acquire() as con:
        qid = await con.fetchval(
            """INSERT INTO quiz_questions
               (question, options, correct_index, explanation, difficulty, source_url, status, created_by)
               VALUES($1,$2,$3,$4,$5,$6,'approved','admin') RETURNING id""",
            question, json.dumps(options), correct_index, explanation, difficulty, source_url,
        )
    return qid


async def analytics(pool):
    async with pool.acquire() as con:
        total = await con.fetchval("SELECT count(*) FROM quiz_questions")
        approved = await con.fetchval("SELECT count(*) FROM quiz_questions WHERE status='approved'")
        pending = await con.fetchval("SELECT count(*) FROM quiz_questions WHERE status='pending'")
        attempts_24h = await con.fetchval(
            "SELECT count(*) FROM quiz_attempts WHERE created_at > now() - interval '1 day'"
        )
        accuracy = await con.fetchval(
            "SELECT round(100.0*avg(case when correct then 1 else 0 end),1) FROM quiz_attempts "
            "WHERE created_at > now() - interval '7 days'"
        )
    return {"total": total, "approved": approved, "pending": pending,
            "attempts_24h": attempts_24h, "accuracy_7d": accuracy}
