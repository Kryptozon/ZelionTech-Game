"""Missions menu, social mission detail, Telegram auto-verify, learn quizzes."""
import json
from aiogram import Router, F
from aiogram.types import CallbackQuery

from ..keyboards import social_list, social_detail, learn_list, quiz_options, back_menu
from ..services import missions as msvc
from ..services import economy
from ..services import analytics
from ..services.social_verify import verify_telegram_join
from .core import post_award

router = Router()


@router.callback_query(F.data == "missions")
async def cb_missions(cb: CallbackQuery, pool):
    learn = await msvc.list_learn(pool)
    await cb.message.edit_text(
        "🎯 <b>Clearance Tests</b>\nAnswer ZelionTech quizzes to earn  ZLN-XP.\n"
        "(Each costs ⚡ energy and has a cooldown.)",
        reply_markup=learn_list(learn),
    )
    await cb.answer()


# ---------------- Social missions ----------------
@router.callback_query(F.data == "social:list")
async def cb_social_list(cb: CallbackQuery, pool):
    mlist = await msvc.list_social(pool)
    states = {m["id"]: await msvc.social_mission_state(pool, cb.from_user.id, m["id"]) for m in mlist}
    await cb.message.edit_text(
        "📡 <b>Social Missions</b>\nFollow ZelionTech's official channels.\n"
        "• Telegram = instant auto-verify ✅\n"
        "• Others = submit proof, reviewed within 24h ⏳\n\n"
        "✅ done · ⏳ pending · 🔁 re-submit · ▫️ not started",
        reply_markup=social_list(mlist, states),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("social:open:"))
async def cb_social_open(cb: CallbackQuery, pool):
    mid = int(cb.data.split(":")[2])
    m = await msvc.get_mission(pool, mid)
    state = await msvc.social_mission_state(pool, cb.from_user.id, mid)
    if m["verification"] == "auto":
        how = ("1️⃣ Tap <b>Open page</b> and JOIN.\n"
               "2️⃣ Tap <b>Verify now</b> — points are added instantly. ⚡")
    else:
        how = ("1️⃣ Tap <b>Open page</b> and follow/join.\n"
               "2️⃣ Tap <b>Submit Proof</b>, send username + screenshot.\n"
               "3️⃣ Admin reviews within <b>24h</b> → points added automatically.")
    status_line = {
        "approved": "✅ Already completed.",
        "pending": "⏳ Proof pending review (within 24h).",
        "rejected": "🔁 Previous proof rejected — re-submit.",
        "none": "▫️ Not started yet.",
    }[state]
    await cb.message.edit_text(
        f"📡 <b>{m['title']}</b> · Reward <b>+{m['xp_reward']} ZLN-XP</b>\n\n"
        f"{m['description']}\n\n{how}\n\n{status_line}",
        reply_markup=social_detail(m, state),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("social:verify:"))
async def cb_social_verify(cb: CallbackQuery, pool, redis, bot):
    mid = int(cb.data.split(":")[2])
    m = await msvc.get_mission(pool, mid)
    if await msvc.social_mission_state(pool, cb.from_user.id, mid) == "approved":
        await cb.answer("Already verified ✅", show_alert=True)
        return
    ok = await verify_telegram_join(bot, m["platform"], cb.from_user.id)
    if not ok:
        await cb.answer("❌ Not joined yet. Open the page, JOIN, then tap Verify.", show_alert=True)
        return
    # Mark as an approved proof so it shows ✅ and can't be re-claimed; award once.
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO proof_submissions(user_id, mission_id, platform, claimed_handle, status, reviewed_at) "
            "VALUES($1,$2,$3,'auto','approved', now())",
            cb.from_user.id, mid, m["platform"],
        )
        await con.execute(
            "INSERT INTO social_accounts(user_id, platform, handle, verified) VALUES($1,$2,$3,true) "
            "ON CONFLICT (platform, handle) DO NOTHING",
            cb.from_user.id, m["platform"], f"tg:{cb.from_user.id}",
        )
    award = await economy.award_points(pool, cb.from_user.id, m["xp_reward"], "proof",
                                       f"tgjoin:{mid}:{cb.from_user.id}", redis=redis)
    await cb.message.edit_text(
        f"✅ <b>Verified!</b> +{m['xp_reward']} ZLN-XP for {m['title']}. ⚡",
        reply_markup=back_menu("social:list"),
    )
    await cb.answer("Verified ✅")
    await post_award(pool, redis, bot, cb.from_user.id, award)


# ---------------- Quiz ----------------
@router.callback_query(F.data.startswith("quiz:open:"))
async def cb_quiz_open(cb: CallbackQuery, pool):
    mid = int(cb.data.split(":")[2])
    m = await msvc.get_mission(pool, mid)
    if not await msvc.quiz_eligible(pool, cb.from_user.id, mid):
        await cb.answer("⏳ This test is on cooldown. Try later.", show_alert=True)
        return
    await cb.message.edit_text(
        f"🧠 <b>{m['title']}</b> · +{m['xp_reward']} ZLN-XP · cost {m['energy_cost']}⚡\n\n{m['quiz_question']}",
        reply_markup=quiz_options(m),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("quiz:ans:"))
async def cb_quiz_answer(cb: CallbackQuery, pool, redis, bot):
    _, _, mid, idx = cb.data.split(":")
    mid, idx = int(mid), int(idx)
    m = await msvc.get_mission(pool, mid)

    if not await msvc.quiz_eligible(pool, cb.from_user.id, mid):
        await cb.answer("⏳ On cooldown.", show_alert=True)
        return

    opts = m["quiz_options"]
    if isinstance(opts, str):
        opts = json.loads(opts)
    if not opts[idx]["correct"]:
        await cb.answer("❌ Not quite. Try again in a moment.", show_alert=True)
        return

    if not await economy.spend_energy(pool, cb.from_user.id, m["energy_cost"]):
        await cb.answer("⚡ Not enough energy. Claim or wait for regen.", show_alert=True)
        return

    await msvc.record_completion(pool, cb.from_user.id, mid, m["cooldown_sec"])
    ref = f"{mid}:{cb.message.date.strftime('%Y-%m-%d-%H')}"
    award = await economy.award_points(pool, cb.from_user.id, m["xp_reward"], "quiz", ref,
                                       redis=redis, surge=True)
    await analytics.log_event(pool, cb.from_user.id, "mission_complete",
                              {"mission_id": mid, "type": "quiz"})
    surge = award.get("multiplier", 1)
    extra = f" (⚡SURGE x{surge})" if surge > 1 else ""
    await cb.message.edit_text(
        f"✅ <b>Correct!</b> +{m['xp_reward']} ZLN-XP{extra}\nNice clearance, Operator. ⚡",
        reply_markup=back_menu("missions"),
    )
    await cb.answer("Correct! ✅")
    await post_award(pool, redis, bot, cb.from_user.id, award)
