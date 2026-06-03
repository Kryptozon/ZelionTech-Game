import os
from dotenv import load_dotenv

load_dotenv()


def _ints(raw: str):
    return [int(x) for x in raw.replace(" ", "").split(",") if x.strip()]


class Settings:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    BOT_USERNAME = os.getenv("BOT_USERNAME", "ZelionReactorBot")
    ADMIN_IDS = _ints(os.getenv("ADMIN_IDS", ""))

    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://zelion:zelion@db:5432/zelion")
    REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

    USE_WEBHOOK = os.getenv("USE_WEBHOOK", "false").lower() == "true"
    WEBHOOK_BASE = os.getenv("WEBHOOK_BASE", "")
    WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me")
    WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
    # Render (and most PaaS) inject the port to bind via $PORT.
    WEB_PORT = int(os.getenv("WEB_PORT", os.getenv("PORT", "8080")))

    # --- Launch mode / logging ---
    APP_ENV = os.getenv("APP_ENV", "production").lower()        # production | development
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL = (os.getenv("LOG_LEVEL", "").upper() or ("DEBUG" if DEBUG else "INFO"))

    # Official links (override seeded mission URLs at startup)
    LINKS = {
        "facebook": os.getenv("LINK_FACEBOOK", ""),
        "telegram_official": os.getenv("LINK_TELEGRAM_OFFICIAL", ""),
        "telegram_global": os.getenv("LINK_TELEGRAM_GLOBAL", ""),
        "x": os.getenv("LINK_X", ""),
        "linkedin": os.getenv("LINK_LINKEDIN", ""),
        "instagram": os.getenv("LINK_INSTAGRAM", ""),
        "whatsapp": os.getenv("LINK_WHATSAPP", ""),
        "tiktok": os.getenv("LINK_TIKTOK", ""),
        "discord": os.getenv("LINK_DISCORD", ""),
        "youtube": os.getenv("LINK_YOUTUBE", ""),
    }

    # --- Phase 2: Telegram auto-verify targets (bot must be admin/member) ---
    TG_VERIFY = {
        "telegram_official": os.getenv("TG_OFFICIAL_CHAT", "@zeliontechofficial"),
        "telegram_global": os.getenv("TG_GLOBAL_CHAT", "@zelionglobal"),
    }

    # --- Phase 2: Group activity rewards ---
    GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0") or 0)  # 0 = accept any group
    GROUP_MSG_XP = int(os.getenv("GROUP_MSG_XP", "2"))
    GROUP_MSG_DAILY_CAP = int(os.getenv("GROUP_MSG_DAILY_CAP", "20"))
    GROUP_MSG_MIN_LEN = int(os.getenv("GROUP_MSG_MIN_LEN", "3"))
    GROUP_REACT_XP = int(os.getenv("GROUP_REACT_XP", "5"))
    GROUP_REACT_DAILY_CAP = int(os.getenv("GROUP_REACT_DAILY_CAP", "5"))

    # --- Phase 2/3: Surge hours (UTC) + weekly bonus ---
    SURGE_HOURS = _ints(os.getenv("SURGE_HOURS", ""))      # e.g. "18,21"
    SURGE_MULT = int(os.getenv("SURGE_MULT", "2"))
    SURGE_DURATION_MIN = int(os.getenv("SURGE_DURATION_MIN", "60"))
    WEEKLY_BONUS = _ints(os.getenv("WEEKLY_BONUS", "500,300,200"))

    # --- Mini App / Web server ---
    MINIAPP_URL = os.getenv("MINIAPP_URL", "https://zeliontech-game.onrender.com/app")
    FRONTEND_DIST = os.getenv("FRONTEND_DIST", "frontend/dist")
    WEB_ALWAYS = os.getenv("WEB_ALWAYS", "true").lower() == "true"  # serve API even in polling mode
    INITDATA_TTL = int(os.getenv("INITDATA_TTL", "86400"))         # max age of WebApp initData (s)

    # --- ZelionTech knowledge base + AI quiz ---
    WEBSITE_URL = os.getenv("WEBSITE_URL", "https://zeliontech.com")
    KB_MAX_PAGES = int(os.getenv("KB_MAX_PAGES", "25"))
    AI_API_BASE = os.getenv("AI_API_BASE", "https://api.openai.com/v1")
    AI_API_KEY = os.getenv("AI_API_KEY", "")                        # empty => grounded fallback generator
    AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.ADMIN_IDS

    def validate_static(self):
        """Fail fast on misconfiguration before any network/IO."""
        errors = []
        if not self.BOT_TOKEN or ":" not in self.BOT_TOKEN:
            errors.append("BOT_TOKEN is missing or malformed.")
        if not self.ADMIN_IDS:
            errors.append("ADMIN_IDS is empty — no one can use admin commands.")
        if self.USE_WEBHOOK:
            if not self.WEBHOOK_BASE.startswith("https://"):
                errors.append("USE_WEBHOOK=true requires an https:// WEBHOOK_BASE.")
            if self.WEBHOOK_SECRET in ("", "change-me"):
                errors.append("WEBHOOK_SECRET must be set to a strong random value in webhook mode.")
        return errors


settings = Settings()
