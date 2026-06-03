# ✅ User Testing Checklist — Zelion Reactor

Run through this after every deploy. Use two Telegram accounts (one admin, one player),
plus a third to test referrals.

## Onboarding
- [ ] `/start` shows the welcome + main menu.
- [ ] `/start ref_<adminId>` from a NEW account creates a pending referral (check `referrals` table).
- [ ] Self-referral (`/start ref_<ownId>`) does NOT create a reward.

## Energy & daily
- [ ] **Claim Energy** grants energy + XP, sets streak Day 1.
- [ ] Second claim within 24h shows the cooldown alert.
- [ ] Energy passively regenerates over time (check **Profile** after a while).

## Quizzes
- [ ] Open a Clearance Test → wrong answer is rejected, no points.
- [ ] Correct answer spends energy, awards XP, sets cooldown.
- [ ] Re-opening before cooldown shows "on cooldown".
- [ ] Spending with insufficient energy is blocked.

## Social missions + proof (core flow)
- [ ] Social list shows all 10 platforms with status icons.
- [ ] Open a platform → "Open page" button opens the correct official URL.
- [ ] **Submit Proof** → bot asks for handle → asks for screenshot.
- [ ] Sending text instead of a photo at step 2 re-prompts for an image.
- [ ] After photo: user sees "PENDING — review within 24h"; **all admins receive the proof** with Approve/Reject.
- [ ] Submitting the same mission again while pending is blocked.

## Admin review
- [ ] **Approve** → user receives points automatically + approval message; mission shows ✅.
- [ ] **Reject** → bot asks reason → user receives rejection + reason; mission allows re-submit.
- [ ] Approving a duplicate handle (used by another account) auto-rejects.
- [ ] `/pending` lists all queued proofs with buttons.

## Referrals
- [ ] New invitee earns ≥50💎 and is ≥24h old → referrer gets +150💎 +50⚡ and a notification.
- [ ] Referral leaderboard (`👥 Referrals`) counts only activated referrals.

## Leaderboard & profile
- [ ] Points leaderboard ranks users by 💎 and shows "Your rank".
- [ ] Profile shows rank, energy, streak, referrals, progress to next rank.
- [ ] Crossing a level threshold triggers a LEVEL UP message.

## Admin tools
- [ ] `/stats` returns sane numbers.
- [ ] `/grant <id> <pts>` awards + notifies; `/ban` blocks the user from all actions; `/unban` restores.
- [ ] `/broadcast` delivers to all users (throttled).
- [ ] `/export` returns a CSV.

## Anti-spam
- [ ] Rapid double-taps within 2s are debounced (no double rewards).
- [ ] Banned user gets the suspended message and cannot act.

## Phase 2 — Telegram auto-verify
- [ ] Bot is admin in @zeliontechofficial and @zelionglobal.
- [ ] Social mission shows **Verify now (auto)** for the two Telegram missions.
- [ ] Tapping Verify BEFORE joining → "Not joined yet" alert, no points.
- [ ] Join the channel → Verify → instant points, mission shows ✅, cannot re-claim.

## Phase 2 — Group activity
- [ ] Bot is admin in the group; privacy mode disabled.
- [ ] A real message (≥3 chars, not a command) earns XP; check `group_activity` row + points.
- [ ] Sending many messages within 60s scores only once (anti-flood).
- [ ] More than 20 scored messages/day stop earning (daily cap).
- [ ] Adding a reaction earns XP (cap 5/day); removing a reaction earns nothing.

## Phase 2/3 — Events & leaderboard
- [ ] `/surge 2 5` posts a surge announcement to the group; a claim/quiz during it shows ⚡SURGE x2 and doubles points.
- [ ] Weekly board (`📅 Weekly`) and all-time board (`⭐ All-time`) both render from Redis.
- [ ] `/weeklyreset` closes the week, pays top-3 bonuses, and a snapshot row appears in `leaderboard_snapshots`.

## Phase 3 — Anti-cheat & analytics
- [ ] `/shadow <id>` → that user still sees "+points" messages but their `points` does NOT increase (ledger row = 0).
- [ ] `/unshadow <id>` restores normal earning.
- [ ] `/analytics` returns DAU/WAU and a top-events list.
- [ ] Duplicate social handle on a second account is auto-rejected on approve.
