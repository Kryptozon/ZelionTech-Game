"""Validate Telegram WebApp initData server-side (HMAC-SHA256 with BOT_TOKEN)."""
import hmac
import hashlib
import json
import time
from urllib.parse import parse_qsl

from ..config import settings

ADMIN_TOKEN_TTL = 12 * 3600


def make_admin_token(user_id: int) -> str:
    """Signed admin session token (issued only after password check)."""
    exp = int(time.time()) + ADMIN_TOKEN_TTL
    msg = f"admin:{user_id}:{exp}"
    sig = hmac.new(settings.BOT_TOKEN.encode(), msg.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{user_id}.{exp}.{sig}"


def verify_admin_token(token: str, user_id: int) -> bool:
    try:
        uid, exp, sig = token.split(".")
        if int(uid) != int(user_id) or int(exp) < time.time():
            return False
        msg = f"admin:{uid}:{exp}"
        good = hmac.new(settings.BOT_TOKEN.encode(), msg.encode(), hashlib.sha256).hexdigest()[:32]
        return hmac.compare_digest(good, sig)
    except Exception:
        return False


def validate_init_data(init_data: str, max_age: int | None = None):
    """Return the parsed Telegram user dict if initData is authentic & fresh, else None.

    Algorithm (per Telegram docs):
      secret_key = HMAC_SHA256(key="WebAppData", msg=BOT_TOKEN)
      check_hash = HMAC_SHA256(key=secret_key, msg=data_check_string)
    """
    if not init_data:
        return None
    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret_key = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calc_hash, received_hash):
        return None

    # Freshness check (replay protection).
    ttl = settings.INITDATA_TTL if max_age is None else max_age
    auth_date = int(pairs.get("auth_date", "0") or 0)
    if ttl and auth_date and (time.time() - auth_date) > ttl:
        return None

    user_raw = pairs.get("user")
    if not user_raw:
        return None
    try:
        return json.loads(user_raw)
    except json.JSONDecodeError:
        return None
