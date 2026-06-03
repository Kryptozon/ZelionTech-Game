# 🧠 ZelionTech Knowledge Base & AI Quiz (Phase 5)

The quiz is grounded in **two sources** and never invents facts:
1. **Seed document(s)** in `knowledge/` — the **Institutional Whitepaper v3** (extracted to
   `zelion_infrastructure_whitepaper.md`) + the **verified facts** file. (`source_type='document'`)
2. **Live website** `https://zeliontech.com`, crawled on demand. (`source_type='website'`)

> `knowledge/` is git-ignored (the whitepaper is confidential). It IS included in local Docker
> builds. For Render, commit it to your **private** repo or rely on the website KB.

## Section taxonomy (req #1)
Every chunk is auto-classified into one of 14 categories (`bot/services/categories.py`):
Zelion Infrastructure · ZEV Device · ESG Verification · BNB Chain Coordination Layer ·
DePIN Integration · Tokenomics · Enterprise Deployment · Leadership/Team · Roadmap ·
Security Architecture · RWA Compatibility · Carbon Markets · AI/Data-Center Energy Demand ·
Renewable Energy Validation. *(Verified: the seed docs produce 94 chunks across these.)*

## Question types (req #5)
`mcq · true_false · scenario · architecture · tokenomics` — stored in `quiz_questions.qtype`.

## Difficulty tiers + XP (req #3, #6)
| difficulty | tier | XP |
|---|---|---|
| 1 | beginner | 5 |
| 2 | intermediate | 10 |
| 3 | advanced | 20 |
| 4 | expert | 35 |
Difficulty unlocks by user level (L1→beginner … L4+→expert). Already-answered questions aren't
repeated (`quiz_attempts` unique per user+question); selection prefers least-asked + random.

## Streak bonuses (req #7)
3 correct → **+10** · 5 correct → **+25** · 10 correct → **special rank-up** (+50).
Tracked in Redis (`quizstreak:<uid>`, daily TTL); a wrong answer resets the streak and triggers a 30s cooldown.

## Quiz ranks (req #8) — by lifetime correct answers
Reactor Cadet (0) → Energy Validator (10) → Grid Architect (30) → ZEV Operator (75) →
Infrastructure Elite (150) → Zelion Master (300). Shown in navbar, profile badge, and after each answer.

## Daily challenge (req #9)
`GET /api/quiz/daily` — 5 questions chosen **deterministically by date** (same for everyone),
stored in `daily_challenges`. Completing all 5 pays a **+50💎** bonus once per day.

## Safety (req #14, #9-safety)
- Each question is generated from **one verified KB chunk** and stores that chunk's `source_url`
  (+ `source_type`). If the excerpt is insufficient the model returns `{"skip":true}` — nothing invented.
- No `AI_API_KEY` → a deterministic, fully-grounded source-attribution generator is used instead.
- Generated questions start `pending`; `/genquiz` pre-generates **approved** batches for instant play.
- The Mini App shows “Based on the ZelionTech whitepaper/website” with the source link on every answer.

## Database (req #11)
`knowledge_pages`, `knowledge_chunks` (both + `source_type`, `category`),
`quiz_questions` (+ `qtype`, `tier`, `category`, `source_url`, `source_type`, `status`),
`quiz_attempts`, `daily_challenges`. Migrations `004_quiz_kb.sql` + `005_kb_doc_quiz.sql` (idempotent).

## Admin commands
- `/kbimport` — import seed document(s) from `knowledge/`.
- `/kbrefresh` (req #15) — rebuild KB from **document + zeliontech.com**, show per-category counts.
- `/genquiz [per]` (req #16) — pre-generate & **auto-approve** batches across all types/difficulties.
- `/quizpending`, `/qok_<id>`, `/qno_<id>` — review/approve/reject.
- Mini App **Admin → Questions / Knowledge** mirrors these.

## API endpoints (req #7-quiz)
`POST /api/admin/kb/refresh` · `GET /api/quiz/next` · `POST /api/quiz/answer` ·
`GET /api/quiz/history` · `GET /api/quiz/daily` · `GET /api/quiz/rank` ·
`GET /api/admin/questions` · `POST /api/admin/questions/:id/approve|reject`.

## Logo & UI (req #17, #18)
Gold **Z** SVG logo (`ui.jsx <Logo>`) used in: splash screen, navbar, loading screen,
leaderboard header, profile rank badge, and empty/daily quiz cards. Black/gold futuristic theme
throughout (`index.css`).

## First-run sequence
```
# in the bot (admin):
/kbrefresh        # crawl site + import whitepaper/facts -> 94+ categorized chunks
/genquiz 3        # generate & approve ~21 questions across types & tiers
# players: open Mini App -> Quiz -> Practice or Daily Challenge
```
