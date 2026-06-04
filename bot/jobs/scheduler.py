"""Background jobs: weekly leaderboard reset, surge hours, daily discussion,
periodic group leaderboard posts. (Proof moderation now lives in the Mini App.)"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from ..config import settings
from ..services import redis_lb
from ..services import events as esvc
from ..services import leaderboard
from ..services import community as csvc

log = logging.getLogger("zelion.jobs")


def start_all(bot, pool, redis):
    asyncio.create_task(weekly_reset_loop(bot, pool, redis))
    asyncio.create_task(daily_discussion_loop(bot, pool))
    asyncio.create_task(group_leaderboard_loop(bot, pool))
    if settings.SURGE_HOURS:
        asyncio.create_task(surge_scheduler_loop(bot, pool, redis))


def _seconds_to_next_monday_utc():
    now = datetime.now(timezone.utc)
    days_ahead = (7 - now.weekday()) % 7
    target = (now + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=7)
    return (target - now).total_seconds()


async def weekly_reset_loop(bot, pool, redis):
    while True:
        await asyncio.sleep(_seconds_to_next_monday_utc())
        try:
            top3 = await redis_lb.snapshot_and_reset_week(pool, redis)
            names = await leaderboard.names_for(pool, [uid for uid, _ in top3]) if top3 else {}
            medals = ["🥇", "🥈", "🥉"]
            body = "\n".join(
                f"{medals[i]} {names.get(uid, uid)} — {sc} ZLN-XP" for i, (uid, sc) in enumerate(top3)
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
                        f"Bonuses paid to the top 3. New week, new race — charge up! ⚡")
                except Exception:
                    pass
        except Exception as e:
            log.warning("weekly reset error: %s", e)


async def daily_discussion_loop(bot, pool):
    """Post the daily discussion topic to the group once per day (after DISCUSSION_HOUR UTC)."""
    while True:
        try:
            now = datetime.now(timezone.utc)
            if now.hour >= settings.DISCUSSION_HOUR:
                topic = await csvc.post_daily_discussion(bot, pool)
                if topic:
                    log.info("daily discussion posted")
        except Exception as e:
            log.warning("daily discussion error: %s", e)
        await asyncio.sleep(1800)  # check every 30 min (post is idempotent per day)


async def group_leaderboard_loop(bot, pool):
    """Post 'Top Contributors Today' to the group periodically."""
    await asyncio.sleep(3600)
    while True:
        try:
            await csvc.post_group_leaderboard(bot, pool)
        except Exception as e:
            log.warning("group leaderboard error: %s", e)
        await asyncio.sleep(6 * 3600)  # every 6 hours


async def surge_scheduler_loop(bot, pool, redis):
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
