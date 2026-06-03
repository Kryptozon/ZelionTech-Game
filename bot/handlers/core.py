"""Start, main menu, claim energy, invite, profile, leaderboard, help."""
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from ..config import settings
from ..keyboards import main_menu, invite_kb, lb_tabs, back_menu
from ..texts import WELCOME, HOW_TO_PLAY, LEVEL_UP, REFERRAL_SUCCESS
from ..services import economy, users, leaderboard, redis_lb

router = Router()


async def menu_text(pool, user_id: int) -> str:
    u = await users.get_user(pool, user_id)
    cur, cap = await economy.energy_status(pool, user_id)
    rank = economy.RANKS.get(u["level"], "⚡ Spark")
    return (
        f"🔋 <b>Zelion Reactor — Main Menu</b>\n\n"
        f"⚡ Energy: <b>{cur}/{cap}</b>\n"
        f"💎 Points: <b>{u['points']}</b>\n"
        f"🏅 Rank: <b>{rank}</b> (Lv.{u['level']})\n"
        f"🔥 Streak: <b>{u['streak_count']}</b> days"
    )


@router.message(CommandStart())
async def cmd_start(message: Message, pool):
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            await users.set_referrer(pool, message.from_user.id, int(args[1][4:]))
        except ValueError:
            pass
    await message.answer(WELCOME, reply_markup=main_menu())


@router.message(Command("menu"))
async def cmd_menu(message: Message, pool):
    await message.answer(await menu_text(pool, message.from_user.id), reply_markup=main_menu())


@router.callback_query(F.data == "menu")
async def cb_menu(cb: CallbackQuery, pool):
    await cb.message.edit_text(await menu_text(pool, cb.from_user.id), reply_markup=main_menu())
    await cb.answer()


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(HOW_TO_PLAY, reply_markup=back_menu())


@router.callback_query(F.data == "help")
async def cb_help(cb: CallbackQuery):
    await cb.message.edit_text(HOW_TO_PLAY, reply_markup=back_menu())
    await cb.answer()


# ---------------- Claim energy ----------------
@router.callback_query(F.data == "claim")
async def cb_claim(cb: CallbackQuery, pool, redis, bot):
    res = await economy.claim_daily(pool, cb.from_user.id, redis=redis)
    if res["status"] == "cooldown":
        h = res["seconds"] // 3600
        m = (res["seconds"] % 3600) // 60
        await cb.answer(f"⏳ Next charge in {h}h {m}m. (+5⚡/hr meanwhile)", show_alert=True)
        return
    surge = res["award"].get("multiplier", 1)
    surge_line = f"\n⚡ <b>SURGE x{surge}!</b>" if surge > 1 else ""
    streak_mult = "×2" if res["streak"] >= 7 else ""
    await cb.message.edit_text(
        f"✅ <b>Reactor charged!</b>\n+{res['energy']}⚡  +{res['xp']}💎\n"
        f"🔥 Streak: Day {res['streak']} {streak_mult}{surge_line}",
        reply_markup=back_menu(),
    )
    await cb.answer("Charged! ⚡")
    await post_award(pool, redis, bot, cb.from_user.id, res["award"])


# ---------------- Invite ----------------
@router.callback_query(F.data == "invite")
async def cb_invite(cb: CallbackQuery, pool):
    link = f"https://t.me/{settings.BOT_USERNAME}?start=ref_{cb.from_user.id}"
    activated, pending = await users.referral_stats(pool, cb.from_user.id)
    await cb.message.edit_text(
        f"👥 <b>Recruit Operators</b>\n\n"
        f"Your link:\n<code>{link}</code>\n\n"
        f"✅ Activated: <b>{activated}</b>\n⏳ Pending: <b>{pending}</b>\n\n"
        f"You earn <b>+150💎 +50⚡</b> when a recruit activates "
        f"(stays 24h and reaches 50💎). Fake invites don't count.",
        reply_markup=invite_kb(link),
    )
    await cb.answer()


# ---------------- Profile ----------------
@router.callback_query(F.data == "profile")
async def cb_profile(cb: CallbackQuery, pool, redis):
    u = await users.get_user(pool, cb.from_user.id)
    cur, cap = await economy.energy_status(pool, cb.from_user.id)
    rank = economy.RANKS.get(u["level"], "⚡ Spark")
    nxt = economy.next_threshold(u["points"])
    rank_line = f"▰ {u['points']}/{nxt[1]}💎 to {economy.RANKS[nxt[0]]}" if nxt else "🔮 Max rank!"
    place = await redis_lb.rank(redis, redis_lb.ALL, cb.from_user.id)
    week = await redis_lb.score(redis, redis_lb.WEEK, cb.from_user.id)
    activated, _ = await users.referral_stats(pool, cb.from_user.id)
    await cb.message.edit_text(
        f"👤 <b>Operator {u['username'] or u['first_name']}</b>\n\n"
        f"🏅 {rank} (Lv.{u['level']})\n💎 Points: <b>{u['points']}</b>\n"
        f"⚡ Energy: {cur}/{cap}\n🔥 Streak: {u['streak_count']}\n"
        f"🏆 All-time rank: #{place or '—'}\n📅 This week: {week}💎\n"
        f"👥 Referrals: {activated}\n\n{rank_line}",
        reply_markup=back_menu(),
    )
    await cb.answer()


# ---------------- Leaderboards ----------------
async def _render_zset(pool, redis, key, title, viewer_id):
    pairs = await redis_lb.top(redis, key, 10)
    names = await leaderboard.names_for(pool, [uid for uid, _ in pairs])
    medals = ["🥇", "🥈", "🥉"] + [f"{i}." for i in range(4, 11)]
    body = "\n".join(
        f"{medals[i]} {names.get(uid, uid)} — {sc}💎" for i, (uid, sc) in enumerate(pairs)
    ) or "No operators yet — be the first! ⚡"
    place = await redis_lb.rank(redis, key, viewer_id)
    return f"🏆 <b>{title}</b>\n\n{body}\n\n— Your rank: <b>#{place or '—'}</b>"


@router.callback_query(F.data == "lb:week")
async def cb_lb_week(cb: CallbackQuery, pool, redis):
    txt = await _render_zset(pool, redis, redis_lb.WEEK, "Weekly Top 10", cb.from_user.id)
    await cb.message.edit_text(txt, reply_markup=lb_tabs())
    await cb.answer()


@router.callback_query(F.data == "lb:all")
async def cb_lb_all(cb: CallbackQuery, pool, redis):
    txt = await _render_zset(pool, redis, redis_lb.ALL, "All-Time Top 10", cb.from_user.id)
    await cb.message.edit_text(txt, reply_markup=lb_tabs())
    await cb.answer()


@router.callback_query(F.data == "lb:refs")
async def cb_lb_refs(cb: CallbackQuery, pool):
    rows = await leaderboard.referral_top(pool, 10)
    body = "\n".join(
        f"{i+1}. {r['username'] or r['first_name']} — {r['refs']} recruits"
        for i, r in enumerate(rows)
    ) or "No recruits yet."
    await cb.message.edit_text(f"👥 <b>Top Recruiters</b>\n\n{body}", reply_markup=lb_tabs())
    await cb.answer()


# ---------------- shared post-award notifier ----------------
async def post_award(pool, redis, bot, user_id, award):
    """Send level-up + referral-activation notifications after a points award."""
    if award and award.get("leveled"):
        rank = economy.RANKS.get(award["level"], "⚡ Spark")
        try:
            await bot.send_message(user_id, LEVEL_UP.format(rank=rank, level=award["level"]))
        except Exception:
            pass
    referrer = await economy.maybe_activate_referral(pool, user_id, redis=redis)
    if referrer:
        try:
            await bot.send_message(referrer, REFERRAL_SUCCESS)
        except Exception:
            pass
