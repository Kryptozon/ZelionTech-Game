"""Phase 2: Telegram auto-verification via getChatMember.

The bot must be a MEMBER (for public groups) or ADMIN (for channels) of the
target chat for getChatMember to succeed on arbitrary users.
"""
from aiogram import Bot
from ..config import settings

JOINED_STATUSES = {"member", "administrator", "creator"}


async def verify_telegram_join(bot: Bot, platform: str, user_id: int) -> bool:
    chat = settings.TG_VERIFY.get(platform)
    if not chat:
        return False
    try:
        member = await bot.get_chat_member(chat, user_id)
        return member.status in JOINED_STATUSES
    except Exception:
        # User not found / bot lacks rights / chat invalid -> treat as not joined.
        return False
