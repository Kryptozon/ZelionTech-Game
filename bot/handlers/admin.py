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
from ..services import kb_doc
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
        "/seedquestions — seed curated + KB question bank (target 300, approved)\n"
        "/kbimport — import seed document(s) from /knowledge\n"
        "/kbrefresh — rebuild KB from document(s) + zeliontech.com\n"
        "/genquiz — (re)build the approved question bank\n"
        "/quizstats — question bank + attempts stats\n"
        "/quizpending — review pending questions (/qok_ID · /qno_ID)"
    )


@router.message(Command("pending"))
async def cmd_pending(message: Message, pool):
    """Proof moderation now lives in the Mini App Admin Dashboard."""
    if not _is_admin(message.from_user.id):
        return
    s = await psvc.dashboard_stats(pool)
    await message.answer(
        f"🗂 <b>Proof moderation moved to the Mini App.</b>\n\n"
        f"Open <b>🎮 Zelion Reactor → Admin tab</b> to approve / reject / ban with screenshots.\n\n"
        f"📨 Pending: <b>{s['pending']}</b>\n"
        f"✅ Approved today: <b>{s['approved_today']}</b>\n"
        f"❌ Rejected today: <b>{s['rejected_today']}</b>\n"
        f"💰 ZLN-XP distributed: <b>{s['zln_distributed']}</b>\n"
        f"🚫 Banned: <b>{s['banned']}</b>"
    )


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
    body = "\n".join(f"{medals[i]} {names.get(uid, uid)} — {sc} ZLN-XP"
                     for i, (uid, sc) in enumerate(top3)) or "no entries"
    # Award weekly bonuses to winners.
    for i, (uid, _sc) in enumerate(top3):
        if i < len(settings.WEEKLY_BONUS):
            await asvc.grant_points(pool, uid, settings.WEEKLY_BONUS[i], message.from_user.id, redis=redis)
    await message.answer(f"📅 Weekly board closed.\n{body}")


@router.message(Command("kbimport"))
async def cmd_kbimport(message: Message, pool):
    if not _is_admin(message.from_user.id):
        return
    await message.answer("📄 Importing seed documents from /knowledge …")
    try:
        docs = await kb_doc.import_all(pool)
        names = ", ".join(docs["names"]) or "none found"
        await message.answer(
            f"✅ Document KB imported.\nFiles: <b>{docs['files']}</b> · "
            f"Chunks: <b>{docs['chunks']}</b>\nSources: {names}"
        )
    except Exception as e:
        await message.answer(f"❌ /kbimport failed: <code>{e}</code>")


@router.message(Command("kbrefresh"))
async def cmd_kbrefresh(message: Message, pool):
    if not _is_admin(message.from_user.id):
        return
    await message.answer("🔄 Rebuilding knowledge base from document(s) + zeliontech.com …")
    try:
        docs = await kb_doc.import_all(pool)
        site = await kbsvc.refresh(pool)
        cats = await kbsvc.stats_by_category(pool)
        top = "\n".join(f"• {c['category']} ({c['source_type']}): {c['c']}" for c in cats[:8]) or "—"
        await message.answer(
            f"✅ Knowledge base rebuilt.\n"
            f"📄 Document chunks: <b>{docs['chunks']}</b> ({docs['files']} files)\n"
            f"🌐 Website chunks: <b>{site['chunks']}</b> ({site['pages']} pages)\n\n"
            f"<b>By category:</b>\n{top}\n\nRun /genquiz to (re)build the question bank."
        )
    except Exception as e:
        await message.answer(f"❌ /kbrefresh failed: <code>{e}</code>\nDocuments may still be usable — try /seedquestions.")


@router.message(Command("seedquestions"))
async def cmd_seedquestions(message: Message, pool):
    """Insert the curated + KB-generated approved question bank (target 300). Idempotent."""
    if not _is_admin(message.from_user.id):
        return
    from ..services import quiz_seed
    await message.answer("🌱 Seeding the Zelion question bank (curated + knowledge base, target 300)…")
    try:
        res = await quiz_seed.seed(pool, target=300)
        await message.answer(
            f"✅ Seed complete.\n"
            f"📘 Curated inserted: <b>{res['curated']}</b>\n"
            f"🧩 KB-generated: <b>{res['generated']}</b>\n"
            f"🧠 Active approved questions now: <b>{res['active_total']}</b> / {res['target']}\n"
            f"All approved & active — daily quiz is live. (idempotent: safe to re-run)"
        )
    except Exception as e:
        await message.answer(f"❌ /seedquestions failed: <code>{e}</code>")


@router.message(Command("genquiz"))
async def cmd_genquiz(message: Message, pool):
    """(Re)build the question bank: curated + KB-generated approved questions (req #16)."""
    if not _is_admin(message.from_user.id):
        return
    from ..services import quiz_seed
    await message.answer("🤖 Building the question bank from the Zelion knowledge base…")
    try:
        res = await quiz_seed.seed(pool, target=300)
        a = await quizsvc.analytics(pool)
        await message.answer(
            f"✅ Question bank ready.\n"
            f"Active approved questions: <b>{a['approved']}</b>\n"
            f"(curated +{res['curated']}, KB-generated +{res['generated']})\n"
            f"Users now get 5 daily questions. 🧠"
        )
    except Exception as e:
        await message.answer(f"❌ /genquiz failed: <code>{e}</code>")


@router.message(Command("quizstats"))
async def cmd_quizstats(message: Message, pool):
    if not _is_admin(message.from_user.id):
        return
    try:
        a = await quizsvc.analytics(pool)
        diffs = " · ".join(f"D{r['difficulty']}:{r['c']}" for r in a["by_difficulty"]) or "—"
        await message.answer(
            f"📊 <b>Quiz stats</b>\n"
            f"Total questions: <b>{a['total']}</b>\n"
            f"Active approved: <b>{a['approved']}</b> ({diffs})\n"
            f"Pending: <b>{a['pending']}</b>\n"
            f"Attempts (24h): <b>{a['attempts_24h']}</b>\n"
            f"Daily sessions (24h): <b>{a['daily_sessions_24h']}</b>\n"
            f"Accuracy (7d): <b>{a['accuracy_7d'] or 0}%</b>"
        )
    except Exception as e:
        await message.answer(f"❌ /quizstats failed: <code>{e}</code>")


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
    await message.answer(f"✅ Granted {amount} ZLN-XP to <code>{uid}</code>.")
    try:
        await bot.send_message(uid, f"🎁 An admin granted you <b>+{amount} ZLN-XP</b>!")
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
