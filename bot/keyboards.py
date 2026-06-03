from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from .config import settings


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    # Full-screen Mini App (web_app buttons only render in private chats).
    kb.button(text="🎮 Open Zelion Reactor", web_app=WebAppInfo(url=settings.MINIAPP_URL))
    kb.button(text="⚡ Claim Energy", callback_data="claim")
    kb.button(text="🎯 Missions", callback_data="missions")
    kb.button(text="📡 Social Missions", callback_data="social:list")
    kb.button(text="👥 Invite", callback_data="invite")
    kb.button(text="🏆 Leaderboard", callback_data="lb:week")
    kb.button(text="👤 Profile", callback_data="profile")
    kb.adjust(1, 2, 1, 2, 1)
    return kb.as_markup()


def back_menu(target="menu") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Back", callback_data=target)
    return kb.as_markup()


def social_list(missions, states: dict) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    icons = {"approved": "✅", "pending": "⏳", "rejected": "🔁", "none": "▫️"}
    for m in missions:
        st = states.get(m["id"], "none")
        kb.button(
            text=f"{icons.get(st,'▫️')} {m['title']} (+{m['xp_reward']})",
            callback_data=f"social:open:{m['id']}",
        )
    kb.button(text="⬅️ Back", callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def social_detail(mission, state: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if mission["url"]:
        kb.button(text="🔗 Open page", url=mission["url"])
    if state not in ("approved",):
        if mission["verification"] == "auto":
            kb.button(text="✅ Verify now (auto)", callback_data=f"social:verify:{mission['id']}")
        else:
            kb.button(text="✅ I followed — Submit Proof", callback_data=f"proof:start:{mission['id']}")
    kb.button(text="⬅️ Back", callback_data="social:list")
    kb.adjust(1)
    return kb.as_markup()


def learn_list(missions) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for m in missions:
        kb.button(text=f"🧠 {m['title']} (+{m['xp_reward']})", callback_data=f"quiz:open:{m['id']}")
    kb.button(text="⬅️ Back", callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def quiz_options(mission) -> InlineKeyboardMarkup:
    import json
    opts = mission["quiz_options"]
    if isinstance(opts, str):
        opts = json.loads(opts)
    kb = InlineKeyboardBuilder()
    for idx, o in enumerate(opts):
        kb.button(text=o["text"], callback_data=f"quiz:ans:{mission['id']}:{idx}")
    kb.button(text="⬅️ Back", callback_data="missions")
    kb.adjust(1)
    return kb.as_markup()


def invite_kb(link: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    share = f"https://t.me/share/url?url={link}&text=Join%20me%20on%20Zelion%20Reactor%20⚡"
    kb.button(text="📤 Share link", url=share)
    kb.button(text="⬅️ Back", callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def lb_tabs() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Weekly", callback_data="lb:week")
    kb.button(text="⭐ All-time", callback_data="lb:all")
    kb.button(text="👥 Referrals", callback_data="lb:refs")
    kb.button(text="⬅️ Back", callback_data="menu")
    kb.adjust(3, 1)
    return kb.as_markup()


def proof_review_kb(pid: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Approve", callback_data=f"padm:approve:{pid}")
    kb.button(text="❌ Reject", callback_data=f"padm:reject:{pid}")
    kb.button(text="🚫 Ban User", callback_data=f"padm:ban:{pid}")
    kb.adjust(2, 1)
    return kb.as_markup()
