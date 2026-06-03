"""Phase 2: reward real messages & reactions in the ZelionTech group."""
from aiogram import Router, F
from aiogram.types import Message, MessageReactionUpdated

from ..config import settings
from ..services import group as gsvc
from ..services import users as usvc

router = Router()


def _is_target_group(chat_id: int) -> bool:
    return settings.GROUP_CHAT_ID == 0 or chat_id == settings.GROUP_CHAT_ID


# Group text messages -> small XP (capped, anti-flood). Commands excluded.
@router.message(F.chat.type.in_({"group", "supergroup"}), F.text)
async def group_message(message: Message, pool, redis):
    if not _is_target_group(message.chat.id) or not message.from_user:
        return
    if message.text.startswith("/"):
        return
    await usvc.ensure_user(pool, message.from_user.id,
                           message.from_user.username or "", message.from_user.first_name or "")
    await gsvc.reward_message(pool, redis, message.from_user.id,
                             message.chat.id, message.message_id, message.text)


# Reactions -> XP (capped). Only when a NEW reaction is added.
@router.message_reaction()
async def on_reaction(event: MessageReactionUpdated, pool, redis):
    if not _is_target_group(event.chat.id) or not event.user:
        return
    if not event.new_reaction:  # reaction removed
        return
    await usvc.ensure_user(pool, event.user.id, event.user.username or "", event.user.first_name or "")
    await gsvc.reward_reaction(pool, redis, event.user.id, event.chat.id, event.message_id)
