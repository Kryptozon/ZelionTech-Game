"""Proof submission via bot DM. The screenshot is saved in the DB and reviewed in
the Mini App Admin Dashboard (no Telegram forwarding / review callbacks)."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from ..states import ProofFlow
from ..keyboards import back_menu
from ..texts import PROOF_ASK_HANDLE, PROOF_ASK_SCREENSHOT, PROOF_PENDING, PROOF_DUPLICATE
from ..services import proof as psvc
from ..services import missions as msvc

router = Router()


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
    await state.update_data(handle=message.text.strip()[:128])
    await state.set_state(ProofFlow.waiting_screenshot)
    await message.answer(PROOF_ASK_SCREENSHOT)


@router.message(ProofFlow.waiting_screenshot, F.photo)
async def proof_screenshot(message: Message, state: FSMContext, pool, bot):
    data = await state.get_data()
    await state.clear()
    # Download the screenshot bytes and store them in the DB (no forwarding).
    try:
        buf = await bot.download(message.photo[-1])
        image = buf.read()
    except Exception:
        image = None
    pid = await psvc.create_submission(
        pool, message.from_user.id, data["mission_id"], data["platform"], data["handle"],
        screenshot=image, mime="image/jpeg",
        username=message.from_user.username or message.from_user.full_name,
    )
    if pid is None:
        await message.answer(PROOF_DUPLICATE, reply_markup=back_menu())
        return
    if pid == "too_large":
        await message.answer("⚠️ That image is too large (max 3 MB). Send a smaller screenshot.")
        return
    m = await msvc.get_mission(pool, data["mission_id"])
    await message.answer(
        PROOF_PENDING.format(xp=m["xp_reward"]) + "\n📥 An admin will review it in the dashboard.",
        reply_markup=back_menu(),
    )


@router.message(ProofFlow.waiting_screenshot)
async def proof_need_photo(message: Message):
    await message.answer("📷 Please upload a <b>screenshot image</b> to finish your proof.")
