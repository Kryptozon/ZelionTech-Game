"""Phase 2/3: surge hours + weekly events."""
import json
from ..config import settings


async def start_surge(redis, pool, bot, mult: int, minutes: int):
    """Activate a global surge (points multiplier) for `minutes`, announce to the group."""
    await redis.set("surge:mult", str(mult), ex=minutes * 60)
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO events(kind, detail) VALUES('surge', $1)",
            json.dumps({"mult": mult, "minutes": minutes}),
        )
    text = (
        f"⚡⚡ <b>POWER SURGE ACTIVE!</b> ⚡⚡\n"
        f"All points are <b>x{mult}</b> for the next <b>{minutes} minutes</b>.\n"
        f"Claim, run quizzes, and chat in the group NOW to cash in! 🔋"
    )
    if settings.GROUP_CHAT_ID:
        try:
            await bot.send_message(settings.GROUP_CHAT_ID, text)
        except Exception:
            pass
    return text


async def surge_active(redis) -> int:
    v = await redis.get("surge:mult")
    try:
        return int(v) if v else 1
    except (TypeError, ValueError):
        return 1
