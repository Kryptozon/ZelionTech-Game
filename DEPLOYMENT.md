# 🚀 Deployment Checklist — Zelion Reactor

## 1. Create the bot
- [ ] Open [@BotFather](https://t.me/BotFather) → `/newbot` → name + username (e.g. `ZelionReactorBot`).
- [ ] Copy the **BOT_TOKEN**.
- [ ] `/setprivacy` → **Disable** (only needed later if the bot must read group messages for Phase 2 group-activity points). For Phase 1 DM gameplay, leave default.
- [ ] (Optional) `/setdescription`, `/setuserpic`, `/setcommands`:
  ```
  start - Enter the Reactor
  menu - Open main menu
  help - How to play
  ```

## 2. Get your admin ID
- [ ] DM [@userinfobot](https://t.me/userinfobot) → copy your numeric ID into `ADMIN_IDS`.

## 3. Prepare the server
- [ ] Ubuntu 22.04+ VPS (Hetzner/DigitalOcean/Railway). Install Docker + Compose.
- [ ] `git clone` (or copy) the `zelion-reactor` folder onto the server.

## 4. Configure
- [ ] `cp .env.example .env`
- [ ] Set `BOT_TOKEN`, `BOT_USERNAME`, `ADMIN_IDS`.
- [ ] Confirm the official `LINK_*` URLs.

## 5a. Run (polling — simplest, no domain needed)
- [ ] `.env`: `USE_WEBHOOK=false`
- [ ] `docker compose up --build -d`
- [ ] `docker compose logs -f bot` → expect `Starting polling…`

## 5b. Run (webhook — for scale/production)
- [ ] Point a domain at the server, put **nginx + HTTPS (Let's Encrypt)** in front, proxy to `:8080`.
- [ ] `.env`: `USE_WEBHOOK=true`, `WEBHOOK_BASE=https://yourdomain`, `WEBHOOK_SECRET=<long-random>`.
- [ ] `docker compose up --build -d` → the bot calls `setWebhook` on startup.
- [ ] Verify: `https://api.telegram.org/bot<TOKEN>/getWebhookInfo`.

## 6. Test
- [ ] `/start` → welcome + menu.
- [ ] Claim energy, run a quiz, open a social mission, submit proof.
- [ ] As admin: `/pending` → approve → confirm user receives points.
- [ ] Run the full `TESTING.md` checklist.

## 7. Phase 2/3 — enable social auto-verify + group rewards + events
**Telegram auto-verify (@zeliontechofficial, @zelionglobal):**
- [ ] Add the bot to **both channels** and promote to **admin** — `getChatMember` only works on a member/admin chat.
- [ ] Confirm `TG_OFFICIAL_CHAT` / `TG_GLOBAL_CHAT` in `.env` match the usernames.
- [ ] Test: open a Telegram social mission → **Verify now** → points awarded instantly.

**Group activity rewards (real messages + reactions):**
- [ ] Add the bot to your community **group** and promote to **admin** (so it receives messages + reaction updates).
- [ ] In @BotFather → `/setprivacy` → **Disable** (lets the bot read group messages to score them).
- [ ] Set `GROUP_CHAT_ID` in `.env` to the group's numeric id (or leave `0` to accept any group the bot is in).
- [ ] The bot auto-requests `message_reaction` updates (no manual config needed).
- [ ] Test: post a real message in the group → earn XP (capped 20/day); add a reaction → earn XP (capped 5/day).

**Weekly reset + surge hours (automatic):**
- [ ] Weekly board resets every **Monday 00:00 UTC** automatically; top-3 get `WEEKLY_BONUS` and a group post.
- [ ] Set `SURGE_HOURS` (UTC, e.g. `18,21`) for automatic 2× point windows, or run `/surge 2 60` manually.
- [ ] Run `/weeklyreset` to close the board on demand.

> **Scaling note:** Phase 1–3 run in one bot process (background asyncio jobs). For higher load, split the
> scheduler/broadcast workers out and move to managed Postgres + Redis — the service layer is already decoupled.

## 8. Webhook mode (production HTTPS)
The bot already calls `setWebhook` on boot when `USE_WEBHOOK=true` (see `bot/main.py::run_webhook`).
You only need a domain + HTTPS in front of port 8080.

**a) DNS + nginx**
```bash
sudo apt install -y nginx
sudo cp deploy/nginx.conf /etc/nginx/sites-available/zelion
sudo sed -i 's/your-domain.com/YOURDOMAIN/g' /etc/nginx/sites-available/zelion
sudo ln -s /etc/nginx/sites-available/zelion /etc/nginx/sites-enabled/zelion
sudo nginx -t
```

**b) HTTPS with certbot (Let's Encrypt)**
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d YOURDOMAIN
sudo systemctl reload nginx
```

**c) Flip the bot to webhook**
```bash
# In .env:
USE_WEBHOOK=true
WEBHOOK_BASE=https://YOURDOMAIN
WEBHOOK_SECRET=<a long random string>
# then:
docker compose up -d --build
```

**d) Verify webhook**
```bash
TOKEN=8014869783:AAGaFoLJ1RJ_vNb-2XLb4mOe-eYGeD0PYJk
curl -s "https://api.telegram.org/bot$TOKEN/getWebhookInfo"
# To remove a webhook (revert to polling):
curl -s "https://api.telegram.org/bot$TOKEN/deleteWebhook"
```

## 9. Final deployment commands
```bash
# --- First launch (build + run all services) ---
docker compose up -d --build

# --- Logs / status ---
docker compose logs -f bot          # expect: ✓ PostgreSQL, ✓ Redis, ✓ Bot token, 🚀 Starting
docker compose ps

# --- Restart / stop ---
docker compose restart bot
docker compose down                 # stop (keeps volumes/data)
docker compose up -d                # start again

# --- Migrations ---
# Schema + db/migrations/*.sql run automatically on every bot boot (idempotent).
# To re-apply manually against the running DB:
docker compose exec -T db psql -U zelion -d zelion -f /docker-entrypoint-initdb.d/init.sql

# --- Backups ---
docker compose exec -T db pg_dump -U zelion zelion > backup_$(date +%F).sql   # backup
cat backup_2026-06-03.sql | docker compose exec -T db psql -U zelion -d zelion # restore
# Redis is append-only (redisdata volume) and auto-persists.

# --- Daily backup cron (host) ---
# 0 3 * * * cd /opt/zelion-reactor && docker compose exec -T db pg_dump -U zelion zelion > /backups/zelion_$(date +\%F).sql
```

## 10. Launch checklist (verify before going public)
- [ ] `docker compose logs bot` shows ✓ PostgreSQL, ✓ Redis, ✓ Bot token @ZelionTechGameBot, ✓ Admin IDs `[1087968824]`.
- [ ] Bot is **admin** in @zeliontechofficial and @zelionglobal → logs show "Channel … reachable".
- [ ] Bot is **admin** in group `-1003423593105`, privacy disabled → logs show "Group … reachable".
- [ ] **Telegram auto-verification** works (Verify now → instant points).
- [ ] **Proof approvals** work (submit → admin `/pending` → approve → user auto-credited within 24h).
- [ ] **Leaderboard updates** (weekly + all-time render from Redis; points move after actions).
- [ ] **Referrals activate** (invitee ≥24h + ≥50💎 → referrer paid +150💎).
- [ ] **Surge hours** work (`/surge 2 5` → group announce → ×2 points).
- [ ] **Weekly reset** works (`/weeklyreset` → top-3 bonuses + snapshot row).
- [ ] **Analytics** works (`/analytics` shows DAU/WAU, missions, proofs, referrals).
- [ ] **Anti-spam** works (rapid taps debounced; group anti-flood 60s; daily caps enforced).
- [ ] Run the full `TESTING.md` end-to-end.

## 11. Launch announcement (post in your channels)
> ⚡ Zelion Reactor is LIVE! Charge daily, follow our channels for points, invite
> friends, and climb to 🔮 Oracle. Start now 👉 t.me/ZelionTechGameBot

## Backups & ops
- [ ] Daily `pg_dump` cron (command above). Test a restore once.
- [ ] `.env` is git-ignored (`.gitignore`) and excluded from the image (`.dockerignore`). Rotate `WEBHOOK_SECRET`/`BOT_TOKEN` if leaked.
- [ ] Monitor `docker compose logs` / uptime-check the webhook URL.
- [ ] `restart: always` on all 3 services survives reboots; enable Docker on boot: `sudo systemctl enable docker`.
