"""aiohttp server: serves /api/*, the built Mini App at /app, and (webhook mode) /webhook."""
import os
import logging
from aiohttp import web

from ..config import settings
from .api import setup_api

log = logging.getLogger("zelion.web")


def _dist_dir():
    d = settings.FRONTEND_DIST
    if not os.path.isabs(d):
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), d)
    return d


async def health(request):
    return web.json_response({"status": "ok", "service": "zelion-reactor"})


async def spa_handler(request):
    """Serve the built Mini App; fall back to index.html for client-side routes."""
    dist = _dist_dir()
    rel = request.match_info.get("path", "").lstrip("/")
    candidate = os.path.normpath(os.path.join(dist, rel))
    if rel and candidate.startswith(dist) and os.path.isfile(candidate):
        return web.FileResponse(candidate)
    index = os.path.join(dist, "index.html")
    if os.path.isfile(index):
        return web.FileResponse(index)
    return web.json_response(
        {"error": "frontend not built", "hint": "run `npm --prefix frontend run build`"},
        status=503,
    )


def build_app(bot, dp, pool, redis) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app["dp"] = dp
    app["pool"] = pool
    app["redis"] = redis

    app.router.add_get("/health", health)
    setup_api(app)

    # Webhook (only registered in webhook mode).
    if settings.USE_WEBHOOK:
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        SimpleRequestHandler(
            dispatcher=dp, bot=bot, secret_token=settings.WEBHOOK_SECRET
        ).register(app, path=settings.WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)

    # Mini App static (must be last so /api and /webhook win).
    app.router.add_get("/app", spa_handler)
    app.router.add_get("/app/{path:.*}", spa_handler)
    return app


async def start_web(app: web.Application):
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.WEB_HOST, settings.WEB_PORT)
    await site.start()
    log.info("🌐 Web server on %s:%s  (Mini App at %s)",
             settings.WEB_HOST, settings.WEB_PORT, settings.MINIAPP_URL)
    return runner
