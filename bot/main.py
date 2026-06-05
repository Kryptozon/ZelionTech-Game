import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ErrorEvent
from redis.asyncio import Redis

from .config import settings
from .db import create_pool, init_db
from .middlewares import UserMiddleware, AntiSpamMiddleware, AnalyticsMiddleware
from .handlers import get_routers
from .services import redis_lb
from .jobs import scheduler

log = logging.getLogger("zelion")


def configure_logging():
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # aiogram is chatty on DEBUG; keep it at INFO unless we're debugging.
    if settings.LOG_LEVEL != "DEBUG":
        logging.getLogger("aiogram").setLevel(logging.WARNING)


def build_dispatcher(pool, redis) -> Dispatcher:
    dp = Dispatcher()
    dp["pool"] = pool
    dp["redis"] = redis
    for ev in (dp.message, dp.callback_query, dp.message_reaction):
        ev.middleware(UserMiddleware())
        ev.middleware(AnalyticsMiddleware())
    dp.message.middleware(AntiSpamMiddleware())
    dp.callback_query.middleware(AntiSpamMiddleware())
    for r in get_routers():
        dp.include_router(r)

    @dp.errors()
    async def _on_error(event: ErrorEvent):
        upd = getattr(event.update, "update_id", "?")
        log.exception("Unhandled error on update %s: %s", upd, event.exception)
        return True  # swallow so one bad update never kills the bot

    return dp


async def _validate_critical(bot, pool, redis):
    """Critical checks — abort startup if any fail."""
    async with pool.acquire() as con:
        await con.fetchval("SELECT 1")
    log.info("✓ PostgreSQL connection OK")

    pong = await redis.ping()
    if not pong:
        raise SystemExit("Redis PING failed.")
    log.info("✓ Redis connection OK")

    me = await bot.get_me()
    log.info("✓ Bot token OK — @%s (id %s)", me.username, me.id)

    if settings.ADMIN_IDS:
        log.info("✓ Admin IDs: %s", settings.ADMIN_IDS)
    else:
        log.warning("⚠ No ADMIN_IDS configured — admin commands are disabled.")


async def _validate_reachability(bot):
    """Soft checks — warn but do not abort (bot may be added later)."""
    for label, chat in (
        ("telegram_official", settings.TG_VERIFY["telegram_official"]),
        ("telegram_global", settings.TG_VERIFY["telegram_global"]),
    ):
        try:
            c = await bot.get_chat(chat)
            log.info("✓ Channel %s reachable: %s", chat, getattr(c, "title", c.id))
        except Exception as e:
            log.warning("⚠ %s (%s) not reachable — make the bot ADMIN there for auto-verify. (%s)",
                        label, chat, e)
    if settings.GROUP_CHAT_ID:
        try:
            g = await bot.get_chat(settings.GROUP_CHAT_ID)
            log.info("✓ Group %s reachable: %s", settings.GROUP_CHAT_ID, getattr(g, "title", g.id))
        except Exception as e:
            log.warning("⚠ Group %s not reachable — add the bot + disable privacy mode. (%s)",
                        settings.GROUP_CHAT_ID, e)


async def _bootstrap():
    configure_logging()
    static_errors = settings.validate_static()
    if static_errors:
        for e in static_errors:
            log.error("CONFIG ERROR: %s", e)
        raise SystemExit("Fix the configuration above before starting.")

    log.info("Booting Zelion Reactor — env=%s debug=%s mode=%s",
             settings.APP_ENV, settings.DEBUG, "webhook" if settings.USE_WEBHOOK else "polling")

    bot = Bot(settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    pool = await create_pool()
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    await _validate_critical(bot, pool, redis)
    await init_db(pool)
    log.info("✓ Schema + migrations applied")
    await redis_lb.ensure_seed(pool, redis)

    # Guarantee a playable quiz bank on boot (curated questions, no AI/KB needed).
    from .services import quiz_seed
    try:
        seeded = await quiz_seed.ensure_min(pool, minimum=25)
        active = await quiz_seed.count_active(pool)
        log.info("✓ Quiz bank ready — %s active question(s) (seeded %s)", active, seeded)
    except Exception as e:
        log.warning("quiz ensure_min failed: %s", e)

    # Guarantee the curated ZelionTech puzzle bank on boot (idempotent; no generic puzzles).
    from .services import puzzle_seed
    try:
        pz = await puzzle_seed.ensure_seed(pool)
        log.info("✓ ZelionTech puzzle bank ready — %s in bank (newly seeded %s)",
                 pz.get("bank"), pz.get("inserted"))
    except Exception as e:
        log.warning("puzzle ensure_seed failed: %s", e)

    # Seed progressive task chains on boot.
    from .services import tasks as tasksvc
    try:
        await tasksvc.ensure_seed(pool)
        log.info("✓ Task chains ready — %s chain(s)", await tasksvc.count_chains(pool))
    except Exception as e:
        log.warning("task seed failed: %s", e)
    await _validate_reachability(bot)

    dp = build_dispatcher(pool, redis)
    scheduler.start_all(bot, pool, redis)
    log.info("✓ Background jobs started (SLA, weekly reset, surge)")
    return bot, pool, redis, dp


async def run():
    bot, pool, redis, dp = await _bootstrap()
    from .web.server import build_app, start_web

    # The web server (API + Mini App) runs in BOTH modes so the Mini App always works.
    runner = None
    if settings.USE_WEBHOOK or settings.WEB_ALWAYS:
        app = build_app(bot, dp, pool, redis)
        runner = await start_web(app)

    try:
        if settings.USE_WEBHOOK:
            url = f"{settings.WEBHOOK_BASE}{settings.WEBHOOK_PATH}"
            await bot.set_webhook(
                url, secret_token=settings.WEBHOOK_SECRET, drop_pending_updates=True,
                allowed_updates=dp.resolve_used_update_types(),
            )
            log.info("✓ Webhook registered at %s — 🚀 running (webhook mode)", url)
            await asyncio.Event().wait()
        else:
            await bot.delete_webhook(drop_pending_updates=True)
            log.info("🚀 Starting POLLING (web API also live at :%s)…", settings.WEB_PORT)
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if runner:
            await runner.cleanup()


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
