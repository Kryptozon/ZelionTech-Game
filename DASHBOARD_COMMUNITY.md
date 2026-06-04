# 🛡️ Admin Dashboard + 💬 Community (Phase 8 patch)

Patches the existing project. No rebuild. Telegram proof forwarding is removed —
all moderation happens inside the Mini App **Admin** tab.

## Files added
```
db/migrations/008_dashboard_community.sql   # proof screenshot (BYTEA) + community tables
bot/services/community.py                   # daily discussion, group missions, score, leaderboard
frontend/src/screens/Community.jsx          # Community tab
DASHBOARD_COMMUNITY.md
```
## Files modified
```
bot/services/proof.py        # store screenshot in DB; list_by_status/get_image/dashboard_stats/
                             #   ban_and_reject_all; REMOVED deliver()/undelivered()/retries
bot/services/group.py        # strict anti-spam (min 20 chars, 90s, daily cap, dup hash,
                             #   emoji/low-value filter) + reply & discussion rewards
bot/handlers/proof.py        # DM proof still works but saves screenshot bytes (no forwarding)
bot/handlers/group.py        # detect replies + discussion answers
bot/handlers/admin.py        # /pending now points to the dashboard (no Telegram review buttons)
bot/jobs/scheduler.py        # removed proof delivery/SLA loops; added daily discussion +
                             #   group leaderboard posters
bot/web/api.py               # proof_submit accepts base64 image; full admin proof endpoints
                             #   + image endpoint + ban + banned + proof-stats; community endpoints
bot/config.py                # GROUP_MSG_MIN_LEN=20, GROUP_FLOOD_SEC=90, reply/discussion XP,
                             #   DISCUSSION_HOUR
frontend/src/screens/Admin.jsx     # full moderation dashboard (sections, filters, modal, counters)
frontend/src/screens/Missions.jsx  # screenshot upload on proof submission
frontend/src/App.jsx               # Community tab; Admin tab admin-only; passes me to Admin
frontend/src/api.js                # new admin + community client methods
.env.example                       # new community/anti-spam vars
```

## PART A — Proof moderation in the Mini App

### Flow
User opens a social mission → enters handle/link → **uploads a screenshot** → submits.
The image is stored in `proof_submissions.screenshot` (BYTEA, ≤3 MB) with status `pending`.
It **instantly appears** in the Admin tab — no Telegram chat involved. (Bot-DM submission still
works and also saves the screenshot bytes; nothing is forwarded.)

### Admin Dashboard (Admin tab, visible only to `is_admin`)
- Counters: **Pending · Approved today · Rejected today · ZLN-XP distributed · Banned**.
- Sections: **Pending / Approved / Rejected / Banned**.
- Filters: by **platform**, by **username/ID search**, newest-first.
- Each card: screenshot thumbnail (tap → full modal), username, Telegram ID, mission/platform,
  handle/link, timestamp, reward, status (+ rejection reason).
- Buttons on pending: **✅ Approve · ❌ Reject (reason prompt) · 🚫 Ban User**.

### Actions
- **Approve** → status `approved`, ZLN-XP awarded via the idempotent ledger, leaderboard updates,
  handle marked verified, referral activation checked, user gets a Telegram success message.
- **Reject** → optional reason → status `rejected`, user notified, can resubmit.
- **Ban** → user `banned`, all their pending proofs auto-rejected, can't submit/earn (the
  ban middleware already blocks banned users everywhere).

### Security
Every `/api/admin/*` route is gated by `@authed` (validates Telegram **initData** HMAC) **and**
`@admin_only` (`settings.is_admin` → only `ADMIN_IDS=1087968824`). The screenshot image route
takes initData as a query param (so `<img>` works) and is still admin-gated. Non-admins calling
admin APIs get **403**; the Admin tab itself renders **"Unauthorized"** for non-admins.

### Removed complexity
`proof.deliver()`, `undelivered()`, the 2-min retry loop, the SLA reminder loop, and the
Telegram review buttons are gone. No `PROOF_REVIEW_CHAT_ID` anywhere.

## PART B — Community / group engagement

- **Anti-spam** (`group.py`): min 20 chars, ≥12 alphanumerics, ≥3 distinct words (kills "hi" /
  emoji-only / repeated text), per-user **duplicate hash** (24h), **1 rewarded msg / 90s**, daily cap.
- **Rewards**: meaningful message (+3), reply to another member (+4), reaction (+2, capped),
  answering the **daily discussion** (+15, once/day). Surge multiplier applies.
- **Daily discussion**: scheduler posts a topic from `discussion_topics` to the group each day
  (after `DISCUSSION_HOUR` UTC), pins it; replies to it count as discussion answers.
- **Group missions** (daily + weekly) computed from `group_activity`; claim in the Community tab.
- **Group leaderboards**: Top Contributors Today / This Week (weighted score); the bot posts
  "Top Contributors Today" to the group every 6h.
- **Community tab**: daily discussion, your contribution score, group missions, today/week
  leaderboard, active surge banner, **Open Group** button.
- Momentum: Power Surge Hours already supported (`/surge`, `SURGE_HOURS`); surge banner shown
  in the Community tab; weekly winners announced in the group.

## Database (migration 008)
`proof_submissions += screenshot BYTEA, screenshot_mime, submitted_link, username_snapshot` ·
`daily_discussions` · `group_missions` + `user_group_missions` · `discussion_topics`
(seeded with 8 group missions + 12 topics). `group_activity += meta`.

## Render / env updates
No new **required** env vars. Confirm:
- `GROUP_CHAT_ID=-1003423593105`
- `ADMIN_IDS=1087968824`
- optional: `DISCUSSION_HOUR`, `GROUP_MSG_MIN_LEN`, `GROUP_FLOOD_SEC` (defaults are sensible).
Migrations run automatically on boot.

## Telegram requirements
- Add the bot to the group and make it **admin**; in BotFather `/setprivacy → Disable`
  (so it can read group messages). Reactions are tracked via `message_reaction` updates.

## Testing checklist
**Dashboard**
- [ ] As a normal user: Mini App has no Admin tab; calling `/api/admin/*` returns 403.
- [ ] As 1087968824: Admin tab visible; counters load.
- [ ] Submit a social proof with a screenshot in the Mini App → appears under **Pending** instantly with thumbnail.
- [ ] Tap thumbnail → full-screen modal.
- [ ] Approve → user's ZLN-XP rises, leaderboard updates, user gets a Telegram message, card moves to Approved.
- [ ] Reject with reason → user notified, can resubmit; card moves to Rejected.
- [ ] Ban → user can no longer use the bot/Mini App; pending proofs auto-rejected; appears under Banned.
- [ ] Filters by platform and username work.

**Community**
- [ ] Post a <20-char or "hi" message in the group → no reward. A meaningful 20+ char message → reward (once/90s).
- [ ] Reply to a member → reply mission progresses. Reply to the pinned daily discussion → discussion reward.
- [ ] Community tab shows discussion, contribution score, missions, leaderboard, surge banner, Open Group.
- [ ] Claim a completed group mission → ZLN-XP added.
- [ ] Daily discussion auto-posts after DISCUSSION_HOUR; "Top Contributors Today" posts every 6h.

## Deploy
```bash
cd zelion-reactor
git add -A
git commit -m "Phase 8: Mini App admin dashboard (DB screenshots) + community engagement; remove proof forwarding"
git push origin main        # Render auto-deploys; migration 008 runs on boot
```
