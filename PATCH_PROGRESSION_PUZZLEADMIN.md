# 🩹 Patch — Expanded Task Chains · Puzzle Admin Control Center · Weekly Cap

Extends the existing project. No rebuild; nothing removed. Most of this spec was already live
(quiz shuffle/penalties, 300-question daily quiz, ~200 puzzles, social rewards, anti-spam, daily
caps, instant Lab effects). This patch adds the **deltas**.

## Migrations
- `015_puzzle_admin.sql` — `puzzles += accepted_variations, source_topic, status, youtube_posted,
  telegram_posted, released_hints` (+ backfill of existing rows).

## Backend modified
- `bot/services/tasks.py` — **expanded to 12 chains / 68 tiers**: Validate Energy (Bronze→Reactor
  Elite, 1k→10M), Power Surge (→x1000), separate Reactor Core / **Battery / Solar / Quantum** lab
  chains, Community (messages) + **Replies** + **Discussion** chains, Quiz (attempts + correct +
  **login streak**), Puzzle (1→100 + **weekly/elite mystery**), Social (+**Instagram** + **complete
  all socials**). New server-side metrics (replies, discussion, per-upgrade levels, quiz attempts,
  login_streak, legendary-puzzle solves, instagram, social_count). `ensure_seed` now **upserts** so
  the rebalanced goals/rewards apply on deploy.
- `bot/services/puzzles.py` — answer matching accepts **accepted_variations**; player payload can
  show **admin-released hints** (`released_hints`) and a **closed** flag (never answers/scripts);
  new admin fns `set_status` (active/closed/skipped → "closed forever", scarcity), `release_hint`,
  `mark_posted`.
- `bot/services/puzzle_seed.py` — seeds `accepted_variations` + `source_topic` + `status='active'`.
- `bot/services/tap.py` — **weekly XP cap** (`WEEKLY_TAP_CAP`, default 50,000/ISO-week, Redis) on
  tap rewards; `get_state`/`tap` expose weekly_used/remaining + a cap message.
- `bot/config.py` — community **reply +2**, **discussion +5** (per spec).
- `bot/web/api.py` — admin puzzle list now returns full fields (answer, accepted_variations,
  explanation, source_topic, status, hints, posted flags, released_hints); new endpoints:
  `POST /api/admin/puzzles/{id}/skip`, `/release-hint`, `/mark-posted/{platform}`.

## Frontend modified
- `screens/Admin.jsx` — **Puzzle Control Center**: per puzzle shows ID, title, difficulty, reward,
  status, question, answer, accepted variations, explanation, source topic, hint-release state +
  **Release Hint 1/2/3**, **Copy Answer / Hint1-3 / Video Script / Telegram Post**, **Release /
  Close / Skip**, **Mark YouTube/Telegram Posted**.
- `screens/Intelligence.jsx` — shows **admin-released hints**, YouTube/Telegram "posted" indicators,
  and **⚠ Puzzle Closed Forever** when a puzzle is closed/skipped.
- `screens/Community.jsx` — **full "How to earn ZLN-XP" info panel** (message/reply/discussion/quiz/
  puzzle/social/missions) as an always-visible card **and** the first-open popup.
- `api.js` — admin puzzle control methods.
- (Task UI `screens/Tasks.jsx` already exists — auto-unlock + "⚡ New Task Unlocked" popup +
  completed history + total %.)

## Admin security (server-side enforced)
All `/api/admin/*` routes require valid Telegram **initData** + `ADMIN_IDS=1087968824` (`@admin_only`).
Players' puzzle payloads **never** include answer, accepted variations, unreleased hints, or scripts —
only admin-released hints. Closed/skipped puzzles are removed from rotation server-side.

## Validation (run here — all pass)
12 chains / 68 tiers · every task metric resolvable · puzzle admin fns present · `WEEKLY_TAP_CAP=50000`
· `/api/tasks` + new admin puzzle routes registered · backend `py_compile` ✓ · frontend build ✓.

## Testing checklist
- [ ] Tasks: claim a tier → reward + "⚡ New Task Unlocked"; locked tiers can't be claimed (API 400).
- [ ] Lab/Battery/Solar/Quantum task chains progress from real upgrade levels.
- [ ] Reply/discussion task chains progress from group activity.
- [ ] Weekly tap cap: after 50k tap-XP in a week, taps earn 0 with the cap message.
- [ ] Community tab shows the full earning panel + popup on first open.
- [ ] Admin → Puzzles: release hints (appear in-app), Close/Skip → "Puzzle Closed Forever", copy
      buttons work, Mark Posted toggles indicators; non-admins get 403.
- [ ] Puzzle answer accepts an `accepted_variations` value.

## Git + Render
```bash
cd zelion-reactor
git add -A
git commit -m "Expand task chains (lab/replies/discussion/streak/legendary/social), puzzle admin control center, weekly XP cap, community info panel"
git push origin main
```
Render auto-deploys; **migration 015** + `tasks.ensure_seed` (upsert) run on boot. No env changes
required (`WEEKLY_TAP_CAP`, reply/discussion XP have sensible defaults; override via env if desired).
