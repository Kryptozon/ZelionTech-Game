# 🩹 Patch — Quiz shuffle · Telegram links · Join rewards · Group msgs · Lab sync

Extends the existing project. No rebuild.

## 1. Quiz answer randomization (was always option A)
- `bot/services/quiz.py`: added `answer_order(question_id, user_id, n)` — a deterministic
  per-(question,user) permutation. Options are shuffled on serve (`daily_status`), the answer is
  validated server-side by mapping the shuffled choice back to the original (`submit_answer`), and
  the returned `correct_index` is in shuffled space. **No DB change; the existing 300-question bank
  works unchanged.** Different users see different placements (anti-memorization).
- Test: `tests/test_quiz_shuffle.py` → distribution **A:100 B:82 C:109 D:109** (all four), plus
  reversibility + per-user-variance checks. `python tests/test_quiz_shuffle.py` → PASSED.

## 2. Correct Telegram links
- `bot/config.py`: `GROUP_LINK=https://t.me/zelionglobal`, `CHANNEL_LINK=https://t.me/zeliontechofficial`.
- `bot/web/api.py`: `_group_link()` now returns the **public** link (no more `t.me/c/...` that showed
  "unavailable"); community/group payloads include `group_link` + `channel_link`.
- `frontend/src/screens/Community.jsx`: **Open Group** opens `https://t.me/zelionglobal`, new
  **Open Channel** opens `https://t.me/zeliontechofficial` (hard-coded fallbacks so they're never blank).

## 3. Join rewards
- `db/migrations/010_join_rewards.sql`: Join Channel → **+30 ZLN-XP** (`@zeliontechofficial`),
  Join Group → **+35 ZLN-XP** (`@zelionglobal`).
- `bot/web/api.py`: new `POST /api/missions/{id}/verify` — tries `getChatMember` auto-verify and
  awards instantly; if not joined it returns `needs_proof` so the user falls back to screenshot →
  Admin Dashboard. `frontend/src/screens/Missions.jsx`: "✅ Verify join" button for the Telegram
  missions; reward values (+30/+35) shown on the cards.

## 4. Group message rewards (+1 / valid msg)
- `bot/config.py`: `GROUP_MSG_XP=1`, `GROUP_MSG_MIN_LEN=10`, `GROUP_FLOOD_SEC=60`, daily cap kept.
- `bot/services/group.py`: relaxed `_meaningful()` to min 10 chars, blocks emoji-only & repeated spam.
- Group is `GROUP_CHAT_ID=-1003423593105` (Zelion Global). Requires bot **admin** + **privacy off**.
- `frontend/src/screens/Community.jsx`: always-visible rule card **“Earn +1 ZLN-XP for every valid
  group message after joining Zelion Global.”** + a **first-open popup** (localStorage-gated).

## 5. Reactor Lab upgrade sync (per-tap didn't update) — ROOT CAUSE FIXED
- `bot/services/tap.py` `effective_stats()` was **overwriting** a stat per upgrade row, so a
  level-0 upgrade sharing a stat (e.g. Fusion Reactor on `points_per_tap`) reset Reactor Core's
  bonus back to base → buying had no effect. Now it **accumulates** deltas. Reactor Core (+per-tap),
  Battery (+max energy), Solar Amplifier (+recharge) all apply correctly.
- `frontend/src/screens/Lab.jsx`: shows live **+X/tap · max · +/s** and refreshes tap state right
  after a purchase. The Reactor screen reloads tap state on view, so per-tap updates without reload.

## 6. UI: ZLN-XP labels intact everywhere; group/channel links work; join rewards shown; per-tap
updates; community rule visible (card + popup).

## Files modified
```
bot/services/quiz.py        bot/services/tap.py        bot/services/group.py
bot/config.py               bot/web/api.py
db/migrations/010_join_rewards.sql        tests/test_quiz_shuffle.py
frontend/src/screens/Community.jsx        frontend/src/screens/Missions.jsx
frontend/src/screens/Lab.jsx              frontend/src/api.js
.env (local group values)
```

## Validation (run here)
- ✓ backend `py_compile` · ✓ `npm run build` · ✓ quiz shuffle test PASSED (A/B/C/D distributed)
- ✓ `POST /api/missions/{id}/verify` registered · ✓ GROUP_LINK/CHANNEL_LINK correct ·
  ✓ `effective_stats` accumulates.

## Git + Render
```bash
cd zelion-reactor
git add -A
git commit -m "Fix quiz A/B/C/D shuffle, real Telegram links, +30/+35 join rewards, +1 group msg, Reactor Lab per-tap sync"
git push origin main
```
Render auto-deploys; **migration 010 runs on boot** (join rewards). No env changes required
(config defaults already match). Confirm the bot is **admin in `-1003423593105`** with **privacy
mode disabled** so group messages earn ZLN-XP.
```
# Quick post-deploy checks:
#  - Quiz: correct answer is sometimes B/C/D (not always A)
#  - Community: Open Group → t.me/zelionglobal ; Open Channel → t.me/zeliontechofficial
#  - Missions: Telegram cards show +30 / +35 ; "Verify join" works
#  - Reactor Lab: buy Reactor Core → "+X/tap" rises ; Reactor tap earns more
```
