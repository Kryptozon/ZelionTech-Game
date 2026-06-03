# 🎮 Zelion Reactor — Telegram Mini App + AI Quiz

This extends the existing bot with a full-screen Telegram Web App (React + Vite + Tailwind),
a REST API authenticated by Telegram `initData`, and an AI quiz grounded in **zeliontech.com**.

## What was added (file tree changes)
```
zelion-reactor/
├── render.yaml                      # NEW — Render blueprint (web + Postgres + Redis)
├── Dockerfile                       # CHANGED — multi-stage: build frontend, serve from Python
├── requirements.txt                 # CHANGED — + beautifulsoup4
├── db/migrations/004_quiz_kb.sql    # NEW — knowledge_pages, knowledge_chunks, quiz_questions, quiz_attempts
├── bot/
│   ├── config.py                    # CHANGED — MINIAPP_URL, WEBSITE_URL, AI_*, WEB_ALWAYS, PORT
│   ├── main.py                      # CHANGED — web server runs in BOTH polling & webhook modes
│   ├── keyboards.py                 # CHANGED — "🎮 Open Zelion Reactor" web_app button
│   ├── handlers/admin.py            # CHANGED — /kbrefresh /genquiz /quizpending /qok_ /qno_
│   ├── web/                         # NEW
│   │   ├── auth.py                  #   initData HMAC validation
│   │   ├── api.py                   #   all /api/* endpoints
│   │   └── server.py                #   aiohttp app: API + Mini App static + webhook
│   └── services/
│       ├── kb.py                    # NEW — crawl zeliontech.com -> chunks
│       ├── ai_quiz.py               # NEW — grounded question generator (AI or fallback)
│       └── quiz.py                  # NEW — serve/score questions, difficulty unlock, cooldown
└── frontend/                        # NEW — React + Vite + Tailwind Mini App
    ├── package.json vite.config.js tailwind.config.js postcss.config.js index.html
    └── src/
        ├── main.jsx App.jsx api.js telegram.js ui.jsx index.css
        └── screens/ Home Missions Quiz Leaderboard Profile Admin
```

## API endpoints (all require header `X-Init-Data: <Telegram.WebApp.initData>`)
Game: `GET /api/me` · `POST /api/claim-energy` · `GET /api/missions` ·
`POST /api/missions/:id/complete` · `POST /api/proof/submit` · `GET /api/leaderboard` ·
`GET /api/referrals` · `GET /api/profile`
Quiz: `GET /api/quiz/next` · `POST /api/quiz/answer` · `GET /api/quiz/history`
Admin: `GET /api/admin/proofs` · `POST /api/admin/proofs/:id/approve|reject` ·
`POST /api/admin/kb/refresh` · `GET /api/admin/questions` ·
`POST /api/admin/questions/:id/approve|reject`

## Authentication
`bot/web/auth.py` validates `initData` server-side:
`secret = HMAC_SHA256("WebAppData", BOT_TOKEN)`, then compares
`HMAC_SHA256(secret, data_check_string)` to the received `hash`, and enforces `auth_date`
freshness (`INITDATA_TTL`). Invalid/expired/banned → `401`. The verified Telegram user id is
mapped to the existing `users` table (`ensure_user`). Admin endpoints additionally require the
id to be in `ADMIN_IDS`.

## AI quiz — grounded & safe
1. `/kbrefresh` (bot) or **Admin → Knowledge → Refresh** crawls `zeliontech.com`
   (same-domain BFS, `KB_MAX_PAGES`), stores `knowledge_pages` + `knowledge_chunks`.
2. `ai_quiz.generate()` samples chunks and asks the LLM for a question **only from that excerpt**;
   if the excerpt is insufficient the model returns `{"skip":true}` and nothing is invented.
   With no `AI_API_KEY`, a deterministic, source-cited fallback generator is used instead.
3. Every question stores a `source_url` (safety rule) and starts as `status='pending'`.
   Admins approve in the Mini App or via `/qok_<id>` / `/qno_<id>`.
4. Difficulty unlocks by user level (1 basic → 5 expert); harder = more points; wrong answer = 30s
   cooldown; correct streak = bonus XP. Questions already answered by a user aren't repeated.

## Build the frontend
```bash
cd frontend
npm install
npm run build        # -> frontend/dist  (Docker does this automatically in stage 1)
```

## BotFather setup
1. **Menu button (opens Mini App):**
   `@BotFather` → `/mybots` → @ZelionTechGameBot → **Bot Settings → Menu Button → Configure menu button**
   → send the URL: `https://zeliontech-game.onrender.com/app` → label: `🎮 Open Game`.
   (CLI equivalent: `/setmenubutton`.)
2. **Inline button in /start** is already added in code (`keyboards.main_menu` → "🎮 Open Zelion Reactor",
   a `web_app` button). It renders automatically in private chat.
3. The Mini App **must be HTTPS** (Render gives you that).

## Deploy on Render (recommended — one service)
1. Push the repo to GitHub.
2. Render → **New → Blueprint** → select the repo (uses `render.yaml`): creates Postgres, Redis,
   and the Docker web service `zeliontech-game`.
3. In the service **Environment**, set the secrets marked `sync:false`:
   `BOT_TOKEN` (and optionally `AI_API_KEY`). Confirm `WEBHOOK_BASE` / `MINIAPP_URL` match your
   Render URL `https://zeliontech-game.onrender.com`.
4. Deploy. On boot the bot sets its webhook, runs migrations, and serves the Mini App at `/app`.
5. Make @ZelionTechGameBot **admin** in @zeliontechofficial, @zelionglobal and group `-1003423593105`,
   and `/setprivacy → Disable`.
6. Set the BotFather menu button URL (above).
7. Open the bot → tap **🎮 Open Zelion Reactor** → the full-screen game loads.

## Deploy with Docker Compose (self-host)
```bash
# Webhook mode needs a public HTTPS domain + nginx (deploy/nginx.conf). For a quick test,
# Render is easier. Locally you can still run polling + API:
docker compose up -d --build
# API + Mini App served on :8080 (USE_WEBHOOK=false). For Telegram to open the Mini App it must
# be reachable over HTTPS, so set MINIAPP_URL to your public https URL.
```

## Mini App testing checklist
- [ ] Tap 🎮 Open Zelion Reactor → app loads full-screen, header dark, gold Z logo.
- [ ] Invalid/!Telegram open → shows "Couldn't authenticate" (initData rejected). ✅ security.
- [ ] Home: claim energy works, points/energy/streak update.
- [ ] Missions: social proof submit → admin gets the proof in DM; learn quiz awards points.
- [ ] Quiz: question card shows difficulty badge + reward; correct → explanation + source link;
      wrong → cooldown; "Based on the ZelionTech website" links to a zeliontech.com URL.
- [ ] Leaderboard weekly/all-time render; Profile referral link copy/share works.
- [ ] Admin tab (only for ADMIN_IDS): approve/reject proofs, approve/reject questions, refresh KB.
- [ ] `/kbrefresh` then `/genquiz 5 1` → pending questions appear; approve → they show in /api/quiz/next.
