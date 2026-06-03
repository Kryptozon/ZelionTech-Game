"""Admin panel: /admin /pending /stats /ban /unban /grant /broadcast /export."""
import asyncio
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext

from ..config import settings
from ..states import BroadcastFlow
from ..keyboards import proof_review_kb
from ..services import proof as psvc
from ..services import admin as asvc
from ..services import analytics as analytics
from ..services import events as esvc
from ..services import redis_lb
from ..services import kb as kbsvc
from ..services import ai_quiz
from ..services import quiz as quizsvc

router = Router()


def _is_admin(uid: int) -> bool:
    return settings.is_admin(uid)


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not _is_admin(message.from_user.id):
        return
    await message.answer(
        "🛠 <b>Admin panel</b>\n"
        "/pending — review proof queue\n"
        "/stats — KPIs · /analytics — DAU/WAU\n"
        "/grant <code>&lt;user_id&gt; &lt;points&gt;</code>\n"
        "/ban <code>&lt;user_id&gt; &lt;reason&gt;</code> · /unban <code>&lt;user_id&gt;</code>\n"
        "/shadow <code>&lt;user_id&gt;</code> · /unshadow <code>&lt;user_id&gt;</code>\n"
        "/surge <code>&lt;mult&gt; &lt;minutes&gt;</code> — start a power surge\n"
        "/weeklyreset — close the weekly board now\n"
        "/broadcast — message all users\n"
        "/export — users CSV\n"
        "— <b>AI Quiz</b> —\n"
        "/kbrefresh — crawl zeliontech.com into the knowledge base\n"
        "/genquiz <code>[count] [difficulty]</code> — AI-generate grounded questions\n"
        "/quizpending — review pending questions (/qok_ID · /qno_ID)"
    )


@router.message(Command("pending"))
async def cmd_pending(message: Message, pool, bot):
    if not _is_admin(message.from_user.id):
        return
    rows = await psvc.list_pending(pool, 20)
    if not rows:
        await message.answer("✅ No pending proofs. The queue is clear.")
        return
    await message.answer(f"📨 <b>{len(rows)} pending proof(s)</b> — sending for review…")
    for p in rows:
        caption = (
            f"🔔 <b>Proof #{p['id']}</b>\n"
            f"User: @{p['username']} <code>{p['user_id']}</code>\n"
            f"Mission: <b>{p['title']}</b> (+{p['xp_reward']}💎)\n"
            f"Handle: <code>{p['claimed_handle']}</code>"
        )
        try:
            await bot.send_photo(message.from_user.id, p["file_id"], caption=caption,
                                 reply_markup=proof_review_kb(p["id"]))
        except Exception:
            await message.answer(caption, reply_markup=proof_review_kb(p["id"]))


@router.message(Command("stats"))
async def cmd_stats(message: Message, pool):
    if not _is_admin(message.from_user.id):
        return
    s = await asvc.stats(pool)
    await message.answer(
        "📊 <b>Reactor stats</b>\n"
        f"👥 Users: <b>{s['total']}</b>\n"
        f"🟢 Active (24h): <b>{s['active_24h']}</b>\n"
        f"🆕 New (24h): <b>{s['new_24h']}</b>\n"
        f"📨 Pending proofs: <b>{s['pending_proofs']}</b>\n"
        f"🤝 Activated referrals: <b>{s['activated_refs']}</b>\n"
        f"⛔ Banned: <b>{s['banned']}</b>"
    )


@router.message(Command("analytics"))
async def cmd_analytics(message: Message, pool):
    if not _is_admin(message.from_user.id):
        return
    s = await analytics.summary(pool)
    rows = "\n".join(f"• {r['event']}: {r['c']}" for r in s["top_events"]) or "no events yet"
    await message.answer(
        f"📈 <b>Analytics</b>\n"
        f"👥 DAU: <b>{s['dau']}</b> · WAU: <b>{s['wau']}</b>\n\n"
        f"🎯 Missions completed (24h): <b>{s['missions_24h']}</b>\n"
        f"📨 Proofs — pending <b>{s['proofs_pending']}</b> · "
        f"approved 24h <b>{s['proofs_approved_24h']}</b> · rejected 24h <b>{s['proofs_rejected_24h']}</b>\n"
        f"🤝 Referrals — activated 24h <b>{s['refs_activated_24h']}</b> · "
        f"pending <b>{s['refs_pending']}</b>\n\n"
        f"<b>Top events (24h):</b>\n{rows}"
    )


@router.message(Command("shadow"))
async def cmd_shadow(message: Message, pool):
    if not _is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Usage: <code>/shadow &lt;user_id&gt;</code>")
        return
    await asvc.shadow_set(pool, int(parts[1]), message.from_user.id, True)
    await message.answer(f"🥷 Shadow-banned <code>{parts[1]}</code> (earns 0, unaware).")


@router.message(Command("unshadow"))
async def cmd_unshadow(message: Message, pool):
    if not _is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Usage: <code>/unshadow &lt;user_id&gt;</code>")
        return
    await asvc.shadow_set(pool, int(parts[1]), message.from_user.id, False)
    await message.answer(f"✅ Shadow-ban removed for <code>{parts[1]}</code>.")


@router.message(Command("surge"))
async def cmd_surge(message: Message, pool, redis, bot):
    if not _is_admin(message.from_user.id):
        return
    parts = message.text.split()
    mult = int(parts[1]) if len(parts) > 1 else settings.SURGE_MULT
    minutes = int(parts[2]) if len(parts) > 2 else settings.SURGE_DURATION_MIN
    await esvc.start_surge(redis, pool, bot, mult, minutes)
    await message.answer(f"⚡ Surge x{mult} started for {minutes} min (announced to group).")


@router.message(Command("weeklyreset"))
async def cmd_weeklyreset(message: Message, pool, redis, bot):
    if not _is_admin(message.from_user.id):
        return
    top3 = await redis_lb.snapshot_and_reset_week(pool, redis)
    names = {}
    if top3:
        from ..services import leaderboard
        names = await leaderboard.names_for(pool, [uid for uid, _ in top3])
    medals = ["🥇", "🥈", "🥉"]
    body = "\n".join(f"{medals[i]} {names.get(uid, uid)} — {sc}💎"
                     for i, (uid, sc) in enumerate(top3)) or "no entries"
    # Award weekly bonuses to winners.
    for i, (uid, _sc) in enumerate(top3):
        if i < len(settings.WEEKLY_BONUS):
            await asvc.grant_points(pool, uid, settings.WEEKLY_BONUS[i], message.from_user.id, redis=redis)
    await message.answer(f"📅 Weekly board closed.\n{body}")


@router.message(Command("kbrefresh"))
async def cmd_kbrefresh(message: Message, pool):
    if not _is_admin(message.from_user.id):
        return
    await message.answer("🌐 Crawling zeliontech.com… this can take a minute.")
    summary = await kbsvc.refresh(pool)
    await message.answer(
        f"✅ Knowledge base updated.\nPages: <b>{summary['pages']}</b> · "
        f"Chunks: <b>{summary['chunks']}</b> · Visited: {summary['visited']}\n"
        f"Now run /genquiz to generate questions."
    )


@router.message(Command("genquiz"))
async def cmd_genquiz(message: Message, pool):
    if not _is_admin(message.from_user.id):
        return
    parts = message.text.split()
    count = int(parts[1]) if len(parts) > 1 else 5
    difficulty = int(parts[2]) if len(parts) > 2 else 1
    await message.answer(f"🤖 Generating {count} grounded questions (difficulty {difficulty})…")
    res = await ai_quiz.generate(pool, count=count, difficulty=difficulty)
    await message.answer(
        f"✅ Generated <b>{res.get('inserted', 0)}</b> question(s) "
        f"(mode: {res.get('mode', '-')}). They are PENDING — review in the Mini App "
        f"admin screen or with /quizpending."
        + (f"\n⚠️ {res['reason']}" if res.get("reason") else "")
    )


@router.message(Command("quizpending"))
async def cmd_quizpending(message: Message, pool):
    if not _is_admin(message.from_user.id):
        return
    rows = await quizsvc.admin_list(pool, "pending", 10)
    if not rows:
        await message.answer("✅ No pending questions.")
        return
    a = await quizsvc.analytics(pool)
    lines = [f"📋 <b>{len(rows)} pending</b> (approved {a['approved']}, total {a['total']})\n"]
    for r in rows:
        import json as _j
        opts = _j.loads(r["options"]) if isinstance(r["options"], str) else r["options"]
        correct = opts[r["correct_index"]]
        lines.append(
            f"#{r['id']} [D{r['difficulty']}] {r['question']}\n"
            f"   ✅ {correct}\n   src: {r['source_url']}\n"
            f"   /qok_{r['id']}  ·  /qno_{r['id']}"
        )
    await message.answer("\n".join(lines))


@router.message(F.text.regexp(r"^/qok_(\d+)$"))
async def cmd_qok(message: Message, pool):
    if not _is_admin(message.from_user.id):
        return
    qid = int(message.text.split("_")[1])
    await quizsvc.set_status(pool, qid, "approved", message.from_user.id)
    await message.answer(f"✅ Question #{qid} approved — now live in the quiz.")


@router.message(F.text.regexp(r"^/qno_(\d+)$"))
async def cmd_qno(message: Message, pool):
    if not _is_admin(message.from_user.id):
        return
    qid = int(message.text.split("_")[1])
    await quizsvc.set_status(pool, qid, "rejected", message.from_user.id)
    await message.answer(f"🗑 Question #{qid} rejected.")


@router.message(Command("grant"))
async def cmd_grant(message: Message, pool, redis, bot):
    if not _is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Usage: <code>/grant &lt;user_id&gt; &lt;points&gt;</code>")
        return
    uid, amount = int(parts[1]), int(parts[2])
    await asvc.grant_points(pool, uid, amount, message.from_user.id, redis=redis)
    await message.answer(f"✅ Granted {amount}💎 to <code>{uid}</code>.")
    try:
        await bot.send_message(uid, f"🎁 An admin granted you <b>+{amount}💎</b>!")
    except Exception:
        pass


@router.message(Command("ban"))
async def cmd_ban(message: Message, pool):
    if not _is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("Usage: <code>/ban &lt;user_id&gt; [reason]</code>")
        return
    uid = int(parts[1])
    reason = parts[2] if len(parts) > 2 else "Policy violation"
    await asvc.ban_user(pool, uid, message.from_user.id, reason)
    await message.answer(f"⛔ Banned <code>{uid}</code> — {reason}")


@router.message(Command("unban"))
async def cmd_unban(message: Message, pool):
    if not _is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Usage: <code>/unban &lt;user_id&gt;</code>")
        return
    await asvc.unban_user(pool, int(parts[1]), message.from_user.id)
    await message.answer(f"✅ Unbanned <code>{parts[1]}</code>.")


@router.message(Command("export"))
async def cmd_export(message: Message, pool):
    if not _is_admin(message.from_user.id):
        return
    csv = await asvc.export_users_csv(pool)
    await message.answer_document(
        BufferedInputFile(csv.encode("utf-8"), filename="zelion_users.csv")
    )


# ---------------- Broadcast ----------------
@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    await state.set_state(BroadcastFlow.waiting_message)
    await message.answer("📢 Send the message to broadcast to all users. /cancel to abort.")


@router.message(BroadcastFlow.waiting_message, F.text == "/cancel")
async def broadcast_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Cancelled.")


@router.message(BroadcastFlow.waiting_message)
async def broadcast_send(message: Message, state: FSMContext, pool, bot):
    await state.clear()
    ids = await asvc.all_user_ids(pool)
    await message.answer(f"📡 Broadcasting to {len(ids)} users…")
    sent = 0
    for uid in ids:
        try:
            await bot.copy_message(uid, message.chat.id, message.message_id)
            sent += 1
        except Exception:
            pass
        if sent % 25 == 0:
            await asyncio.sleep(1)  # ~25 msg/sec throttle
    await message.answer(f"✅ Broadcast done. Delivered to {sent}/{len(ids)}.")
