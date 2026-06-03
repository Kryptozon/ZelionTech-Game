"""Proof submission FSM + admin approve/reject callbacks."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from ..config import settings
from ..states import ProofFlow, RejectFlow
from ..keyboards import back_menu, proof_review_kb
from ..texts import (
    PROOF_ASK_HANDLE, PROOF_ASK_SCREENSHOT, PROOF_PENDING, PROOF_DUPLICATE,
    PROOF_APPROVED_USER, PROOF_REJECTED_USER,
)
from ..services import proof as psvc
from ..services import missions as msvc

router = Router()


# ---------------- User: submit proof ----------------
@router.callback_query(F.data.startswith("proof:start:"))
async def proof_start(cb: CallbackQuery, pool, state: FSMContext):
    mid = int(cb.data.split(":")[2])
    m = await msvc.get_mission(pool, mid)
    cur = await msvc.social_mission_state(pool, cb.from_user.id, mid)
    if cur in ("pending", "approved"):
        await cb.answer(PROOF_DUPLICATE, show_alert=True)
        return
    await state.set_state(ProofFlow.waiting_handle)
    await state.update_data(mission_id=mid, platform=m["platform"])
    await cb.message.answer(PROOF_ASK_HANDLE.format(title=m["title"]))
    await cb.answer()


@router.message(ProofFlow.waiting_handle, F.text)
async def proof_handle(message: Message, state: FSMContext):
    handle = message.text.strip()[:128]
    await state.update_data(handle=handle)
    await state.set_state(ProofFlow.waiting_screenshot)
    await message.answer(PROOF_ASK_SCREENSHOT)


@router.message(ProofFlow.waiting_screenshot, F.photo)
async def proof_screenshot(message: Message, state: FSMContext, pool, bot):
    data = await state.get_data()
    file_id = message.photo[-1].file_id
    mid = data["mission_id"]
    pid = await psvc.create_submission(
        pool, message.from_user.id, mid, data["platform"], data["handle"], file_id
    )
    await state.clear()
    if pid is None:
        await message.answer(PROOF_DUPLICATE, reply_markup=back_menu())
        return
    m = await msvc.get_mission(pool, mid)
    await message.answer(PROOF_PENDING.format(xp=m["xp_reward"]), reply_markup=back_menu())

    # Push to all admins for review
    caption = (
        f"🔔 <b>Proof #{pid} — pending</b>\n"
        f"User: {message.from_user.full_name} (@{message.from_user.username}) "
        f"<code>{message.from_user.id}</code>\n"
        f"Mission: <b>{m['title']}</b> (+{m['xp_reward']}💎)\n"
        f"Claimed handle: <code>{data['handle']}</code>"
    )
    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_photo(admin_id, file_id, caption=caption, reply_markup=proof_review_kb(pid))
        except Exception:
            pass


@router.message(ProofFlow.waiting_screenshot)
async def proof_need_photo(message: Message):
    await message.answer("📷 Please upload a <b>screenshot image</b> to finish your proof.")


# ---------------- Admin: approve ----------------
@router.callback_query(F.data.startswith("padm:approve:"))
async def admin_approve(cb: CallbackQuery, pool, redis, bot):
    if not settings.is_admin(cb.from_user.id):
        await cb.answer("Not authorized.", show_alert=True)
        return
    pid = int(cb.data.split(":")[2])
    res = await psvc.approve(pool, pid, cb.from_user.id, redis=redis)
    if res is None:
        await cb.answer("Already reviewed.", show_alert=True)
        return
    if res == "dup":
        await cb.message.edit_caption(caption=f"❌ Proof #{pid} auto-rejected: duplicate handle.")
        await cb.answer("Duplicate handle — rejected.")
        return
    await cb.message.edit_caption(caption=f"✅ Proof #{pid} approved by you. +{res['xp']}💎 granted.")
    await cb.answer("Approved ✅")
    try:
        await bot.send_message(
            res["user_id"], PROOF_APPROVED_USER.format(xp=res["xp"], title=res["title"])
        )
        # Level-up notice (referral activation already resolved inside approve()).
        if res.get("leveled"):
            from ..services import economy
            from ..texts import LEVEL_UP
            rank = economy.RANKS.get(res["level"], "⚡ Spark")
            await bot.send_message(res["user_id"], LEVEL_UP.format(rank=rank, level=res["level"]))
        if res.get("referrer"):
            from ..texts import REFERRAL_SUCCESS
            await bot.send_message(res["referrer"], REFERRAL_SUCCESS)
    except Exception:
        pass


# ---------------- Admin: reject (asks reason) ----------------
@router.callback_query(F.data.startswith("padm:reject:"))
async def admin_reject_start(cb: CallbackQuery, state: FSMContext):
    if not settings.is_admin(cb.from_user.id):
        await cb.answer("Not authorized.", show_alert=True)
        return
    pid = int(cb.data.split(":")[2])
    await state.set_state(RejectFlow.waiting_reason)
    await state.update_data(pid=pid)
    await cb.message.reply("✍️ Send the <b>rejection reason</b> (the user will see it).")
    await cb.answer()


@router.message(RejectFlow.waiting_reason, F.text)
async def admin_reject_reason(message: Message, state: FSMContext, pool, bot):
    if not settings.is_admin(message.from_user.id):
        return
    data = await state.get_data()
    await state.clear()
    reason = message.text.strip()[:256]
    res = await psvc.reject(pool, data["pid"], message.from_user.id, reason)
    if res is None:
        await message.answer("Already reviewed.")
        return
    m = await msvc.get_mission(pool, res["mission_id"])
    await message.answer(f"❌ Proof #{data['pid']} rejected.")
    try:
        await bot.send_message(
            res["user_id"], PROOF_REJECTED_USER.format(title=m["title"], reason=reason)
        )
    except Exception:
        pass
