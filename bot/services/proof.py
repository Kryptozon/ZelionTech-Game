"""Proof submission + Mini-App dashboard moderation.

Screenshots are stored in the DB and reviewed inside the Mini App Admin Dashboard.
No Telegram forwarding / retries.
"""
import json
import logging
from .economy import award_points, maybe_activate_referral

log = logging.getLogger("zelion.proof")
MAX_IMAGE_BYTES = 3 * 1024 * 1024  # 3 MB cap


async def create_submission(pool, user_id, mission_id, platform, handle,
                            screenshot=None, mime=None, username=None):
    """Create a pending proof with an optional screenshot (bytes). Returns pid or None if duplicate."""
    if screenshot and len(screenshot) > MAX_IMAGE_BYTES:
        return "too_large"
    async with pool.acquire() as con:
        existing = await con.fetchval(
            "SELECT 1 FROM proof_submissions WHERE user_id=$1 AND mission_id=$2 "
            "AND status IN ('pending','approved')",
            user_id, mission_id,
        )
        if existing:
            return None
        reward = await con.fetchval("SELECT xp_reward FROM missions WHERE id=$1", mission_id) or 0
        pid = await con.fetchval(
            """INSERT INTO proof_submissions(user_id, mission_id, platform, claimed_handle,
                    submitted_link, username_snapshot, screenshot, screenshot_mime, status, reward)
               VALUES($1,$2,$3,$4,$4,$5,$6,$7,'pending',$8) RETURNING id""",
            user_id, mission_id, platform, handle, username, screenshot, mime, reward,
        )
        log.info("proof_created pid=%s user=%s mission=%s platform=%s has_image=%s",
                 pid, user_id, mission_id, platform, bool(screenshot))
        return pid


# ---------------- Dashboard queries ----------------
async def list_by_status(pool, status="pending", limit=100):
    async with pool.acquire() as con:
        rows = await con.fetch(
            """SELECT p.id, p.user_id, p.mission_id, p.platform, p.claimed_handle, p.submitted_link,
                      p.reward, p.status, p.reject_reason, p.created_at, p.reviewed_at, p.reviewed_by,
                      (p.screenshot IS NOT NULL) AS has_image,
                      m.title, COALESCE(u.username, p.username_snapshot) AS username, u.first_name
               FROM proof_submissions p
               JOIN missions m ON m.id = p.mission_id
               LEFT JOIN users u ON u.id = p.user_id
               WHERE p.status = $1 ORDER BY p.created_at DESC LIMIT $2""",
            status, limit,
        )
    return [dict(r) for r in rows]


async def get_image(pool, pid):
    async with pool.acquire() as con:
        r = await con.fetchrow(
            "SELECT screenshot, screenshot_mime FROM proof_submissions WHERE id=$1", pid)
    if not r or not r["screenshot"]:
        return None, None
    return bytes(r["screenshot"]), (r["screenshot_mime"] or "image/jpeg")


async def banned_users(pool, limit=100):
    async with pool.acquire() as con:
        rows = await con.fetch(
            """SELECT b.user_id, b.reason, b.created_at, u.username, u.first_name
               FROM bans b LEFT JOIN users u ON u.id=b.user_id
               ORDER BY b.created_at DESC LIMIT $1""",
            limit,
        )
    return [dict(r) for r in rows]


async def dashboard_stats(pool):
    async with pool.acquire() as con:
        pending = await con.fetchval("SELECT count(*) FROM proof_submissions WHERE status='pending'")
        appr_today = await con.fetchval(
            "SELECT count(*) FROM proof_submissions WHERE status='approved' "
            "AND reviewed_at::date = CURRENT_DATE")
        rej_today = await con.fetchval(
            "SELECT count(*) FROM proof_submissions WHERE status='rejected' "
            "AND reviewed_at::date = CURRENT_DATE")
        distributed = await con.fetchval(
            "SELECT COALESCE(sum(reward),0) FROM proof_submissions WHERE status='approved'")
        banned = await con.fetchval("SELECT count(*) FROM bans")
    return {"pending": pending, "approved_today": appr_today, "rejected_today": rej_today,
            "zln_distributed": distributed, "banned": banned}


# ---------------- Moderation actions ----------------
async def approve(pool, pid, admin_id, redis=None):
    """Approve, award ZLN-XP, verify handle, activate referral. Returns result dict / None / 'dup'."""
    async with pool.acquire() as con:
        p = await con.fetchrow(
            """SELECT p.*, m.xp_reward, m.title FROM proof_submissions p
               JOIN missions m ON m.id=p.mission_id WHERE p.id=$1""", pid)
        if not p or p["status"] != "pending":
            return None
        dup = await con.fetchval(
            "SELECT user_id FROM social_accounts WHERE platform=$1 AND handle=$2 "
            "AND verified=true AND user_id<>$3",
            p["platform"], p["claimed_handle"], p["user_id"],
        )
        if dup:
            await con.execute(
                "UPDATE proof_submissions SET status='rejected', reviewed_by=$1, "
                "reject_reason='Duplicate handle already used by another account', reviewed_at=now() WHERE id=$2",
                admin_id, pid)
            return "dup"
        await con.execute(
            "UPDATE proof_submissions SET status='approved', reviewed_by=$1, reviewed_at=now() WHERE id=$2",
            admin_id, pid)
        await con.execute(
            "INSERT INTO social_accounts(user_id, platform, handle, verified) VALUES($1,$2,$3,true) "
            "ON CONFLICT (platform, handle) DO UPDATE SET verified=true",
            p["user_id"], p["platform"], p["claimed_handle"])
        await con.execute(
            "INSERT INTO admin_actions(admin_id, action, target_id, detail) VALUES($1,'approve_proof',$2,$3)",
            admin_id, p["user_id"], json.dumps({"pid": pid}))

    award = await award_points(pool, p["user_id"], p["xp_reward"], "proof", f"proof:{pid}", redis=redis)
    from . import analytics
    await analytics.log_event(pool, p["user_id"], "proof_approved", {"pid": pid, "platform": p["platform"]})
    referrer = await maybe_activate_referral(pool, p["user_id"], redis=redis)
    return {"user_id": p["user_id"], "xp": p["xp_reward"], "title": p["title"],
            "leveled": award["leveled"], "level": award["level"], "referrer": referrer}


async def reject(pool, pid, admin_id, reason):
    async with pool.acquire() as con:
        p = await con.fetchrow("SELECT * FROM proof_submissions WHERE id=$1", pid)
        if not p or p["status"] != "pending":
            return None
        await con.execute(
            "UPDATE proof_submissions SET status='rejected', reviewed_by=$1, reject_reason=$2, "
            "reviewed_at=now() WHERE id=$3", admin_id, (reason or "Not valid")[:280], pid)
        await con.execute(
            "INSERT INTO admin_actions(admin_id, action, target_id, detail) VALUES($1,'reject_proof',$2,$3)",
            admin_id, p["user_id"], json.dumps({"pid": pid}))
    return {"user_id": p["user_id"], "mission_id": p["mission_id"], "reason": reason}


async def ban_and_reject_all(pool, target_user_id, admin_id):
    """Ban a user from missions/rewards and auto-reject all their pending proofs."""
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO bans(user_id, reason, banned_by) VALUES($1,'Fraudulent proof',$2) "
            "ON CONFLICT (user_id) DO UPDATE SET reason='Fraudulent proof', banned_by=$2, created_at=now()",
            target_user_id, admin_id)
        await con.execute("UPDATE users SET status='banned' WHERE id=$1", target_user_id)
        await con.execute(
            "UPDATE proof_submissions SET status='rejected', reviewed_by=$1, "
            "reject_reason='User banned', reviewed_at=now() WHERE user_id=$2 AND status='pending'",
            admin_id, target_user_id)
        await con.execute(
            "INSERT INTO admin_actions(admin_id, action, target_id, detail) VALUES($1,'ban',$2,$3)",
            admin_id, target_user_id, json.dumps({"via": "dashboard"}))
    return {"user_id": target_user_id}
