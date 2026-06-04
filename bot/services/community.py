"""Community / group engagement: daily discussion, group missions, contribution
score, group leaderboards. ZLN-XP rewards go through the shared points ledger."""
import datetime as dt
from ..config import settings
from . import economy

SCORE_WEIGHTS = {"message": 2, "reply": 3, "reaction": 1, "discussion": 5}


def _today():
    return dt.date.today()


def _week_key():
    iso = dt.date.today().isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


# ---------------- Daily discussion ----------------
async def post_daily_discussion(bot, pool):
    """Post today's discussion topic to the group (once/day). Returns the topic or None."""
    if not settings.GROUP_CHAT_ID:
        return None
    async with pool.acquire() as con:
        existing = await con.fetchval(
            "SELECT topic FROM daily_discussions WHERE discussion_date=$1", _today())
        if existing:
            return existing
        topic = await con.fetchval(
            """SELECT topic FROM discussion_topics WHERE active
               AND topic NOT IN (SELECT topic FROM daily_discussions
                                 WHERE discussion_date > CURRENT_DATE - 14)
               ORDER BY random() LIMIT 1""")
        if not topic:
            topic = await con.fetchval("SELECT topic FROM discussion_topics ORDER BY random() LIMIT 1")
        if not topic:
            return None
    text = (f"🗣️ <b>Daily Zelion Discussion</b>\n\n{topic}\n\n"
            f"💬 Reply with your take — meaningful answers earn <b>ZLN-XP</b>!")
    try:
        msg = await bot.send_message(settings.GROUP_CHAT_ID, text)
        try:
            await bot.pin_chat_message(settings.GROUP_CHAT_ID, msg.message_id, disable_notification=True)
        except Exception:
            pass
        async with pool.acquire() as con:
            await con.execute(
                "INSERT INTO daily_discussions(discussion_date, topic, message_id) VALUES($1,$2,$3) "
                "ON CONFLICT (discussion_date) DO UPDATE SET topic=$2, message_id=$3",
                _today(), topic, msg.message_id)
        return topic
    except Exception:
        return None


async def todays_discussion(pool):
    async with pool.acquire() as con:
        r = await con.fetchrow(
            "SELECT topic, message_id, replies FROM daily_discussions WHERE discussion_date=$1", _today())
    return dict(r) if r else None


async def discussion_message_id(pool):
    d = await todays_discussion(pool)
    return d["message_id"] if d else None


# ---------------- Group missions ----------------
async def _progress(con, user_id):
    today, week_start = _today(), _today() - dt.timedelta(days=_today().weekday())
    row = await con.fetchrow(
        """SELECT
             count(*) FILTER (WHERE kind='message'    AND created_at::date=$2) AS msg_today,
             count(*) FILTER (WHERE kind='reply'       AND created_at::date=$2) AS reply_today,
             count(*) FILTER (WHERE kind='reaction'    AND created_at::date=$2) AS react_today,
             count(*) FILTER (WHERE kind='discussion'  AND created_at::date=$2) AS disc_today,
             count(*) FILTER (WHERE kind='reply'       AND created_at>=$3) AS reply_week,
             count(*) FILTER (WHERE kind='reaction'    AND created_at>=$3) AS react_week,
             count(DISTINCT created_at::date) FILTER (WHERE created_at>=$3) AS days_week
           FROM group_activity WHERE user_id=$1""",
        user_id, today, week_start)
    refs = await con.fetchval(
        "SELECT count(*) FROM referrals WHERE referrer_id=$1 AND status='activated'", user_id) or 0
    return {
        "messages": row["msg_today"], "replies": row["reply_today"], "reactions": row["react_today"],
        "discussion": row["disc_today"], "days": row["days_week"],
        "replies_week": row["reply_week"], "reactions_week": row["react_week"], "referrals": refs,
    }


def _metric_value(metric, prog, period):
    if metric == "replies" and period == "weekly":
        return prog["replies_week"]
    if metric == "reactions" and period == "weekly":
        return prog["reactions_week"]
    return prog.get(metric, 0)


async def list_missions(pool, user_id):
    async with pool.acquire() as con:
        missions = await con.fetch("SELECT * FROM group_missions WHERE active ORDER BY period, id")
        claimed = {(r["mission_id"], r["period_key"]) for r in await con.fetch(
            "SELECT mission_id, period_key FROM user_group_missions WHERE user_id=$1", user_id)}
        prog = await _progress(con, user_id)
    out = []
    for m in missions:
        pk = _today().isoformat() if m["period"] == "daily" else _week_key()
        cur = _metric_value(m["metric"], prog, m["period"])
        out.append({
            "id": m["id"], "title": m["title"], "icon": m["icon"], "period": m["period"],
            "metric": m["metric"], "goal": m["goal"], "reward": m["reward"],
            "progress": min(cur, m["goal"]), "done": cur >= m["goal"],
            "claimed": (m["id"], pk) in claimed,
        })
    return out


async def claim_mission(pool, redis, user_id, mission_id):
    async with pool.acquire() as con:
        m = await con.fetchrow("SELECT * FROM group_missions WHERE id=$1 AND active", mission_id)
        if not m:
            return {"error": "not_found"}
        pk = _today().isoformat() if m["period"] == "daily" else _week_key()
        if await con.fetchval(
                "SELECT 1 FROM user_group_missions WHERE user_id=$1 AND mission_id=$2 AND period_key=$3",
                user_id, mission_id, pk):
            return {"error": "already_claimed"}
        prog = await _progress(con, user_id)
        if _metric_value(m["metric"], prog, m["period"]) < m["goal"]:
            return {"error": "incomplete"}
        await con.execute(
            "INSERT INTO user_group_missions(user_id, mission_id, period_key) VALUES($1,$2,$3) "
            "ON CONFLICT DO NOTHING", user_id, mission_id, pk)
    await economy.award_points(pool, user_id, m["reward"], "group_mission",
                               f"gmis:{user_id}:{mission_id}:{pk}", redis=redis)
    return {"ok": True, "reward": m["reward"]}


# ---------------- Contribution score + leaderboard ----------------
async def contribution_score(pool, user_id):
    async with pool.acquire() as con:
        prog = await _progress(con, user_id)
    today = sum(prog[k] * SCORE_WEIGHTS[k] for k in ("messages", "replies", "reactions", "discussion"))
    return {"today": today, "messages": prog["messages"], "replies": prog["replies"],
            "reactions": prog["reactions"], "discussion": prog["discussion"], "days_week": prog["days"]}


async def group_leaderboard(pool, period="today", limit=10):
    window = {
        "today": "created_at::date = CURRENT_DATE",
        "week": "created_at >= date_trunc('week', now())",
        "month": "created_at >= date_trunc('month', now())",
    }.get(period, "created_at::date = CURRENT_DATE")
    sql = (
        "SELECT g.user_id, COALESCE(u.username, u.first_name, g.user_id::text) AS name, "
        "SUM(CASE g.kind WHEN 'message' THEN 2 WHEN 'reply' THEN 3 WHEN 'reaction' THEN 1 "
        "WHEN 'discussion' THEN 5 ELSE 1 END) AS score "
        f"FROM group_activity g LEFT JOIN users u ON u.id=g.user_id WHERE {window} "
        "GROUP BY g.user_id, u.username, u.first_name ORDER BY score DESC LIMIT $1")
    async with pool.acquire() as con:
        rows = await con.fetch(sql, limit)
    return [{"name": r["name"], "score": int(r["score"])} for r in rows]


async def post_group_leaderboard(bot, pool):
    if not settings.GROUP_CHAT_ID:
        return
    rows = await group_leaderboard(pool, "today", 5)
    if not rows:
        return
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    body = "\n".join(f"{medals[i]} {r['name']} — {r['score']} pts" for i, r in enumerate(rows))
    try:
        await bot.send_message(
            settings.GROUP_CHAT_ID,
            f"🏆 <b>Top Contributors Today</b>\n\n{body}\n\nKeep the discussion going — earn ZLN-XP! ⚡")
    except Exception:
        pass
