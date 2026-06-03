# 🛠 Admin Operating Manual — Zelion Reactor

Only Telegram IDs in `ADMIN_IDS` can use these. Every action is logged to `admin_actions`.

## Daily routine
1. `/pending` — review the proof queue (target: clear within **24h**).
   - Each proof arrives as a **photo + caption** with **✅ Approve / ❌ Reject** buttons.
   - The bot also auto-pings you hourly if any proof is older than 24h.
2. **Approve** → user is paid automatically (points ledger), social account marked verified,
   referral activation re-checked, user notified.
3. **Reject** → bot asks you for a reason → user is notified with that reason and may re-submit.
4. `/stats` — glance at users, 24h-active, new signups, pending proofs, activated referrals, bans.

## Reviewing proof — what to check
- Screenshot clearly shows the claimed username **following/joined** ZelionTech.
- Handle isn't an obvious throwaway; not a reused screenshot.
- Duplicate handles are auto-rejected on approve (one handle per platform across all users).
- If unsure, **Reject** with reason "unclear screenshot — please resubmit".

## Commands
| Command | Purpose |
|---|---|
| `/admin` | Show this menu |
| `/pending` | Send the pending proof queue with action buttons |
| `/stats` | KPIs |
| `/grant <user_id> <points>` | Manually award points (logged); user notified |
| `/ban <user_id> [reason]` | Suspend a cheater (blocks all bot use) |
| `/unban <user_id>` | Restore access |
| `/broadcast` | Send a message/photo to all users (throttled ~25/sec) |
| `/export` | Download a CSV of all users |
| `/analytics` | DAU / WAU + top events (24h) |
| `/shadow <id>` / `/unshadow <id>` | Shadow-ban: user keeps playing but earns **0 real points**, unaware. Best for suspected farmers you're still investigating. |
| `/surge <mult> <minutes>` | Start a Power Surge (e.g. `/surge 2 60`) — announced to the group, all points ×mult. |
| `/weeklyreset` | Close the weekly leaderboard now, pay top-3 bonuses, snapshot to history. |

## Anti-cheat playbook
- **Fake referrals:** rewards only fire when the invitee is ≥24h old AND has ≥50💎. Watch `/stats` activated-referrals vs new users; investigate spikes.
- **Multiple accounts / farming:** duplicate social handle → auto-reject on approve. Repeat offenders → `/ban`.
- **Spam:** 2-second per-user debounce is automatic. Persistent abusers → `/ban`.
- **Screenshot fraud:** reject + reason; `/ban` on repeat.
- A banned user keeps no access and earns nothing; unban is reversible.

## Tuning the economy
- Rewards/cooldowns live in `db/init.sql` (missions) and `bot/services/economy.py`
  (`DAILY_TABLE`, `LEVEL_THRESHOLDS`, referral constants). Change → rebuild bot container.
- Add a mission: `INSERT INTO missions(...)` (set a unique `code`), restart.
