"""Mini App REST API (aiohttp). All endpoints authenticate via Telegram initData."""
import json
from aiohttp import web

from ..config import settings
from .auth import validate_init_data, make_admin_token, verify_admin_token
from ..services import economy, users, missions as msvc, proof as psvc
from ..services import leaderboard, redis_lb, quiz, kb, kb_doc, ai_quiz, analytics
from ..services import tap as tapsvc, upgrades as upgsvc, tap_missions as tapmis
from ..services import community as csvc
from ..services import puzzles as pzsvc
from ..services import tasks as tasksvc


# ---------------- auth helpers ----------------
async def _auth(request):
    init = request.headers.get("X-Init-Data") or request.query.get("initData", "")
    tg_user = validate_init_data(init)
    if not tg_user:
        return None
    pool = request.app["pool"]
    if await users.is_banned(pool, tg_user["id"]):
        return None
    await users.ensure_user(pool, tg_user["id"], tg_user.get("username") or "",
                            tg_user.get("first_name") or "")
    return tg_user


def authed(handler):
    async def inner(request):
        user = await _auth(request)
        if not user:
            return web.json_response({"error": "unauthorized"}, status=401)
        request["user"] = user
        return await handler(request)
    return inner


def admin_only(handler):
    """Grants access if EITHER is true (server-side):
      1) Telegram ID is in ADMIN_IDS (the owner), OR
      2) a valid admin session token is present (issued by /api/admin/login
         after the password check — the fallback path)."""
    async def inner(request):
        uid = request["user"]["id"]
        token = request.headers.get("X-Admin-Token") or request.query.get("admin_token", "")
        if settings.is_admin(uid) or verify_admin_token(token, uid):
            return await handler(request)
        return web.json_response({"error": "admin_auth_required"}, status=403)
    return inner


def _ctx(request):
    return request.app["pool"], request.app["redis"], request.app["bot"], request["user"]["id"]


# ============================================================
# GAME ENDPOINTS
# ============================================================
@authed
async def me(request):
    pool = request.app["pool"]
    uid = request["user"]["id"]
    u = await users.get_user(pool, uid)
    cur, cap = await economy.energy_status(pool, uid)
    nxt = economy.next_threshold(u["points"])
    qrank = await quiz.quiz_rank(pool, uid)
    return web.json_response({
        "id": uid,
        "username": u["username"], "first_name": u["first_name"],
        "level": u["level"], "rank": economy.RANKS.get(u["level"], "⚡ Spark"),
        "points": u["points"], "energy": cur, "energy_cap": cap,
        "streak": u["streak_count"],
        "next_threshold": nxt[1] if nxt else None,
        "quiz_rank": qrank["rank"], "quiz_correct": qrank["correct"],
        "quiz_next_rank": qrank["next_rank"], "quiz_next_at": qrank["next_at"],
        "is_admin": settings.is_admin(uid),
    })


@authed
async def claim_energy(request):
    pool, redis, bot, uid = _ctx(request)
    res = await economy.claim_daily(pool, uid, redis=redis)
    if res["status"] == "ok":
        await economy.maybe_activate_referral(pool, uid, redis=redis)
    return web.json_response(res)


@authed
async def get_missions(request):
    pool = request.app["pool"]
    uid = request["user"]["id"]
    social = await msvc.list_social(pool)
    learn = await msvc.list_learn(pool)
    social_out = []
    for m in social:
        social_out.append({
            "id": m["id"], "title": m["title"], "description": m["description"],
            "reward": m["xp_reward"], "url": m["url"], "platform": m["platform"],
            "verification": m["verification"],
            "state": await msvc.social_mission_state(pool, uid, m["id"]),
        })
    learn_out = [{
        "id": m["id"], "title": m["title"], "question": m["quiz_question"],
        "options": [o["text"] for o in (json.loads(m["quiz_options"]) if isinstance(m["quiz_options"], str) else m["quiz_options"])],
        "reward": m["xp_reward"], "energy_cost": m["energy_cost"],
        "eligible": await msvc.quiz_eligible(pool, uid, m["id"]),
    } for m in learn]
    return web.json_response({"social": social_out, "learn": learn_out})


@authed
async def complete_mission(request):
    """Learn-quiz mission completion. Body: {answer_index}."""
    pool, redis, bot, uid = _ctx(request)
    mid = int(request.match_info["id"])
    body = await request.json()
    m = await msvc.get_mission(pool, mid)
    if not m:
        return web.json_response({"error": "not_found"}, status=404)
    if not await msvc.quiz_eligible(pool, uid, mid):
        return web.json_response({"error": "cooldown"}, status=429)
    opts = json.loads(m["quiz_options"]) if isinstance(m["quiz_options"], str) else m["quiz_options"]
    idx = int(body.get("answer_index", -1))
    if idx < 0 or idx >= len(opts) or not opts[idx]["correct"]:
        return web.json_response({"correct": False})
    if not await economy.spend_energy(pool, uid, m["energy_cost"]):
        return web.json_response({"error": "no_energy"}, status=400)
    await msvc.record_completion(pool, uid, mid, m["cooldown_sec"])
    award = await economy.award_points(pool, uid, m["xp_reward"], "quiz",
                                       f"{mid}:api", redis=redis, surge=True)
    return web.json_response({"correct": True, "awarded": m["xp_reward"],
                              "leveled": award["leveled"], "level": award["level"]})


@authed
async def mission_verify(request):
    """Auto-verify a Telegram join via getChatMember; award instantly if joined,
    else tell the client to fall back to proof submission."""
    from ..services.social_verify import verify_telegram_join
    pool, redis, bot, uid = _ctx(request)
    mid = int(request.match_info["id"])
    m = await msvc.get_mission(pool, mid)
    if not m:
        return web.json_response({"error": "not_found"}, status=404)
    if m["verification"] != "auto":
        return web.json_response({"verified": False, "needs_proof": True})
    if await msvc.social_mission_state(pool, uid, mid) == "approved":
        return web.json_response({"verified": True, "already": True})
    ok = await verify_telegram_join(bot, m["platform"], uid)
    if not ok:
        return web.json_response({"verified": False, "needs_proof": True,
                                 "message": "Join first, then tap Verify."})
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO proof_submissions(user_id, mission_id, platform, claimed_handle, status, reviewed_at) "
            "VALUES($1,$2,$3,'auto','approved', now())", uid, mid, m["platform"])
        await con.execute(
            "INSERT INTO social_accounts(user_id, platform, handle, verified) VALUES($1,$2,$3,true) "
            "ON CONFLICT (platform, handle) DO NOTHING", uid, m["platform"], f"tg:{uid}")
    await economy.award_points(pool, uid, m["xp_reward"], "proof",
                               f"tgjoin:{mid}:{uid}", redis=redis)
    return web.json_response({"verified": True, "reward": m["xp_reward"]})


@authed
async def proof_submit(request):
    """Body: {mission_id, handle, image_base64?, mime?}. Screenshot saved in DB."""
    import base64
    pool, redis, bot, uid = _ctx(request)
    body = await request.json()
    mid = int(body["mission_id"])
    handle = str(body.get("handle", "")).strip()[:128]
    m = await msvc.get_mission(pool, mid)
    if not m:
        return web.json_response({"error": "not_found"}, status=404)

    image = None
    b64 = body.get("image_base64")
    if b64:
        if "," in b64:                      # strip data: URL prefix if present
            b64 = b64.split(",", 1)[1]
        try:
            image = base64.b64decode(b64)
        except Exception:
            return web.json_response({"error": "bad_image"}, status=400)

    pid = await psvc.create_submission(
        pool, uid, mid, m["platform"], handle, screenshot=image,
        mime=body.get("mime", "image/jpeg"),
        username=request["user"].get("username") or request["user"].get("first_name"),
    )
    if pid is None:
        return web.json_response({"error": "duplicate"}, status=409)
    if pid == "too_large":
        return web.json_response({"error": "too_large"}, status=413)
    return web.json_response({"status": "pending", "id": pid, "reward": m["xp_reward"]})


@authed
async def get_leaderboard(request):
    pool, redis = request.app["pool"], request.app["redis"]
    uid = request["user"]["id"]

    async def board(key):
        pairs = await redis_lb.top(redis, key, 10)
        names = await leaderboard.names_for(pool, [u for u, _ in pairs])
        return [{"name": names.get(u, str(u)), "score": s} for u, s in pairs]

    return web.json_response({
        "weekly": await board(redis_lb.WEEK),
        "alltime": await board(redis_lb.ALL),
        "my_rank": await redis_lb.rank(redis, redis_lb.ALL, uid),
        "my_week": await redis_lb.score(redis, redis_lb.WEEK, uid),
    })


@authed
async def get_referrals(request):
    pool = request.app["pool"]
    uid = request["user"]["id"]
    activated, pending = await users.referral_stats(pool, uid)
    link = f"https://t.me/{settings.BOT_USERNAME}?start=ref_{uid}"
    return web.json_response({"link": link, "activated": activated, "pending": pending})


@authed
async def get_profile(request):
    pool, redis = request.app["pool"], request.app["redis"]
    uid = request["user"]["id"]
    u = await users.get_user(pool, uid)
    cur, cap = await economy.energy_status(pool, uid)
    activated, _ = await users.referral_stats(pool, uid)
    return web.json_response({
        "username": u["username"], "first_name": u["first_name"],
        "level": u["level"], "rank": economy.RANKS.get(u["level"], "⚡ Spark"),
        "points": u["points"], "energy": cur, "energy_cap": cap, "streak": u["streak_count"],
        "referrals": activated,
        "all_time_rank": await redis_lb.rank(redis, redis_lb.ALL, uid),
        "next_threshold": (economy.next_threshold(u["points"]) or [None, None])[1],
    })


# ============================================================
# TAP-TO-EARN ENDPOINTS
# ============================================================
@authed
async def tap_state(request):
    return web.json_response(await tapsvc.get_state(
        request.app["pool"], request.app["redis"], request["user"]["id"]))


@authed
async def tap_do(request):
    pool, redis = request.app["pool"], request.app["redis"]
    body = await request.json()
    taps = int(body.get("taps", 1))
    nonce = str(body.get("nonce", ""))[:64] or "n"
    return web.json_response(await tapsvc.tap(pool, redis, request["user"]["id"], taps, nonce))


@authed
async def upgrades_list(request):
    return web.json_response(await upgsvc.list_for_user(request.app["pool"], request["user"]["id"]))


@authed
async def upgrade_buy(request):
    pool, redis = request.app["pool"], request.app["redis"]
    code = request.match_info["id"]
    res = await upgsvc.buy(pool, redis, request["user"]["id"], code)
    return web.json_response(res, status=(400 if res.get("error") else 200))


@authed
async def passive_get(request):
    st = await tapsvc.get_state(request.app["pool"], request.app["redis"], request["user"]["id"])
    return web.json_response({"pending": st["passive_pending"], "rate": st["passive_rate"],
                             "cap_hours": st["passive_cap_hours"]})


@authed
async def passive_claim(request):
    pool, redis = request.app["pool"], request.app["redis"]
    return web.json_response(await tapsvc.claim_passive(pool, redis, request["user"]["id"]))


@authed
async def tap_missions_list(request):
    return web.json_response({"missions": await tapmis.list_for_user(
        request.app["pool"], request["user"]["id"])})


@authed
async def tap_mission_claim(request):
    pool, redis = request.app["pool"], request.app["redis"]
    mid = int(request.match_info["id"])
    res = await tapmis.claim(pool, redis, request["user"]["id"], mid)
    return web.json_response(res, status=(400 if res.get("error") else 200))


# ============================================================
# QUIZ ENDPOINTS
# ============================================================
@authed
async def quiz_next(request):
    pool, redis = request.app["pool"], request.app["redis"]
    return web.json_response(await quiz.next_question(pool, redis, request["user"]["id"]))


@authed
async def quiz_answer(request):
    pool, redis = request.app["pool"], request.app["redis"]
    body = await request.json()
    res = await quiz.submit_answer(pool, redis, request["user"]["id"],
                                   int(body["question_id"]), int(body["choice"]))
    status = 400 if res.get("error") else 200
    return web.json_response(res, status=status)


@authed
async def quiz_history(request):
    pool = request.app["pool"]
    return web.json_response({"history": await quiz.history(pool, request["user"]["id"])})


@authed
async def quiz_daily(request):
    pool, redis = request.app["pool"], request.app["redis"]
    return web.json_response(await quiz.daily_status(pool, redis, request["user"]["id"]))


@authed
async def quiz_rank(request):
    pool = request.app["pool"]
    return web.json_response(await quiz.quiz_rank(pool, request["user"]["id"]))


@authed
async def quiz_status(request):
    pool, redis = request.app["pool"], request.app["redis"]
    return web.json_response(await quiz.status(pool, redis, request["user"]["id"]))


# ============================================================
# ADMIN ENDPOINTS
# ============================================================
@authed
async def admin_me(request):
    """Authed (not admin-gated): tells the client whether THIS user is the owner
    and whether they currently have dashboard access (owner OR valid password token)."""
    uid = request["user"]["id"]
    token = request.headers.get("X-Admin-Token") or request.query.get("admin_token", "")
    is_admin = settings.is_admin(uid)
    return web.json_response({"is_admin": is_admin, "id": uid,
                              # Owner gets in with no password; others via the token.
                              "authed": is_admin or verify_admin_token(token, uid)})


@authed
async def admin_login(request):
    """Password fallback: a correct admin password grants a signed session token,
    even if the Telegram ID isn't recognised (owner can always get in)."""
    uid = request["user"]["id"]
    body = await request.json() if request.can_read_body else {}
    if not settings.check_admin_password(body.get("password", "")):
        return web.json_response({"error": "wrong_password"}, status=403)
    return web.json_response({"token": make_admin_token(uid), "ttl": 12 * 3600})


@authed
async def admin_debug(request):
    """TEMP diagnostics (no secrets). Enabled only when ADMIN_DEBUG=true."""
    if not settings.ADMIN_DEBUG:
        return web.json_response({"error": "not_found"}, status=404)
    uid = request["user"]["id"]
    token = request.headers.get("X-Admin-Token") or request.query.get("admin_token", "")
    is_admin = settings.is_admin(uid)
    token_ok = verify_admin_token(token, uid)
    return web.json_response({
        "telegram_id": uid,
        "telegram_id_type": type(uid).__name__,
        "admin_ids_loaded": settings.ADMIN_IDS,
        "is_admin": is_admin,
        "token_valid": token_ok,
        "auth_source": "telegram_id" if is_admin else ("password_token" if token_ok else "denied"),
        "denied_reason": None if (is_admin or token_ok)
                         else ("ADMIN_IDS is empty — env var not loaded" if not settings.ADMIN_IDS
                               else "telegram_id not in ADMIN_IDS and no valid password token"),
    })


@authed
@admin_only
async def admin_users(request):
    """Search users by Telegram ID or username (admin only)."""
    q = (request.query.get("q") or "").strip()
    pool = request.app["pool"]
    async with pool.acquire() as con:
        if q.isdigit():
            rows = await con.fetch(
                "SELECT id, username, first_name, points, level, status FROM users WHERE id=$1", int(q))
        elif q:
            rows = await con.fetch(
                "SELECT id, username, first_name, points, level, status FROM users "
                "WHERE username ILIKE $1 OR first_name ILIKE $1 ORDER BY points DESC LIMIT 25", f"%{q}%")
        else:
            rows = await con.fetch(
                "SELECT id, username, first_name, points, level, status FROM users "
                "ORDER BY points DESC LIMIT 25")
    return web.json_response({"users": [dict(r) for r in rows]})


@authed
@admin_only
async def admin_proofs(request):
    status = request.query.get("status", "pending")
    rows = await psvc.list_by_status(request.app["pool"], status, 100)
    init = request.headers.get("X-Init-Data") or request.query.get("initData", "")
    import urllib.parse
    q = urllib.parse.quote(init)
    return web.json_response({"proofs": [
        {"id": r["id"], "user_id": r["user_id"], "username": r["username"],
         "first_name": r["first_name"], "platform": r["platform"], "mission": r["title"],
         "handle": r["claimed_handle"], "link": r["submitted_link"], "reward": r["reward"],
         "status": r["status"], "reject_reason": r["reject_reason"],
         "created_at": str(r["created_at"]),
         "reviewed_at": str(r["reviewed_at"]) if r["reviewed_at"] else None,
         "has_image": r["has_image"],
         "image_url": (f"/api/admin/proofs/{r['id']}/image?initData={q}" if r["has_image"] else None)}
        for r in rows
    ]})


@authed
@admin_only
async def admin_proof_image(request):
    img, mime = await psvc.get_image(request.app["pool"], int(request.match_info["id"]))
    if not img:
        return web.json_response({"error": "no_image"}, status=404)
    return web.Response(body=img, content_type=mime, headers={"Cache-Control": "private, max-age=600"})


@authed
@admin_only
async def admin_proof_approve(request):
    pool, redis, bot, _ = _ctx(request)
    pid = int(request.match_info["id"])
    res = await psvc.approve(pool, pid, request["user"]["id"], redis=redis)
    if isinstance(res, dict):
        try:
            await bot.send_message(res["user_id"],
                                   f"✅ <b>Proof approved!</b> +{res['xp']} ZLN-XP for {res['title']}.")
        except Exception:
            pass
        return web.json_response({"result": "approved", "awarded": res["xp"]})
    return web.json_response({"result": str(res) if res else "already_reviewed"})


@authed
@admin_only
async def admin_proof_reject(request):
    pool, redis, bot, _ = _ctx(request)
    pid = int(request.match_info["id"])
    body = await request.json() if request.can_read_body else {}
    reason = (body.get("reason") or "Not valid").strip()[:280]
    res = await psvc.reject(pool, pid, request["user"]["id"], reason)
    if res:
        try:
            await bot.send_message(res["user_id"],
                                   f"❌ <b>Proof rejected.</b>\nReason: <i>{reason}</i>\nYou can resubmit.")
        except Exception:
            pass
    return web.json_response({"result": "rejected" if res else "already_reviewed"})


@authed
@admin_only
async def admin_proof_ban(request):
    pool, redis, bot, _ = _ctx(request)
    pid = int(request.match_info["id"])
    async with pool.acquire() as con:
        target = await con.fetchval("SELECT user_id FROM proof_submissions WHERE id=$1", pid)
    if not target:
        return web.json_response({"error": "not_found"}, status=404)
    await psvc.ban_and_reject_all(pool, target, request["user"]["id"])
    try:
        await bot.send_message(target, "🚫 Your account has been banned for fraudulent proof submissions.")
    except Exception:
        pass
    return web.json_response({"result": "banned", "user_id": target})


@authed
@admin_only
async def admin_banned(request):
    return web.json_response({"banned": await psvc.banned_users(request.app["pool"], 100)})


@authed
@admin_only
async def admin_proof_stats(request):
    return web.json_response(await psvc.dashboard_stats(request.app["pool"]))


@authed
@admin_only
async def admin_kb_refresh(request):
    """Rebuild the KB from BOTH the seed document(s) and the live website,
    then pre-generate a mixed batch of grounded questions (pending review)."""
    pool = request.app["pool"]
    docs = await kb_doc.import_all(pool)
    site = await kb.refresh(pool)
    gen_total, plan = 0, [
        (1, "mcq"), (1, "true_false"), (2, "mcq"), (2, "scenario"),
        (3, "architecture"), (3, "tokenomics"), (4, "scenario"),
    ]
    for diff, qtype in plan:
        r = await ai_quiz.generate(pool, count=2, difficulty=diff, qtype=qtype)
        gen_total += r.get("inserted", 0)
    return web.json_response({"documents": docs, "website": site,
                              "generated": gen_total, "status": "pending review"})


@authed
@admin_only
async def admin_questions(request):
    status = request.query.get("status", "pending")
    rows = await quiz.admin_list(request.app["pool"], status, 50)
    return web.json_response({"questions": [
        {"id": r["id"], "question": r["question"],
         "options": json.loads(r["options"]) if isinstance(r["options"], str) else r["options"],
         "correct_index": r["correct_index"], "explanation": r["explanation"],
         "difficulty": r["difficulty"], "source_url": r["source_url"],
         "created_by": r["created_by"]} for r in rows
    ]})


@authed
@admin_only
async def admin_question_approve(request):
    await quiz.set_status(request.app["pool"], int(request.match_info["id"]), "approved",
                          request["user"]["id"])
    return web.json_response({"result": "approved"})


@authed
@admin_only
async def admin_question_reject(request):
    await quiz.set_status(request.app["pool"], int(request.match_info["id"]), "rejected",
                          request["user"]["id"])
    return web.json_response({"result": "rejected"})


# ============================================================
# COMMUNITY ENDPOINTS  (hardened — never 500; return safe empty defaults)
# ============================================================
async def _safe(coro, default, label):
    try:
        return await coro
    except Exception as e:
        log.warning("community %s failed: %s", label, e)
        return default


def _group_link():
    return settings.GROUP_LINK      # public link, always openable (https://t.me/zelionglobal)


def _channel_link():
    return settings.CHANNEL_LINK    # https://t.me/zeliontechofficial


@authed
async def community_overview(request):
    pool, redis = request.app["pool"], request.app["redis"]
    uid = request["user"]["id"]
    from ..services import events as esvc
    surge = await _safe(esvc.surge_active(redis), 1, "surge")
    return web.json_response({
        "discussion": await _safe(csvc.todays_discussion(pool), None, "discussion"),
        "missions": await _safe(csvc.list_missions(pool, uid), [], "missions"),
        "score": await _safe(csvc.contribution_score(pool, uid),
                             {"today": 0, "messages": 0, "replies": 0, "reactions": 0,
                              "discussion": 0, "days_week": 0}, "score"),
        "top_today": await _safe(csvc.group_leaderboard(pool, "today", 10), [], "lb_today"),
        "top_week": await _safe(csvc.group_leaderboard(pool, "week", 10), [], "lb_week"),
        "top_month": await _safe(csvc.group_leaderboard(pool, "month", 10), [], "lb_month"),
        "surge_multiplier": surge,
        "group_link": _group_link(),
        "channel_link": _channel_link(),
        "msg_reward": settings.GROUP_MSG_XP,
        "msg_min_len": settings.GROUP_MSG_MIN_LEN,
    })


@authed
async def community_claim(request):
    pool, redis = request.app["pool"], request.app["redis"]
    mid = int(request.match_info["id"])
    res = await csvc.claim_mission(pool, redis, request["user"]["id"], mid)
    return web.json_response(res, status=(400 if res.get("error") else 200))


# ---- Granular /api/group/* routes (each independent & safe) ----
@authed
async def group_activity_ep(request):
    pool = request.app["pool"]
    uid = request["user"]["id"]
    score = await _safe(csvc.contribution_score(pool, uid),
                        {"today": 0, "messages": 0, "replies": 0, "reactions": 0,
                         "discussion": 0, "days_week": 0}, "activity")
    return web.json_response({"score": score, "group_link": _group_link(),
                              "channel_link": _channel_link()})


@authed
async def group_missions_ep(request):
    pool, uid = request.app["pool"], request["user"]["id"]
    return web.json_response({"missions": await _safe(csvc.list_missions(pool, uid), [], "missions")})


@authed
async def group_leaderboard_ep(request):
    pool = request.app["pool"]
    period = request.query.get("period", "today")
    return web.json_response({"period": period,
                              "leaderboard": await _safe(csvc.group_leaderboard(pool, period, 10), [], "lb")})


@authed
async def group_discussion_ep(request):
    pool = request.app["pool"]
    return web.json_response({"discussion": await _safe(csvc.todays_discussion(pool), None, "discussion"),
                              "group_link": _group_link(), "channel_link": _channel_link()})


@authed
async def group_health_ep(request):
    pool, bot = request.app["pool"], request.app["bot"]
    can = False
    try:
        await bot.get_chat(settings.GROUP_CHAT_ID)
        can = True
    except Exception as e:
        log.warning("group health get_chat failed: %s", e)
    activity = await _safe(_count(pool, "SELECT count(*) FROM group_activity"), 0, "activity_count")
    disc = await _safe(csvc.todays_discussion(pool), None, "discussion")
    return web.json_response({
        "status": "ok",
        "bot_can_access_group": can,
        "group_chat_id": settings.GROUP_CHAT_ID,
        "activity_count": activity,
        "discussion_available": disc is not None,
    })


async def _count(pool, sql):
    async with pool.acquire() as con:
        return await con.fetchval(sql)


# ============================================================
# TASK / ACHIEVEMENT ENDPOINTS
# ============================================================
@authed
async def tasks_list(request):
    return web.json_response(await tasksvc.list_chains(request.app["pool"], request["user"]["id"]))


@authed
async def tasks_claim(request):
    pool, redis = request.app["pool"], request.app["redis"]
    tid = int(request.match_info["id"])
    res = await tasksvc.claim(pool, redis, request["user"]["id"], tid)
    return web.json_response(res, status=(400 if res.get("error") else 200))


# ============================================================
# PUZZLE / INTELLIGENCE ENDPOINTS
# ============================================================
@authed
async def puzzles_daily(request):
    pool, redis = request.app["pool"], request.app["redis"]
    uid = request["user"]["id"]
    return web.json_response({
        "daily": await pzsvc.daily(pool, redis, uid),
        "weekly": await pzsvc.weekly(pool, redis, uid),
    })


@authed
async def puzzles_answer(request):
    pool, redis = request.app["pool"], request.app["redis"]
    body = await request.json()
    res = await pzsvc.answer(pool, redis, request["user"]["id"],
                             int(body["puzzle_id"]), str(body.get("answer", "")))
    return web.json_response(res, status=(400 if res.get("error") in ("not_found",) else 200))


@authed
async def puzzles_status(request):
    pool, redis = request.app["pool"], request.app["redis"]
    return web.json_response(await pzsvc.status(pool, redis, request["user"]["id"]))


@authed
async def puzzles_history(request):
    return web.json_response({"history": await pzsvc.history(request.app["pool"], request["user"]["id"])})


@authed
async def puzzles_leaderboard(request):
    period = request.query.get("period", "week")
    return web.json_response({"period": period,
                              "leaderboard": await pzsvc.leaderboard(request.app["pool"], period, 10)})


@authed
@admin_only
async def admin_puzzles(request):
    rows = await pzsvc.admin_list(request.app["pool"], request.query.get("difficulty"))
    return web.json_response({"puzzles": [
        {"id": r["id"], "title": r["title"], "difficulty": r["difficulty"], "category": r["category"],
         "question": r["question"], "answer": r["answer"],
         "accepted_variations": r.get("accepted_variations"), "explanation": r["explanation"],
         "source_topic": r.get("source_topic"), "reward": r["reward"],
         "status": r.get("status", "active"), "active": r["active"],
         "walkthrough": r.get("walkthrough"),
         "hint1": r["hint1"], "hint2": r["hint2"], "hint3": r["hint3"],
         "released_hints": r.get("released_hints", 0),
         "youtube_posted": r.get("youtube_posted", False),
         "telegram_posted": r.get("telegram_posted", False)} for r in rows]})


@authed
@admin_only
async def admin_puzzle_overview(request):
    return web.json_response(await pzsvc.admin_overview(request.app["pool"]))


@authed
@admin_only
async def admin_puzzle_release(request):
    await pzsvc.release_puzzle(request.app["pool"], int(request.match_info["id"]))
    return web.json_response({"result": "released"})


@authed
@admin_only
async def admin_puzzle_reopen(request):
    await pzsvc.release_puzzle(request.app["pool"], int(request.match_info["id"]))
    return web.json_response({"result": "reopened"})


@authed
@admin_only
async def admin_puzzle_activate(request):
    await pzsvc.set_status(request.app["pool"], int(request.match_info["id"]), "active")
    return web.json_response({"result": "activated"})


@authed
@admin_only
async def admin_puzzle_deactivate(request):
    await pzsvc.set_status(request.app["pool"], int(request.match_info["id"]), "closed")
    return web.json_response({"result": "closed"})


@authed
@admin_only
async def admin_puzzle_skip(request):
    await pzsvc.set_status(request.app["pool"], int(request.match_info["id"]), "skipped")
    return web.json_response({"result": "skipped"})


@authed
@admin_only
async def admin_puzzle_release_hint(request):
    body = await request.json() if request.can_read_body else {}
    await pzsvc.release_hint(request.app["pool"], int(request.match_info["id"]), int(body.get("n", 1)))
    return web.json_response({"result": "released"})


@authed
@admin_only
async def admin_puzzle_mark_posted(request):
    plat = request.match_info["platform"]
    await pzsvc.mark_posted(request.app["pool"], int(request.match_info["id"]), plat)
    return web.json_response({"result": "marked", "platform": plat})


@authed
@admin_only
async def admin_puzzle_hints(request):
    return web.json_response(await pzsvc.get_hints(request.app["pool"], int(request.match_info["id"])))


@authed
@admin_only
async def admin_puzzle_youtube(request):
    return web.json_response(await pzsvc.get_script(request.app["pool"], int(request.match_info["id"])))


@authed
@admin_only
async def admin_puzzle_telegram(request):
    s = await pzsvc.get_script(request.app["pool"], int(request.match_info["id"]))
    return web.json_response({"telegram_post": s.get("telegram_post", "")})


def setup_api(app: web.Application):
    r = app.router
    r.add_get("/api/me", me)
    r.add_post("/api/claim-energy", claim_energy)
    r.add_get("/api/missions", get_missions)
    r.add_post("/api/missions/{id}/complete", complete_mission)
    r.add_post("/api/missions/{id}/verify", mission_verify)
    r.add_post("/api/proof/submit", proof_submit)
    r.add_get("/api/leaderboard", get_leaderboard)
    r.add_get("/api/referrals", get_referrals)
    r.add_get("/api/profile", get_profile)
    # tap-to-earn
    r.add_get("/api/tap/state", tap_state)
    r.add_post("/api/tap", tap_do)
    r.add_get("/api/upgrades", upgrades_list)
    r.add_post("/api/upgrades/{id}/buy", upgrade_buy)
    r.add_get("/api/passive", passive_get)
    r.add_post("/api/passive/claim", passive_claim)
    r.add_get("/api/tap/missions", tap_missions_list)
    r.add_post("/api/tap/missions/{id}/claim", tap_mission_claim)
    # quiz
    r.add_get("/api/quiz/next", quiz_next)
    r.add_post("/api/quiz/answer", quiz_answer)
    r.add_get("/api/quiz/history", quiz_history)
    r.add_get("/api/quiz/daily", quiz_daily)
    r.add_get("/api/quiz/status", quiz_status)
    r.add_get("/api/quiz/rank", quiz_rank)
    # tasks / achievements
    r.add_get("/api/tasks", tasks_list)
    r.add_post("/api/tasks/{id}/claim", tasks_claim)
    # puzzles / intelligence
    r.add_get("/api/puzzles/daily", puzzles_daily)
    r.add_post("/api/puzzles/answer", puzzles_answer)
    r.add_get("/api/puzzles/status", puzzles_status)
    r.add_get("/api/puzzles/history", puzzles_history)
    r.add_get("/api/puzzles/leaderboard", puzzles_leaderboard)
    r.add_get("/api/admin/puzzles", admin_puzzles)
    r.add_post("/api/admin/puzzles/{id}/activate", admin_puzzle_activate)
    r.add_post("/api/admin/puzzles/{id}/deactivate", admin_puzzle_deactivate)
    r.add_get("/api/admin/puzzles/overview", admin_puzzle_overview)
    r.add_post("/api/admin/puzzles/{id}/release", admin_puzzle_release)
    r.add_post("/api/admin/puzzles/{id}/reopen", admin_puzzle_reopen)
    r.add_post("/api/admin/puzzles/{id}/skip", admin_puzzle_skip)
    r.add_post("/api/admin/puzzles/{id}/release-hint", admin_puzzle_release_hint)
    r.add_post("/api/admin/puzzles/{id}/mark-posted/{platform}", admin_puzzle_mark_posted)
    r.add_get("/api/admin/puzzles/{id}/hints", admin_puzzle_hints)
    r.add_get("/api/admin/puzzles/{id}/youtube-script", admin_puzzle_youtube)
    r.add_get("/api/admin/puzzles/{id}/telegram-post", admin_puzzle_telegram)
    # community
    r.add_get("/api/community", community_overview)
    r.add_post("/api/community/missions/{id}/claim", community_claim)
    # granular group routes (resilient)
    r.add_get("/api/group/activity", group_activity_ep)
    r.add_get("/api/group/missions", group_missions_ep)
    r.add_get("/api/group/leaderboard", group_leaderboard_ep)
    r.add_get("/api/group/daily-discussion", group_discussion_ep)
    r.add_get("/api/group/health", group_health_ep)
    # admin — identity + login + user search
    r.add_get("/api/admin/me", admin_me)
    r.add_get("/api/admin/debug", admin_debug)
    r.add_post("/api/admin/login", admin_login)
    r.add_get("/api/admin/users", admin_users)
    # admin — proof moderation dashboard
    r.add_get("/api/admin/proofs", admin_proofs)
    r.add_get("/api/admin/proofs/{id}/image", admin_proof_image)
    r.add_post("/api/admin/proofs/{id}/approve", admin_proof_approve)
    r.add_post("/api/admin/proofs/{id}/reject", admin_proof_reject)
    r.add_post("/api/admin/proofs/{id}/ban", admin_proof_ban)
    r.add_get("/api/admin/banned", admin_banned)
    r.add_get("/api/admin/proof-stats", admin_proof_stats)
    # admin — quiz KB
    r.add_post("/api/admin/kb/refresh", admin_kb_refresh)
    r.add_get("/api/admin/questions", admin_questions)
    r.add_post("/api/admin/questions/{id}/approve", admin_question_approve)
    r.add_post("/api/admin/questions/{id}/reject", admin_question_reject)
