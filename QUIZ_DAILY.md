# 🧠 Daily Quiz + ZLN-XP + Logo (Phase 7 patch)

Patches the existing project. No rebuild.

## 1. Files added
```
db/migrations/007_quiz_daily.sql     # daily_quiz_sessions, question_generation_logs,
                                     # quiz_questions += source_section/reward/active/slug
bot/services/quiz_seed.py            # 52 curated fact-checked Qs + KB generator -> 300, idempotent
frontend/public/zelion-logo.png      # <-- YOU add this (your uploaded gold logo). PNG preferred.
QUIZ_DAILY.md
```
## Files modified
```
bot/services/quiz.py     # session-based daily system (5/24h, level-scaled, no-repeat, countdown)
bot/web/api.py           # /api/quiz/daily (hides answers), /answer, /status, /history, /rank
bot/main.py              # auto-seed curated bank on boot (ensure_min) -> never "No questions yet"
bot/handlers/admin.py    # /seedquestions, /genquiz (reseed), /kbrefresh, /quizstats, /quizpending
                         #   all wrapped in try/except -> always reply (started/success/error)
bot/handlers/core.py     # dashboard label polish
frontend/src/screens/Quiz.jsx  # "Daily Zelion Challenge" UI: 5 slots, progress, badges,
                               #   explanation + source section, completion countdown
frontend/src/ui.jsx      # Logo uses /zelion-logo.png (falls back to vector)
frontend/index.html      # favicon/apple-touch-icon -> zelion-logo.png
+ 54 files: every visible "ZP" / 💎 renamed to "ZLN-XP"
```

## 2. Logo — one manual step (I can't write your image bytes)
Save your uploaded gold-Z image as:
```
frontend/public/zelion-logo.png
```
It is then used automatically in the tap button, splash, navbar, quiz, leaderboard,
profile badge, and favicon (the code prefers PNG, falling back to the vector if absent).

## 3. Daily quiz rules (implemented)
- **5 questions per user per rolling 24h** via `daily_quiz_sessions` (expires_at = created+24h).
- **Easy first**, difficulty scales with level: L1–2 beginner · L3–4 +intermediate ·
  L5–7 intermediate+advanced · L8+ advanced+expert (auto-fallback to easier if short).
- **No repeats** until the user's pool is exhausted (`id NOT IN attempts`).
- **Correct** → ZLN-XP (5/10/20/35 by tier) + streak bonus (3→+10, 5→+25, 10→rank-up).
  **Wrong** → explanation shown, **no reward**.
- After 5 → "Daily quiz completed" + live countdown to reset.
- Answers are hidden by the API until the user submits.

## 4. Question bank
- **52 curated, fact-checked** questions (verified against the whitepaper: ZEV = Zelion Energy
  Validator, 3-layer architecture, ZLN fixed supply 500M + exact allocations, vesting, roadmap
  phases, BNB choice, ESG/CSRD, carbon, RWA, DePIN, security, competitive positioning…).
- A **grounded generator** tops the pool to **300** from KB chunks (every question cites a source).
- **Idempotent** via `slug = sha1(question)` + `ON CONFLICT (slug) DO NOTHING`.
- All seeded questions are **approved + active** → no manual approval needed for daily play.
- On boot, `quiz_seed.ensure_min()` guarantees ≥25 active questions (curated only, no AI/KB needed),
  so the Mini App never shows "No questions yet".

## 5. Admin commands (now always reply)
| Command | Reply |
|---|---|
| `/seedquestions` | seeds curated + KB to 300, reports counts |
| `/genquiz` | (re)builds the bank, reports active count |
| `/kbrefresh` | imports docs + crawls site, reports chunks per category (or error) |
| `/quizstats` | total/active/pending, by-difficulty, attempts, daily sessions, accuracy |
| `/quizpending` | lists pending (advanced) questions; `/qok_<id>` `/qno_<id>` |

## 6. API
`GET /api/quiz/daily` · `POST /api/quiz/answer` · `GET /api/quiz/status` ·
`GET /api/quiz/history` · `GET /api/quiz/rank` (+ all prior endpoints).

## 7. Testing checklist
- [ ] Deploy → boot log shows `Quiz bank ready — 52 active question(s)`.
- [ ] Open Mini App → Quiz tab shows **Daily Zelion Challenge**, 0/5, a beginner question, +5 ZLN-XP.
- [ ] Correct answer → green, ZLN-XP added, explanation + source section shown; progress bar fills.
- [ ] Wrong answer → red, explanation shown, **no** ZLN-XP.
- [ ] After 5 → "Daily quiz completed" + countdown; a 6th is not served until reset.
- [ ] Level up a test user → harder questions appear.
- [ ] Everywhere shows **ZLN-XP** (tap, lab, missions, leaderboard, profile, proof messages).
- [ ] `/seedquestions` then `/quizstats` → ~300 active; re-running `/seedquestions` adds 0 (idempotent).
- [ ] All admin commands reply (success or error), never silent.
- [ ] Logo: after adding `zelion-logo.png`, it appears on tap button/splash/navbar/quiz/profile/favicon.

## 8. GitHub push
```bash
cd zelion-reactor
# add your logo first:
#   copy your uploaded image to frontend/public/zelion-logo.png
git add -A
git commit -m "Phase 7: daily quiz (5/24h), 300-question seed bank, ZLN-XP rename, gold logo"
git push origin main
```

## 9. Render redeploy
- Auto-deploys on push (Blueprint `autoDeploy: true`). Otherwise: Render dashboard →
  service **zeliontech-game** → **Manual Deploy → Deploy latest commit**.
- Migrations `004–007` run automatically on boot; `ensure_min` seeds the curated bank.
- After deploy, in the bot run **`/seedquestions`** once to expand the bank toward 300
  (curated alone already makes the daily quiz fully playable).
- No env changes required.
