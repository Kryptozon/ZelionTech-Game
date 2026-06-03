"""Proof submission + admin approval pipeline + reliable admin delivery."""
import logging
import datetime as dt
import asyncpg
from .economy import award_points, maybe_activate_referral
from ..config import settings

log = logging.getLogger("zelion.proof")


async def create_submission(pool, user_id, mission_id, platform, handle, file_id):
    """Create a pending proof (stores reward). Returns proof id, or None if duplicate."""
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
            """INSERT INTO proof_submissions(user_id, mission_id, platform, claimed_handle, file_id,
                                             status, reward, delivered)
               VALUES($1,$2,$3,$4,$5,'pending',$6,false) RETURNING id""",
            user_id, mission_id, platform, handle, file_id, reward,
        )
        log.info("proof_created pid=%s user=%s mission=%s platform=%s", pid, user_id, mission_id, platform)
        return pid


async def deliver(bot, pool, pid) -> bool:
    """Send a proof to every admin with review buttons. Marks delivered on first success.
    Used by the submit flows AND the retry job. Returns True if delivered."""
    from ..keyboards import proof_review_kb
    async with pool.acquire() as con:
        p = await con.fetchrow(
            """SELECT p.*, m.title, u.username, u.first_name
               FROM proof_submissions p JOIN missions m ON m.id=p.mission_id
               JOIN users u ON u.id=p.user_id WHERE p.id=$1""",
            pid,
        )
    if not p:
        return False
    ts = p["created_at"].strftime("%Y-%m-%d %H:%M UTC") if p["created_at"] else "—"
    caption = (
        f"🔔 <b>NEW PROOF #{p['id']}</b> — pending review\n"
        f"👤 User: {p['first_name'] or ''} (@{p['username'] or '—'})\n"
        f"🆔 Telegram ID: <code>{p['user_id']}</code>\n"
        f"📡 Mission/Platform: <b>{p['title']}</b> ({p['platform']})\n"
        f"🔗 Submitted handle: <code>{p['claimed_handle'] or '—'}</code>\n"
        f"💎 Reward: <b>{p['reward']} ZP</b>\n"
        f"🕒 Submitted: {ts}\n"
        f"🧾 Proof ID: <code>{p['id']}</code>"
    )
    kb = proof_review_kb(pid)
    delivered = False
    if not settings.ADMIN_IDS:
        log.error("proof_deliver no ADMIN_IDS configured (pid=%s)", pid)
    for admin_id in settings.ADMIN_IDS:
        try:
            if p["file_id"]:
                await bot.send_photo(admin_id, p["file_id"], caption=caption, reply_markup=kb)
            else:
                await bot.send_message(admin_id, caption + "\n<i>(no screenshot — submitted via Mini App)</i>",
                                       reply_markup=kb)
            delivered = True
            log.info("proof_delivered pid=%s admin=%s", pid, admin_id)
        except Exception as e:
            log.error("proof_deliver_failed pid=%s admin=%s err=%s", pid, admin_id, e)
    if delivered:
        async with pool.acquire() as con:
            await con.execute("UPDATE proof_submissions SET delivered=true WHERE id=$1", pid)
    return delivered


async def undelivered(pool, limit=20):
    async with pool.acquire() as con:
        return await con.fetch(
            "SELECT id FROM proof_submissions WHERE status='pending' AND delivered=false "
            "ORDER BY created_at ASC LIMIT $1",
            limit,
        )


async def list_pending(pool, limit=20):
    async with pool.acquire() as con:
        return await con.fetch(
            """SELECT p.*, m.title, m.xp_reward, u.username,
                      EXTRACT(EPOCH FROM (now()-p.created_at))/3600 AS hours_pending
               FROM proof_submissions p
               JOIN missions m ON m.id = p.mission_id
               JOIN users u ON u.id = p.user_id
               WHERE p.status='pending' ORDER BY p.created_at ASC LIMIT $1""",
            limit,
        )


async def get_submission(pool, pid):
    async with pool.acquire() as con:
        return await con.fetchrow(
            """SELECT p.*, m.title, m.xp_reward FROM proof_submissions p
               JOIN missions m ON m.id=p.mission_id WHERE p.id=$1""",
            pid,
        )


async def approve(pool, pid, admin_id, redis=None):
    """Approve proof, award points automatically. Returns result dict or None/'dup'."""
    async with pool.acquire() as con:
        p = await con.fetchrow(
            """SELECT p.*, m.xp_reward, m.title FROM proof_submissions p
               JOIN missions m ON m.id=p.mission_id WHERE p.id=$1""",
            pid,
        )
        if not p or p["status"] != "pending":
            return None

        # Anti-fraud: same handle already verified by a different user.
        dup = await con.fetchval(
            "SELECT user_id FROM social_accounts WHERE platform=$1 AND handle=$2 "
            "AND verified=true AND user_id<>$3",
            p["platform"], p["claimed_handle"], p["user_id"],
        )
        if dup:
            await con.execute(
                "UPDATE proof_submissions SET status='rejected', reviewed_by=$1, "
                "reject_reason='Duplicate handle already used by another account', reviewed_at=now() WHERE id=$2",
                admin_id, pid,
            )
            await con.execute(
                "INSERT INTO admin_actions(admin_id, action, target_id, detail) VALUES($1,'reject_proof',$2,$3)",
                admin_id, p["user_id"], '{"pid": %d, "reason": "duplicate"}' % pid,
            )
            return "dup"

        await con.execute(
            "UPDATE proof_submissions SET status='approved', reviewed_by=$1, reviewed_at=now() WHERE id=$2",
            admin_id, pid,
        )
        await con.execute(
            "INSERT INTO social_accounts(user_id, platform, handle, verified) VALUES($1,$2,$3,true) "
            "ON CONFLICT (platform, handle) DO UPDATE SET verified=true",
            p["user_id"], p["platform"], p["claimed_handle"],
        )
        await con.execute(
            "INSERT INTO admin_actions(admin_id, action, target_id, detail) VALUES($1,'approve_proof',$2,$3)",
            admin_id, p["user_id"], '{"pid": %d}' % pid,
        )

    award = await award_points(pool, p["user_id"], p["xp_reward"], "proof", f"proof:{pid}", redis=redis)
    from . import analytics
    await analytics.log_event(pool, p["user_id"], "proof_approved",
                              {"pid": pid, "platform": p["platform"]})
    referrer = await maybe_activate_referral(pool, p["user_id"], redis=redis)
    return {
        "user_id": p["user_id"], "xp": p["xp_reward"], "title": p["title"],
        "leveled": award["leveled"], "level": award["level"], "referrer": referrer,
    }


async def reject(pool, pid, admin_id, reason):
    async with pool.acquire() as con:
        p = await con.fetchrow("SELECT * FROM proof_submissions WHERE id=$1", pid)
        if not p or p["status"] != "pending":
            return None
        await con.execute(
            "UPDATE proof_submissions SET status='rejected', reviewed_by=$1, reject_reason=$2, "
            "reviewed_at=now() WHERE id=$3",
            admin_id, reason, pid,
        )
        await con.execute(
            "INSERT INTO admin_actions(admin_id, action, target_id, detail) VALUES($1,'reject_proof',$2,$3)",
            admin_id, p["user_id"], '{"pid": %d}' % pid,
        )
    return {"user_id": p["user_id"], "mission_id": p["mission_id"]}


async def overdue_pending(pool, hours=24):
    """Submissions still pending past the SLA — used for admin reminders."""
    async with pool.acquire() as con:
        return await con.fetch(
            "SELECT id, user_id FROM proof_submissions WHERE status='pending' "
            "AND created_at < now() - ($1 || ' hours')::interval",
            str(hours),
        )
