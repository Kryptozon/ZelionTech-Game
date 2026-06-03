# ⚛️ Zelion Reactor — Tap-to-Earn Game (Phase 6)

Extends the existing Mini App with a Hamster-Kombat-style tap loop themed around
renewable-energy validation, plus a full fix of the proof-delivery system.

## Files added
```
db/migrations/006_tap_game.sql          # tap_state, tap_events, upgrades, user_upgrades,
                                        # passive_rewards, tap_missions, user_tap_missions
                                        # + proof_submissions.reward/.delivered
bot/services/tap.py                     # server-authoritative tap economy + passive yield
bot/services/upgrades.py                # Reactor Lab catalogue + cost scaling + buy
bot/services/tap_missions.py            # tap tasks + progress + claim
frontend/public/zelion-logo.svg         # gold Z reactor logo asset
frontend/src/screens/Tap.jsx            # Reactor Core tap screen (the playable logo)
frontend/src/screens/Lab.jsx            # Reactor Lab (upgrades + tasks)
TAPGAME.md
```
## Files modified
```
bot/web/api.py        # + tap/upgrade/passive/tap-mission endpoints; proof_submit uses deliver()
bot/services/proof.py # + deliver() (reliable admin send + logging), undelivered(), reward column
bot/keyboards.py      # proof_review_kb + 🚫 Ban button
bot/handlers/proof.py # uses deliver(); + Ban handler; richer admin message
bot/handlers/admin.py # + /pendingproofs, /proofdiag
bot/jobs/scheduler.py # + proof_delivery_retry_loop (every 2 min)
bot/middlewares.py    # AntiSpam no longer debounces messages (was dropping proof steps!)
frontend/src/ui.jsx   # Logo now renders the gold-Z asset
frontend/src/App.jsx  # Reactor tab is home; + Lab tab
frontend/src/index.css# reactor pulse / tap waves / floating +ZP / surge / spark
frontend/src/api.js   # tap endpoints
```

## Tap economy (server-authoritative — req #11)
- **ZP** = the existing `users.points` ledger (so leaderboards & anti-cheat are unified).
- **Reactor Energy** lives in `tap_state` (separate resource, lazy-regen).
- `POST /api/tap {taps, nonce}` is the only way to earn from taps. The server:
  idempotency-guards the `nonce`, rate-limits (max 15 POST/3s, ≤50 taps/req), clamps taps to
  available energy, computes ZP from upgrades, applies combo surge, writes the ledger + `tap_events`.
  **The frontend never sets rewards.**

## Upgrades (Reactor Lab) — req #4
| code | stat | effect/level |
|---|---|---|
| Reactor Core | points_per_tap | +1 |
| Battery Pack | max_energy | +500 |
| Solar Amplifier | recharge_rate | +1/s |
| ZEV Validator | passive_rate | +50 ZP/h |
| Proof Engine | combo_mult | +0.1 |
Cost = `base_cost × growth^level`. Buying spends ZP via a negative idempotent ledger entry.

## Power Surge combos — req #6
Tracked in Redis (`combo:<uid>`, 5s TTL): 10→Combo (×1.2), 50→Surge (×1.5), 100→Overdrive (×2.0).
Screen flashes + haptics on surge; `+ZP` floats on every tap; expanding energy rings.

## Passive (Validator Yield) — req #5
`ZEV Validator` level → ZP/hour, accrues offline up to **8h**, manual **Claim** button + countdown.

## Tap missions — req #7
`taps · energy · combo · upgrade · yield · quiz` goals, server-computed progress, one-time claim.

## Proof system fix (req #10) — what was broken & fixed
- **Root cause found:** the anti-spam middleware was debouncing *messages*, which could drop the
  proof screenshot/handle in the FSM → no submission was created → admin got nothing. Now anti-spam
  only debounces button taps.
- **Reliable delivery:** `proof.deliver()` sends every proof to **all `ADMIN_IDS` (1087968824)** with
  photo + full detail (username, Telegram ID, platform, submitted handle, reward, timestamp, proof ID)
  and **✅ Approve / ❌ Reject / 🚫 Ban** buttons. First success marks `delivered=true`.
- **Fallback/retry:** if every send fails, the proof stays `delivered=false`; a background job retries
  every 2 minutes. The user still sees “proof submitted, review within 24h”.
- **Logging:** submissions, deliveries, failures, approvals, rejections, bans all logged.
- **Ban flow:** rejects the proof + bans the user, logged in `admin_actions`.
- **Commands:** `/pendingproofs` (durations), `/proofdiag` (admin-id/health self-check), plus the
  Mini App **Admin → Proofs** panel.

## New API endpoints
`GET /api/tap/state` · `POST /api/tap` · `GET /api/upgrades` · `POST /api/upgrades/:code/buy` ·
`GET /api/passive` · `POST /api/passive/claim` · `GET /api/tap/missions` ·
`POST /api/tap/missions/:id/claim` (+ all prior game/quiz/admin endpoints).

## Logo usage (req #14)
The gold Z (`frontend/public/zelion-logo.svg`) renders in: splash, navbar, **the Reactor Core tap
button (150px center)**, loading screen, leaderboard header, profile badge. Replace with a PNG by
dropping `frontend/public/zelion-logo.png` and pointing `LOGO_SRC` in `ui.jsx` at it.

## Deployment
No new infra. The multi-stage Dockerfile already builds the frontend (the new `public/` asset is
copied automatically). Migrations `006` run on boot. Render/webhook/Mini App URL unchanged
(`https://zeliontech-game.onrender.com/app`).

## Testing checklist
- [ ] Open Mini App → **Reactor** tab is default; gold Z pulses; tapping shows `+ZP` floats + ring waves + haptics.
- [ ] Energy bar drains on taps and regenerates over time; taps stop at 0 energy.
- [ ] Rapid tapping raises the Power Surge counter; ≥50 flashes the screen; server caps auto-clicker speed.
- [ ] Reactor Lab: buy Reactor Core → points-per-tap increases; buy ZEV Validator → Validator Yield appears.
- [ ] Validator Yield accrues, **Claim** credits ZP (capped 8h).
- [ ] Tap tasks show progress and pay out once when complete.
- [ ] Leaderboard/profile update with ZP; profile shows quiz rank badge with logo.
- [ ] **Proof:** submit a social proof in the bot DM → admin **1087968824 receives photo + buttons immediately**.
- [ ] Approve → user auto-credited + “approved” message; Reject → reason prompt → user notified; Ban → user banned + proof rejected.
- [ ] `/proofdiag` shows the admin id and undelivered count; `/pendingproofs` lists with durations.
- [ ] Kill the admin chat (block bot), submit a proof → it stays undelivered; unblock → retry job delivers within 2 min.
