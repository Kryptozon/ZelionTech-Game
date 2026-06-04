# 🩹 Patch — Balanced Economy + Quiz Penalties + Intelligence Puzzles

Extends the existing project. No rebuild; no features removed.

## Migrations (run on boot, idempotent)
- `011_tap_economy.sql` — tap_state += daily_tap_reset_at, overheat_value, cooldown_until,
  fatigue_stage, suspicious_tap_score, last_tap_window.
- `012_puzzles.sql` — puzzles, puzzle_attempts, daily_puzzle_sessions, puzzle_hints,
  puzzle_scripts, puzzle_winners.
- `013_upgrade_scaling.sql` — cost_growth=1.65, max levels (Core/Battery 20, Solar 15, Fusion 10, Quantum 5).

## Backend modified
- `bot/services/economy.py` — **harder level curve** `xp_threshold = 250*(level-1)^1.8`
  (L2:250, L3:871, L4:1806, L5:3031, L10:13049), `rank_name`, extended RANKS to L10, and
  **`deduct_points`** (floors balance at 0, never lowers level).
- `bot/services/tap.py` — full anti-farm rewrite: **daily rewarded-tap caps by level**
  (300/500/800/1200/1800, +200/level after), **per-level energy cost**, **fatigue** (100%/75%/50%),
  **overheat → 5-min cooldown**, **soft-capped points-per-tap** (diminishing >+10, hard cap +22),
  **anti-autoclicker** (≤20 taps/s, ≤50/req, nonce idempotency, suspicious_tap_score, silent
  shadow-limit). `get_state`/`tap` return all limits/heat/cooldown/level fields.
- `bot/services/quiz.py` — **wrong = −1 ZLN-XP** (floored), streaks **5→+10, 10→+25, 25→+100**,
  returns correct_answer + explanation, **5 wrong → Operator Training Required** + 5-min cooldown.
- `bot/services/puzzles.py` (NEW) — daily/weekly puzzle, server-side answer validation (answers
  never sent to users), rewards 20/50/100/250, wrong penalty 2 / legendary 5, **5 wrong → 15-min
  cooldown**, history, leaderboard, admin view (answer/hints/scripts).
- `bot/services/puzzle_seed.py` (NEW) — generates **199 puzzles** (80/59/40/20) — Morse, Binary,
  Cipher, Sequence, Ecosystem, Treasure Hunts — and exports `/puzzles/{easy,medium,hard,legendary}`,
  `/daily_hints`, `/youtube_scripts`, `/telegram_hints`. Seeds DB idempotently; auto-seeds on boot.
- `bot/web/api.py` — tap state returns the new fields; **puzzle endpoints**
  `GET /api/puzzles/daily|status|history|leaderboard`, `POST /api/puzzles/answer`, and admin
  `GET /api/admin/puzzles`, `POST .../{id}/activate|deactivate`, `GET .../{id}/hints|youtube-script|telegram-post`.
- `bot/main.py` — seeds the puzzle bank on boot (`puzzle_seed.ensure_min`).

## Frontend modified
- `screens/Tap.jsx` — daily-taps-left, **overheat meter**, cooldown countdown, **level progress +
  next-level XP**, points-per-tap, **fatigue warning**, “earn more via quizzes/puzzles/missions”,
  **daily-cap modal**; keeps Validator Yield. Uses new `/api/tap` fields.
- `screens/Quiz.jsx` — on wrong: shows **−ZLN-XP**, **correct answer**, explanation, and
  **Operator Training Required** notice.
- `screens/Intelligence.jsx` (NEW) — Intelligence tab: Daily Puzzle + Weekly Mystery Hunt,
  difficulty, reward, attempts-remaining, answer input, **Need a hint? → 📺 YouTube / 📢 Telegram**
  (hints never shown in-app), cooldown countdown, leaderboard.
- `screens/Admin.jsx` — **Puzzle Manager** tab: list, see answer, activate/deactivate, view hints/script.
- `App.jsx` — added **Intel** tab. `api.js` — puzzle + tap client methods.

## Validation (run here — all pass)
- Level curve matches spec; `level_for(900)=3`, `level_for(5500)=6`.
- Daily caps 300/500/800/1200/1800 (+200/lvl); energy/tap scales; fatigue 1.0/0.75/0.5; overheat→cooldown.
- Upgrade cost @1.65 = [50,82,136,224,370].
- **Puzzle public payload excludes `answer` + `explanation`** (no leakage).
- All puzzle+tap routes registered.
- Folders exist: puzzles 80/59/40/20; daily_hints/youtube_scripts/telegram_hints = 199 each.
- Backend `py_compile` ✓ · frontend `npm run build` ✓.

> Not runnable here (no live DB/Redis): the cap/overheat/penalty *DB writes* are exercised on deploy
> — see the testing checklist below.

## Testing checklist
- [ ] Tap past the daily cap → earns 0, modal “Daily Reactor capacity reached”.
- [ ] Energy 0 → taps give 0 ZLN-XP. Higher level → more energy/tap.
- [ ] Rapid tapping → fatigue 75%/50% then **overheat + 5-min cooldown** (rewards blocked).
- [ ] Upgrade costs scale ×1.65; “MAX LEVEL” at caps; per-tap soft-capped (no explosion).
- [ ] Wrong quiz answer → −1 ZLN-XP, shows correct answer + explanation; 5 wrong → training notice.
- [ ] Wrong puzzle → −2 (legendary −5); 5 wrong → 15-min lock. Balance never below 0.
- [ ] Daily puzzle solvable; YouTube/Telegram hint buttons open the channels; answer never in network payload.
- [ ] Admin → Puzzles: see answer, activate/deactivate, view hints/script.

## Git + Render
```bash
cd zelion-reactor
git add -A
git commit -m "Balanced anti-farm tap economy + harder levels + quiz/puzzle penalties + 199-puzzle Intelligence system"
git push origin main
```
Render auto-deploys; migrations **011–013** + the puzzle seed run on boot (no env changes).
The `/puzzles`, `/daily_hints`, `/youtube_scripts`, `/telegram_hints` folders are server-side admin
artifacts (never web-served); answers are exposed only to ADMIN_IDS via the admin API.
