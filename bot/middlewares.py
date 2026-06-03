from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from redis.asyncio import Redis

from .services.users import ensure_user, is_banned
from .services.analytics import log_event
from .texts import BANNED, ANTICHEAT_WARNING

SPAM_TTL = 2  # seconds between actions


class UserMiddleware(BaseMiddleware):
    """Upsert user, block hard-banned users (shadow-bans pass through silently)."""

    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = getattr(event, "from_user", None)
        pool = data.get("pool")
        if user and pool:
            if await is_banned(pool, user.id):
                if isinstance(event, Message):
                    await event.answer(BANNED)
                elif isinstance(event, CallbackQuery):
                    await event.answer(BANNED, show_alert=True)
                return
            data["db_user"] = await ensure_user(
                pool, user.id, user.username or "", user.first_name or ""
            )
        return await handler(event, data)


class AntiSpamMiddleware(BaseMiddleware):
    """Per-user debounce for button taps only.

    Messages are NOT debounced here — that previously dropped proof FSM steps
    (handle text / screenshot photo), so proofs never reached admins. Message
    flooding is handled by group anti-flood and per-feature limits instead.
    """

    async def __call__(self, handler, event: TelegramObject, data: dict):
        if not isinstance(event, CallbackQuery):
            return await handler(event, data)
        user = getattr(event, "from_user", None)
        redis: Redis = data.get("redis")
        if user and redis:
            if not await redis.set(f"spam:{user.id}", "1", nx=True, ex=SPAM_TTL):
                await event.answer(ANTICHEAT_WARNING, show_alert=False)
                return
        return await handler(event, data)


class AnalyticsMiddleware(BaseMiddleware):
    """Phase 3: log a lightweight event per interaction."""

    async def __call__(self, handler, event: TelegramObject, data: dict):
        pool = data.get("pool")
        user = getattr(event, "from_user", None)
        if pool and user:
            if isinstance(event, CallbackQuery):
                name = (event.data or "cb").split(":")[0]
                await log_event(pool, user.id, f"cb:{name}")
            elif isinstance(event, Message):
                if event.text and event.text.startswith("/"):
                    await log_event(pool, user.id, f"cmd:{event.text.split()[0][1:]}")
                else:
                    await log_event(pool, user.id, "msg")
        return await handler(event, data)
