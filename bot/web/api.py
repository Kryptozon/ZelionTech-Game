"""Mini App REST API (aiohttp). All endpoints authenticate via Telegram initData."""
import json
from aiohttp import web

from ..config import settings
from .auth import validate_init_data
from ..services import economy, users, missions as msvc, proof as psvc
from ..services import leaderboard, redis_lb, quiz, kb, ai_quiz, analytics


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
    async def inner(request):
        if not settings.is_admin(request["user"]["id"]):
            return web.json_response({"error": "forbidden"}, status=403)
        return await handler(request)
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
    return web.json_response({
        "id": uid,
        "username": u["username"], "first_name": u["first_name"],
        "level": u["level"], "rank": economy.RANKS.get(u["level"], "⚡ Spark"),
        "points": u["points"], "energy": cur, "energy_cap": cap,
        "streak": u["streak_count"],
        "next_threshold": nxt[1] if nxt else None,
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
async def proof_submit(request):
    """Body: {mission_id, handle}. Image upload is handled in the bot DM flow."""
    pool, redis, bot, uid = _ctx(request)
    body = await request.json()
    mid = int(body["mission_id"])
    handle = str(body.get("handle", "")).strip()[:128]
    m = await msvc.get_mission(pool, mid)
    if not m:
        return web.json_response({"error": "not_found"}, status=404)
    pid = await psvc.create_submission(pool, uid, mid, m["platform"], handle, None)
    if pid is None:
        return web.json_response({"error": "duplicate"}, status=409)
    caption = (f"🔔 <b>Proof #{pid} (Mini App)</b>\nUser <code>{uid}</code>\n"
               f"Mission: <b>{m['title']}</b> (+{m['xp_reward']}💎)\nHandle: <code>{handle}</code>")
    from ..keyboards import proof_review_kb
    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, caption, reply_markup=proof_review_kb(pid))
        except Exception:
            pass
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


# ============================================================
# ADMIN ENDPOINTS
# ============================================================
@authed
@admin_only
async def admin_proofs(request):
    rows = await psvc.list_pending(request.app["pool"], 50)
    return web.json_response({"proofs": [
        {"id": r["id"], "user_id": r["user_id"], "username": r["username"],
         "title": r["title"], "handle": r["claimed_handle"], "reward": r["xp_reward"],
         "created_at": str(r["created_at"])} for r in rows
    ]})


@authed
@admin_only
async def admin_proof_approve(request):
    pool, redis, bot, _ = _ctx(request)
    pid = int(request.match_info["id"])
    res = await psvc.approve(pool, pid, request["user"]["id"], redis=redis)
    if isinstance(res, dict):
        try:
            await bot.send_message(res["user_id"], f"✅ Proof approved! +{res['xp']}💎 for {res['title']}.")
        except Exception:
            pass
    return web.json_response({"result": "ok" if isinstance(res, dict) else str(res)})


@authed
@admin_only
async def admin_proof_reject(request):
    pool, redis, bot, _ = _ctx(request)
    pid = int(request.match_info["id"])
    reason = (await request.json()).get("reason", "Not valid")
    res = await psvc.reject(pool, pid, request["user"]["id"], reason)
    if res:
        try:
            await bot.send_message(res["user_id"], f"❌ Proof rejected: {reason}")
        except Exception:
            pass
    return web.json_response({"result": "ok" if res else "already_reviewed"})


@authed
@admin_only
async def admin_kb_refresh(request):
    pool = request.app["pool"]
    summary = await kb.refresh(pool)
    gen = await ai_quiz.generate(pool, count=8, difficulty=1)
    return web.json_response({"kb": summary, "generated": gen})


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


def setup_api(app: web.Application):
    r = app.router
    r.add_get("/api/me", me)
    r.add_post("/api/claim-energy", claim_energy)
    r.add_get("/api/missions", get_missions)
    r.add_post("/api/missions/{id}/complete", complete_mission)
    r.add_post("/api/proof/submit", proof_submit)
    r.add_get("/api/leaderboard", get_leaderboard)
    r.add_get("/api/referrals", get_referrals)
    r.add_get("/api/profile", get_profile)
    # quiz
    r.add_get("/api/quiz/next", quiz_next)
    r.add_post("/api/quiz/answer", quiz_answer)
    r.add_get("/api/quiz/history", quiz_history)
    # admin
    r.add_get("/api/admin/proofs", admin_proofs)
    r.add_post("/api/admin/proofs/{id}/approve", admin_proof_approve)
    r.add_post("/api/admin/proofs/{id}/reject", admin_proof_reject)
    r.add_post("/api/admin/kb/refresh", admin_kb_refresh)
    r.add_get("/api/admin/questions", admin_questions)
    r.add_post("/api/admin/questions/{id}/approve", admin_question_approve)
    r.add_post("/api/admin/questions/{id}/reject", admin_question_reject)
