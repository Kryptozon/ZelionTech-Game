"""Daily quiz system: 5 questions / 24h, level-scaled difficulty, no-repeat,
ZLN-XP rewards, streak bonuses, ranks, countdown. Server-authoritative."""
import json
import random
import datetime as dt
from . import economy


def answer_order(question_id, user_id, n):
    """Deterministic per-(question,user) permutation so the correct answer is
    randomly placed across A/B/C/D (not always option A). Reproducible on serve,
    reveal, and answer validation — no DB write needed. shuffled[i] = original[order[i]]."""
    seed = (int(question_id) * 1000003) ^ ((int(user_id) * 2654435761) & 0xFFFFFFFF)
    rnd = random.Random(seed)
    order = list(range(n))
    rnd.shuffle(order)
    return order

WRONG_COOLDOWN_SEC = 0          # daily model: no per-wrong cooldown, just no reward
DAILY_SIZE = 5
SESSION_HOURS = 24

# Flat reward/penalty per spec: correct +20 XP, wrong -10 XP.
XP_BY_DIFF = {1: 20, 2: 20, 3: 20, 4: 20, 5: 20}
STREAK_BONUS = {5: 10, 10: 25, 25: 100}        # 5/10/25 correct in a row
WRONG_PENALTY = 10                              # -10 ZLN-XP per wrong (never below 0)
WRONG_STREAK_LIMIT = 5                          # 5 wrong in a row -> training required
TRAINING_COOLDOWN_SEC = 300

QUIZ_RANKS = [
    (0, "Reactor Cadet"), (10, "Energy Validator"), (30, "Grid Architect"),
    (75, "ZEV Operator"), (150, "Infrastructure Elite"), (300, "Zelion Master"),
]


def _now():
    return dt.datetime.now(dt.timezone.utc)


def _allowed_difficulties(level: int):
    if level <= 2:
        return [1]
    if level <= 4:
        return [1, 2]
    if level <= 7:
        return [2, 3]
    return [3, 4]


def _opts(row):
    o = row["options"]
    return json.loads(o) if isinstance(o, str) else o


# ---------------- Ranks ----------------
def rank_for(correct_count):
    name, nxt = QUIZ_RANKS[0][1], None
    for i, (req, label) in enumerate(QUIZ_RANKS):
        if correct_count >= req:
            name = label
            nxt = QUIZ_RANKS[i + 1] if i + 1 < len(QUIZ_RANKS) else None
    return name, nxt


async def quiz_rank(pool, user_id):
    async with pool.acquire() as con:
        correct = await con.fetchval(
            "SELECT count(*) FROM quiz_attempts WHERE user_id=$1 AND correct", user_id) or 0
    name, nxt = rank_for(correct)
    return {"correct": correct, "rank": name,
            "next_rank": (nxt[1] if nxt else None), "next_at": (nxt[0] if nxt else None)}


# ---------------- Daily session ----------------
async def _pick_question_ids(con, user_id, level):
    diffs = _allowed_difficulties(level)
    rows = await con.fetch(
        """SELECT id FROM quiz_questions
           WHERE status='approved' AND active=true AND difficulty = ANY($2::int[])
             AND id NOT IN (SELECT question_id FROM quiz_attempts WHERE user_id=$1)
           ORDER BY difficulty ASC, random() LIMIT $3""",
        user_id, diffs, DAILY_SIZE,
    )
    ids = [r["id"] for r in rows]
    if len(ids) < DAILY_SIZE:
        # Fallback: any approved active (easier first), allow repeats if the pool is exhausted.
        extra = await con.fetch(
            """SELECT id FROM quiz_questions WHERE status='approved' AND active=true
               AND id <> ALL($2::bigint[]) ORDER BY difficulty ASC, random() LIMIT $3""",
            user_id, ids, DAILY_SIZE - len(ids),
        )
        ids += [r["id"] for r in extra]
    return ids[:DAILY_SIZE]


async def _get_or_create_session(con, user_id):
    sess = await con.fetchrow(
        "SELECT * FROM daily_quiz_sessions WHERE user_id=$1 AND expires_at > now() "
        "ORDER BY created_at DESC LIMIT 1",
        user_id,
    )
    if sess:
        return sess
    level = await con.fetchval("SELECT level FROM users WHERE id=$1", user_id) or 1
    ids = await _pick_question_ids(con, user_id, level)
    if not ids:
        return None
    expires = _now() + dt.timedelta(hours=SESSION_HOURS)
    sess = await con.fetchrow(
        "INSERT INTO daily_quiz_sessions(user_id, question_ids, expires_at) VALUES($1,$2,$3) RETURNING *",
        user_id, json.dumps(ids), expires,
    )
    return sess


def _ids(sess):
    q = sess["question_ids"]
    return json.loads(q) if isinstance(q, str) else q


async def daily_status(pool, redis, user_id):
    async with pool.acquire() as con:
        sess = await _get_or_create_session(con, user_id)
        if not sess:
            return {"empty": True, "questions": [], "completed_count": 0, "remaining": 0}
        ids = _ids(sess)
        rows = await con.fetch("SELECT * FROM quiz_questions WHERE id = ANY($1::bigint[])", ids)
        attempts = {r["question_id"]: r for r in await con.fetch(
            "SELECT question_id, chosen_index, correct FROM quiz_attempts "
            "WHERE user_id=$1 AND question_id = ANY($2::bigint[])",
            user_id, ids,
        )}
    by_id = {r["id"]: r for r in rows}
    questions = []
    for qid in ids:
        r = by_id.get(qid)
        if not r:
            continue
        a = attempts.get(qid)
        opts = _opts(r)
        order = answer_order(qid, user_id, len(opts))
        shuffled = [opts[order[i]] for i in range(len(opts))]
        q = {
            "id": r["id"], "question": r["question"], "options": shuffled,
            "difficulty": r["difficulty"], "tier": r["tier"], "category": r["category"],
            "reward": r["reward"] or XP_BY_DIFF.get(r["difficulty"], 10),
            "source_section": r["source_section"], "source_url": r["source_url"],
            "answered": a is not None,
        }
        if a is not None:                    # reveal answer only after answering
            q["was_correct"] = a["correct"]
            q["chosen_index"] = a["chosen_index"]                 # stored in shuffled space
            q["correct_index"] = order.index(r["correct_index"])  # position in shuffled options
            q["explanation"] = r["explanation"]
        questions.append(q)

    completed = sum(1 for q in questions if q["answered"])
    countdown = max(0, int((sess["expires_at"] - _now()).total_seconds()))
    return {
        "date": str(dt.date.today()),
        "questions": questions,
        "completed_count": completed,
        "remaining": DAILY_SIZE - completed,
        "total": DAILY_SIZE,
        "completed": completed >= DAILY_SIZE,
        "reset_time": sess["expires_at"].isoformat(),
        "countdown_seconds": countdown,
    }


async def status(pool, redis, user_id):
    d = await daily_status(pool, redis, user_id)
    return {"completed_count": d.get("completed_count", 0),
            "remaining": d.get("remaining", 0),
            "reset_time": d.get("reset_time"),
            "countdown_seconds": d.get("countdown_seconds", 0)}


async def next_question(pool, redis, user_id):
    """Compat: returns the next unanswered daily question, or a 'done' marker."""
    d = await daily_status(pool, redis, user_id)
    if d.get("empty"):
        return {"empty": True}
    for q in d["questions"]:
        if not q["answered"]:
            return {**q, "remaining": d["remaining"], "completed_count": d["completed_count"]}
    return {"completed": True, "countdown_seconds": d["countdown_seconds"], "reset_time": d["reset_time"]}


# ---------------- Answer ----------------
async def submit_answer(pool, redis, user_id, question_id, chosen_index):
    async with pool.acquire() as con:
        sess = await _get_or_create_session(con, user_id)
        if not sess or question_id not in _ids(sess):
            return {"error": "not_in_daily_session"}
        q = await con.fetchrow(
            "SELECT * FROM quiz_questions WHERE id=$1 AND status='approved' AND active=true", question_id)
        if not q:
            return {"error": "question_not_found"}
        already = await con.fetchval(
            "SELECT correct FROM quiz_attempts WHERE user_id=$1 AND question_id=$2", user_id, question_id)
        if already is not None:
            return {"error": "already_answered"}

    # Map the user's shuffled choice back to the original option, then validate.
    opts = _opts(q)
    order = answer_order(question_id, user_id, len(opts))
    original_choice = order[chosen_index] if 0 <= chosen_index < len(order) else -1
    correct = (original_choice == q["correct_index"])
    shuffled_correct_index = order.index(q["correct_index"])
    correct_answer = opts[q["correct_index"]]
    base = q["reward"] or XP_BY_DIFF.get(q["difficulty"], 10)
    awarded, streak, bonus, special, penalty, training = 0, 0, 0, False, 0, False

    if correct:
        await redis.delete(f"quizwrong:{user_id}")
        streak = await redis.incr(f"quizstreak:{user_id}")
        await redis.expire(f"quizstreak:{user_id}", 86400)
        bonus = STREAK_BONUS.get(streak, 0)
        special = streak in STREAK_BONUS
        awarded = base + bonus
        res = await economy.award_points(pool, user_id, awarded, "quiz",
                                         f"q:{question_id}", redis=redis, surge=True)
    else:
        await redis.delete(f"quizstreak:{user_id}")
        # Penalty: -1 ZLN-XP (never below 0). Learning, not punishing.
        d = await economy.deduct_points(pool, user_id, WRONG_PENALTY, "quiz_penalty", f"qp:{question_id}:{user_id}")
        penalty = d["deducted"]
        wrong = await redis.incr(f"quizwrong:{user_id}")
        await redis.expire(f"quizwrong:{user_id}", 86400)
        if wrong >= WRONG_STREAK_LIMIT:           # Operator Training Required
            training = True
            await redis.set(f"quizcd:{user_id}", "1", ex=TRAINING_COOLDOWN_SEC)
            await redis.delete(f"quizwrong:{user_id}")
        res = {"leveled": False, "level": None}

    async with pool.acquire() as con:
        await con.execute(
            """INSERT INTO quiz_attempts(user_id, question_id, chosen_index, correct, awarded)
               VALUES($1,$2,$3,$4,$5) ON CONFLICT (user_id, question_id) DO NOTHING""",
            user_id, question_id, chosen_index, correct, awarded,
        )
        await con.execute(
            "UPDATE daily_quiz_sessions SET completed_count=completed_count+1 "
            "WHERE id=$1", sess["id"],
        )
        done = await con.fetchval(
            "SELECT count(*) FROM quiz_attempts WHERE user_id=$1 AND question_id = ANY($2::bigint[])",
            user_id, _ids(sess),
        )
    rank = await quiz_rank(pool, user_id)
    countdown = max(0, int((sess["expires_at"] - _now()).total_seconds()))
    return {
        "correct": correct, "correct_index": shuffled_correct_index,
        "correct_answer": correct_answer,
        "base": base, "bonus": bonus, "awarded": awarded, "penalty": penalty,
        "streak": streak, "special": special, "training_required": training,
        "explanation": q["explanation"], "source_section": q["source_section"],
        "source_url": q["source_url"],
        "completed_count": done, "remaining": max(0, DAILY_SIZE - done),
        "completed": done >= DAILY_SIZE, "countdown_seconds": countdown,
        "leveled": res.get("leveled", False), "level": res.get("level"), "rank": rank["rank"],
    }


# ---------------- History / admin ----------------
async def history(pool, user_id, limit=20):
    async with pool.acquire() as con:
        rows = await con.fetch(
            """SELECT a.correct, a.awarded, a.created_at, q.question, q.difficulty, q.tier,
                      q.category, q.source_section, q.source_url
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
        approved = await con.fetchval(
            "SELECT count(*) FROM quiz_questions WHERE status='approved' AND active=true")
        pending = await con.fetchval("SELECT count(*) FROM quiz_questions WHERE status='pending'")
        by_diff = await con.fetch(
            "SELECT difficulty, count(*) c FROM quiz_questions WHERE status='approved' AND active "
            "GROUP BY difficulty ORDER BY difficulty")
        attempts_24h = await con.fetchval(
            "SELECT count(*) FROM quiz_attempts WHERE created_at > now() - interval '1 day'")
        daily_sessions = await con.fetchval(
            "SELECT count(*) FROM daily_quiz_sessions WHERE created_at > now() - interval '1 day'")
        accuracy = await con.fetchval(
            "SELECT round(100.0*avg(case when correct then 1 else 0 end),1) FROM quiz_attempts "
            "WHERE created_at > now() - interval '7 days'")
    return {"total": total, "approved": approved, "pending": pending,
            "by_difficulty": [dict(r) for r in by_diff],
            "attempts_24h": attempts_24h, "daily_sessions_24h": daily_sessions,
            "accuracy_7d": accuracy}
