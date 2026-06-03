# ⚡ Zelion Reactor — Telegram Engagement Bot (Phases 1–3, production-ready)

A production-ready aiogram 3 bot where users charge energy, follow ZelionTech's
official channels (Telegram auto-verified, others via proof + 24h admin review),
pass quizzes, chat in the group for points, invite friends, and climb Redis leaderboards.
Points are for **status / ranks / whitelist eligibility only** — no gambling.

**Included across all phases:**
- **P1:** /start + referrals, menu, daily energy/streak, quizzes, proof missions + 24h admin review + auto-points, ban, anti-spam.
- **P2:** Telegram **auto-verify** (`getChatMember`) for @zeliontechofficial & @zelionglobal, group **message + reaction** rewards, weekly **leaderboard reset**, **surge hours**, referral anti-cheat.
- **P3:** **Redis ZSET** leaderboards, **shadow-ban**, **analytics** events (DAU/WAU), admin export, broadcast, scheduled jobs.

## Stack
Python 3.12 · aiogram 3 · PostgreSQL · Redis · Docker Compose · webhook or polling.

## Project layout
```
zelion-reactor/
├── docker-compose.yml      # db + redis + bot
├── Dockerfile
├── requirements.txt
├── .env.example            # copy to .env and fill in
├── db/
│   ├── init.sql            # P1 schema + seeded missions (idempotent)
│   └── migrations/
│       ├── 002_phase2.sql  # group_activity, events, telegram auto-verify flag
│       └── 003_phase3.sql  # shadow_banned column, analytics_events
└── bot/
    ├── main.py             # entrypoint (polling/webhook) + starts background jobs
    ├── config.py           # env settings, admin allowlist, P2/P3 tunables
    ├── db.py               # pool + runs init.sql then ordered migrations
    ├── keyboards.py texts.py states.py
    ├── middlewares.py      # user-load + ban gate + anti-spam + analytics
    ├── jobs/scheduler.py   # 24h SLA pings, weekly reset, surge scheduler
    ├── handlers/
    │   ├── core.py         # start, menu, claim, invite, profile, leaderboards
    │   ├── missions.py     # social missions, Telegram auto-verify, quizzes
    │   ├── proof.py        # proof FSM + admin approve/reject
    │   ├── group.py        # P2 group message + reaction rewards
    │   └── admin.py        # pending/stats/analytics/grant/ban/shadow/surge/weeklyreset/broadcast/export
    └── services/
        ├── economy.py      # energy, ledger, levels, daily, referral, surge, shadow
        ├── users.py missions.py proof.py leaderboard.py admin.py
        ├── redis_lb.py     # P3 Redis ZSET leaderboards + weekly snapshot
        ├── social_verify.py# P2 getChatMember auto-verify
        ├── group.py        # P2 group activity reward logic
        ├── events.py       # P2/P3 surge activation
        └── analytics.py    # P3 event logging + DAU/WAU summary
```

## Quick start (local, polling)
```bash
cp .env.example .env        # set BOT_TOKEN, ADMIN_IDS, BOT_USERNAME
docker compose up --build
```
The DB schema and missions seed automatically. Open Telegram, `/start` your bot.

See `DEPLOYMENT.md`, `ADMIN_MANUAL.md`, `TESTING.md`.
