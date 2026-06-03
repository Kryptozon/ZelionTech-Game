"""Background jobs: 24h proof SLA, weekly leaderboard reset, scheduled surge hours."""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from ..config import settings
from ..services import proof as psvc
from ..services import redis_lb
from ..services import events as esvc
from ..services import leaderboard

log = logging.getLogger("zelion.jobs")


def start_all(bot, pool, redis):
    asyncio.create_task(sla_reminder_loop(bot, pool))
    asyncio.create_task(weekly_reset_loop(bot, pool, redis))
    if settings.SURGE_HOURS:
        asyncio.create_task(surge_scheduler_loop(bot, pool, redis))


async def sla_reminder_loop(bot, pool):
    """Hourly: ping admins about proofs pending past the 24h SLA."""
    while True:
        try:
            overdue = await psvc.overdue_pending(pool, hours=24)
            if overdue and settings.ADMIN_IDS:
                for admin_id in settings.ADMIN_IDS:
                    try:
                        await bot.send_message(
                            admin_id,
                            f"⏰ <b>{len(overdue)} proof(s) overdue 24h.</b> Run /pending to review.",
                        )
                    except Exception:
                        pass
        except Exception as e:
            log.warning("SLA loop error: %s", e)
        await asyncio.sleep(3600)


def _seconds_to_next_monday_utc():
    now = datetime.now(timezone.utc)
    days_ahead = (7 - now.weekday()) % 7  # Monday=0
    target = (now + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=7)
    return (target - now).total_seconds()


async def weekly_reset_loop(bot, pool, redis):
    """Every Monday 00:00 UTC: snapshot weekly board, reward top 3, announce, reset."""
    while True:
        await asyncio.sleep(_seconds_to_next_monday_utc())
        try:
            top3 = await redis_lb.snapshot_and_reset_week(pool, redis)
            names = await leaderboard.names_for(pool, [uid for uid, _ in top3]) if top3 else {}
            medals = ["🥇", "🥈", "🥉"]
            body = "\n".join(
                f"{medals[i]} {names.get(uid, uid)} — {sc}💎" for i, (uid, sc) in enumerate(top3)
            ) or "no entries this week"
            from ..services import admin as asvc
            for i, (uid, _sc) in enumerate(top3):
                if i < len(settings.WEEKLY_BONUS):
                    await asvc.grant_points(pool, uid, settings.WEEKLY_BONUS[i], 0, redis=redis)
            if settings.GROUP_CHAT_ID:
                try:
                    await bot.send_message(
                        settings.GROUP_CHAT_ID,
                        f"🏆 <b>WEEKLY RANKINGS — RESET!</b>\n\n{body}\n\n"
                        f"Bonuses paid to the top 3. New week, new race — charge up! ⚡",
                    )
                except Exception:
                    pass
        except Exception as e:
            log.warning("weekly reset error: %s", e)


async def surge_scheduler_loop(bot, pool, redis):
    """Trigger a surge at each configured UTC hour (once per day per hour)."""
    while True:
        now = datetime.now(timezone.utc)
        if now.hour in settings.SURGE_HOURS:
            key = f"surge:fired:{now.strftime('%Y-%m-%d-%H')}"
            if await redis.set(key, "1", nx=True, ex=3700):
                try:
                    await esvc.start_surge(redis, pool, bot, settings.SURGE_MULT,
                                           settings.SURGE_DURATION_MIN)
                except Exception as e:
                    log.warning("surge trigger error: %s", e)
        await asyncio.sleep(60)
