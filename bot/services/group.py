"""Group activity rewards with strict anti-spam: min length, anti-flood, daily cap,
duplicate detection, emoji/low-value filtering. Replies and discussion answers earn extra."""
import re
import hashlib
from ..config import settings
from . import economy


async def _scored_today(pool, user_id, kind) -> int:
    async with pool.acquire() as con:
        return await con.fetchval(
            "SELECT count(*) FROM group_activity WHERE user_id=$1 AND kind=$2 "
            "AND scored=true AND created_at > now() - interval '1 day'",
            user_id, kind,
        )


def _meaningful(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < settings.GROUP_MSG_MIN_LEN or t.startswith("/"):
        return False
    letters = sum(ch.isalnum() for ch in t)
    if letters < 12:                       # filters emoji-only / "hi" / symbol spam
        return False
    words = [w for w in re.findall(r"[a-zA-Z0-9']+", t.lower()) if len(w) > 1]
    if len(set(words)) < 3:                # filters repeated single word / "ok ok ok"
        return False
    return True


async def reward_message(pool, redis, user_id, chat_id, message_id, text,
                         is_reply=False, is_discussion=False) -> dict:
    """Score a group message. Returns dict with what was awarded (server-authoritative)."""
    out = {"message": False, "reply": False, "discussion": False, "reason": None}
    if not _meaningful(text):
        out["reason"] = "not_meaningful"
        return out

    # Duplicate text guard (per user, 24h).
    h = hashlib.sha1(re.sub(r"\s+", " ", text.strip().lower()).encode()).hexdigest()[:16]
    if not await redis.set(f"dupmsg:{user_id}:{h}", "1", nx=True, ex=86400):
        out["reason"] = "duplicate"
        return out

    # Anti-flood: 1 rewarded message per GROUP_FLOOD_SEC.
    if not await redis.set(f"gflood:{user_id}", "1", nx=True, ex=settings.GROUP_FLOOD_SEC):
        out["reason"] = "flood"
        return out

    # Daily cap.
    if await _scored_today(pool, user_id, "message") >= settings.GROUP_MSG_DAILY_CAP:
        out["reason"] = "daily_cap"
        return out

    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO group_activity(user_id, chat_id, kind, scored) VALUES($1,$2,'message',true)",
            user_id, chat_id)
    await economy.award_points(pool, user_id, settings.GROUP_MSG_XP, "group_msg",
                               f"gm:{chat_id}:{message_id}", redis=redis, surge=True)
    out["message"] = True

    if is_reply:
        async with pool.acquire() as con:
            await con.execute(
                "INSERT INTO group_activity(user_id, chat_id, kind, scored) VALUES($1,$2,'reply',true)",
                user_id, chat_id)
        await economy.award_points(pool, user_id, settings.GROUP_REPLY_XP, "group_reply",
                                   f"grp:{chat_id}:{message_id}", redis=redis, surge=True)
        out["reply"] = True

    if is_discussion and await _scored_today(pool, user_id, "discussion") < 1:
        async with pool.acquire() as con:
            await con.execute(
                "INSERT INTO group_activity(user_id, chat_id, kind, scored) VALUES($1,$2,'discussion',true)",
                user_id, chat_id)
            await con.execute(
                "UPDATE daily_discussions SET replies = replies + 1 WHERE discussion_date = CURRENT_DATE")
        await economy.award_points(pool, user_id, settings.GROUP_DISCUSSION_XP, "group_discussion",
                                   f"gd:{chat_id}:{message_id}", redis=redis, surge=True)
        out["discussion"] = True

    return out


async def reward_reaction(pool, redis, user_id, chat_id, message_id) -> bool:
    if await _scored_today(pool, user_id, "reaction") >= settings.GROUP_REACT_DAILY_CAP:
        return False
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO group_activity(user_id, chat_id, kind, scored) VALUES($1,$2,'reaction',true)",
            user_id, chat_id)
    await economy.award_points(pool, user_id, settings.GROUP_REACT_XP, "group_react",
                               f"gr:{chat_id}:{message_id}:{user_id}", redis=redis, surge=True)
    return True
