# 🩹 Patch — Hourly Reactor Capacity (replaces daily tap cap)

Extends the existing project. No rebuild; nothing else removed. The tap reward limit no longer
resets daily — it is now a **rolling 1-hour capacity** that refills every hour.

## Files modified
```
db/migrations/016_hourly_capacity.sql   # tap_state += hourly_tap_count, hourly_tap_reset_at
bot/services/tap.py                      # daily cap -> hourly rolling capacity (Redis window)
frontend/src/screens/Tap.jsx             # "Hourly Reactor Capacity" + refill countdown + modal
PATCH_HOURLY_CAPACITY.md
```

## Backend (`tap.py`)
- `daily_cap()` → **`hourly_cap(level)`** — same level-scaled values (300/500/800/1,200/1,800,
  then +200/level, capped). No daily reset.
- Live window in **Redis** (`taphr:{uid}`, incr per rewarded tap, 1-hour TTL → exact countdown,
  survives restarts). New helpers `_hourly()` (used/remaining/reset) and `_consume_hourly()`.
  Mirrored to DB columns `hourly_tap_count` / `hourly_tap_reset_at`.
- `POST /api/tap`: checks hourly capacity, awards only while capacity remains, returns
  `hourly_taps_remaining`, `hourly_reset_seconds`, and `hourly_cap_reached` + a
  "Reactor capacity depleted. Next refill in Xm Ys." message. Over the cap → 0 ZLN-XP (taps still
  animate).
- `GET /api/tap/state`: returns `hourly_tap_limit`, `hourly_taps_used`, `hourly_taps_remaining`,
  `hourly_reset_seconds`, `hourly_reset_at`.
- **Level scaling kept & improved:** higher level → bigger hourly capacity **and** more energy
  storage (`level_max_energy` = +25/level), on top of unlocking harder tasks.
- **All anti-farm mechanics preserved:** energy consumption, overheat + 5-min cooldown, tap fatigue,
  anti-autoclicker (≤20/s, nonce, soft-cap on points-per-tap), and the weekly XP cap.

## Tasks — unchanged (lifetime, NOT hourly)
Task chains read `tap_state.total_taps` (lifetime), which the hourly window never touches. "Validate
1,000 / 5,000 / 100,000 taps" keep cumulative progress. Daily/weekly/community/puzzle systems are
separate and untouched.

## Frontend (`Tap.jsx`)
- Card renamed **"Daily taps left" → "Hourly Reactor Capacity"** showing `used/limit` (e.g. 0 / 1800).
- When depleted: **"Refill in 42m 13s"** under the card + the modal now reads **"Reactor capacity
  depleted — Next refill in: …"**. Countdown ticks live each second.
- Still shows Reactor Energy, Reactor Heat (overheat meter), Level progress, points per tap.
- All "Daily" tap wording removed.

## Validation (run here — all pass)
- `hourly_cap` L1–7 = 300/500/800/1200/1800/2000/2200 · `level_max_energy` +25/level.
- `get_state` returns all 5 hourly fields, **no** `daily_tap_*`.
- Window sim: fresh 0/300/3600 → after 250 = 250/50 → after +100 = capped, remaining 0.
- Backend `py_compile` ✓ · frontend build ✓.

## Testing checklist
- [ ] Tap screen shows "Hourly Reactor Capacity 0/1800" (level-scaled).
- [ ] Earn until capacity hits 0 → taps animate but award 0 ZLN-XP; "Refill in …" countdown shows.
- [ ] Wait 1 hour → capacity refills to full and earning resumes.
- [ ] Higher level → larger capacity and slightly larger max energy.
- [ ] Overheat, energy depletion, fatigue, and anti-autoclicker still trigger.
- [ ] Task chain "Validate N taps" keeps lifetime progress across hours (does not reset).
- [ ] `GET /api/tap/state` returns hourly_tap_limit/used/remaining/reset_at/reset_seconds.

## Git + Render
```bash
cd zelion-reactor
git add -A
git commit -m "Replace daily tap cap with hourly reactor capacity (rolling 1h refill); keep level scaling & anti-farm"
git push origin main
```
Render auto-deploys; **migration 016** runs on boot. No env changes. (Redis is already configured;
the hourly window uses it.)
