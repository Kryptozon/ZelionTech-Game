# 🩹 Patch — Progressive / Infinite Task System

Extends the existing project. No rebuild; nothing removed.

## What it fixes
Users used to run out of tasks. Now every chain auto-unlocks the next, harder tier when you
claim one, and **prestige chains generate new tiers forever** — designed for 6–12 months.

## New files
```
db/migrations/014_tasks.sql           # task_chains, task_definitions, task_claims,
                                       # user_task_progress, user_task_unlocks, achievement_tiers
bot/services/tasks.py                  # task engine: seed, server-side metrics, list, claim, prestige
frontend/src/screens/Tasks.jsx         # Reactor Missions screen
PATCH_TASKS.md
```
## Modified files
```
bot/web/api.py     # GET /api/tasks · POST /api/tasks/{id}/claim
bot/main.py        # tasks.ensure_seed on boot
frontend/src/api.js   # tasks() + claimTask()
frontend/src/App.jsx  # render Tasks screen
frontend/src/screens/Tap.jsx  # "🎯 Missions" button -> Tasks
```

## Chains seeded (9 chains, 45 tiers + infinite prestige)
Reactor Validation (taps 1k→1M), Power Surge (combo), Reactor Core (upgrade level),
Community (valid messages 25→10k), Quiz (correct answers), Intelligence (puzzles solved),
Social (channel/group/proof/X/YouTube — parallel), Elite Reactor Missions (account level →
Cadet/Operator/Engineer/Commander/Oracle), plus a hidden achievement. Exact tiers/rewards match the spec.

## How it works (server-authoritative, anti-abuse)
- **Progress is computed live** from real metrics — `tap_state.total_taps`/`best_combo`,
  `user_upgrades` (reactor_core level), `group_activity` messages, `quiz_attempts` correct,
  `puzzle_attempts` correct, `referrals`, approved social proofs, and account level. The frontend
  **cannot** set progress, unlock, or claim — every claim is validated in `tasks.claim()`.
- **Auto-unlock:** in a sequential chain only the next unclaimed tier is active; earlier are
  completed, later are locked (the immediate next shows as a 🔒 teaser). Claiming requires all
  previous tiers claimed **and** metric ≥ goal. On success → ZLN-XP via the idempotent ledger,
  claim recorded, the next tier becomes active, and the UI shows **"⚡ New task unlocked!"**.
- **Infinite prestige:** claiming the final tier of a prestige chain (taps, surge, messages,
  quiz, puzzles) inserts the next tier at **goal ×3, reward ×2** — tasks never end.
- **Tiers/badges:** Bronze → Silver → Gold → Platinum → Diamond → Reactor Elite → Reactor Legend
  → Reactor Oracle (in `achievement_tiers`).
- **Hidden achievement** is only revealed once it becomes claimable.

## Economy balancing (why it lasts 6–12 months)
- **Effort grows faster than reward.** Verified: taps goals scale ×{5,3,3.3,2,2.5,2,2} while
  rewards scale ×{2.5,2,2,2,2.5,2,2.5} — overall reward growth < requirement growth.
- Tap earning is already daily-capped (300–1,800/day) by the economy patch, so 1,000,000 taps
  ≈ months even before fatigue/overheat. Elite "Reactor Oracle" needs account **level 10**
  (≈13k+ XP on the 1.8 curve) → **< 1% of users**.
- Big chains require thousands of community messages / hundreds of puzzles — weeks-to-months of
  genuine engagement, not farmable in hours.

## Progression example
Day 1: claim "Validate 1,000 taps" (+100) → unlocks "5,000 taps". Send 25 messages (+100) →
unlocks 100. Solve 10 puzzles (+500). … Months later: finish 1,000,000 taps (+25,000) →
prestige "Validate 3,000,000" (+50,000) appears automatically.

## API
`GET /api/tasks` → `{chains:[{name,icon,tasks:[{id,tier_name,title,goal,reward,progress,status}]}],
completion_percent, completed, total}`. `POST /api/tasks/{id}/claim` → `{ok,reward,tier_name,new_tier}`.

## Daily / Weekly / Seasonal
`task_chains.period` supports `permanent|daily|weekly|seasonal` (these chains are `permanent`;
daily/weekly engagement is already covered by daily quiz, tap missions and group missions). Seasonal
chains can be added with `period='seasonal'` + `active=false` and toggled on by an admin.

## Testing checklist
- [ ] Open Reactor → 🎯 Missions: chains show with progress bars + total completion %.
- [ ] A tier with metric ≥ goal shows **Claim**; claiming awards ZLN-XP and reveals "⚡ New task unlocked!".
- [ ] Claiming is blocked if the metric isn't met or a previous tier is unclaimed (try via API → 400).
- [ ] Completed tasks collapse into the "✅ completed" section.
- [ ] Finish a chain's last tier → a harder prestige tier appears (taps/messages/quiz/puzzles/surge).
- [ ] Social tasks unlock independently as proofs are approved.
- [ ] Frontend cannot fake progress (all server-validated).

## Git + Render
```bash
cd zelion-reactor
git add -A
git commit -m "Add progressive/infinite task chains (auto-unlock + prestige tiers, server-validated)"
git push origin main
```
Render auto-deploys; **migration 014** + `tasks.ensure_seed` run on boot. No env changes.
