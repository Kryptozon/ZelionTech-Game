"""Phase 3: lightweight analytics event stream."""
import json
import asyncpg


async def log_event(pool, user_id, event: str, props: dict | None = None):
    try:
        async with pool.acquire() as con:
            await con.execute(
                "INSERT INTO analytics_events(user_id, event, props) VALUES($1,$2,$3)",
                user_id, event, json.dumps(props or {}),
            )
    except Exception:
        pass  # analytics must never break gameplay


async def summary(pool):
    async with pool.acquire() as con:
        dau = await con.fetchval(
            "SELECT count(DISTINCT user_id) FROM analytics_events WHERE created_at > now() - interval '1 day'"
        )
        wau = await con.fetchval(
            "SELECT count(DISTINCT user_id) FROM analytics_events WHERE created_at > now() - interval '7 days'"
        )
        top_events = await con.fetch(
            "SELECT event, count(*) c FROM analytics_events "
            "WHERE created_at > now() - interval '1 day' GROUP BY event ORDER BY c DESC LIMIT 8"
        )
        # Core funnel metrics from authoritative tables (not just the event stream).
        missions_24h = await con.fetchval(
            "SELECT count(*) FROM mission_completions WHERE completed_at > now() - interval '1 day'"
        )
        proofs_pending = await con.fetchval(
            "SELECT count(*) FROM proof_submissions WHERE status='pending'"
        )
        proofs_approved_24h = await con.fetchval(
            "SELECT count(*) FROM proof_submissions WHERE status='approved' "
            "AND reviewed_at > now() - interval '1 day'"
        )
        proofs_rejected_24h = await con.fetchval(
            "SELECT count(*) FROM proof_submissions WHERE status='rejected' "
            "AND reviewed_at > now() - interval '1 day'"
        )
        refs_activated_24h = await con.fetchval(
            "SELECT count(*) FROM referrals WHERE status='activated' "
            "AND activated_at > now() - interval '1 day'"
        )
        refs_pending = await con.fetchval(
            "SELECT count(*) FROM referrals WHERE status='pending'"
        )
    return {
        "dau": dau, "wau": wau, "top_events": top_events,
        "missions_24h": missions_24h,
        "proofs_pending": proofs_pending,
        "proofs_approved_24h": proofs_approved_24h,
        "proofs_rejected_24h": proofs_rejected_24h,
        "refs_activated_24h": refs_activated_24h,
        "refs_pending": refs_pending,
    }
