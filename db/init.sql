-- ============================================================
-- ZelionTech Reactor — schema (idempotent). Runs on first DB init
-- (docker-entrypoint-initdb.d) AND on bot startup (init_db()).
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id               BIGINT PRIMARY KEY,           -- telegram user id
    username         TEXT,
    first_name       TEXT,
    level            INT     DEFAULT 1,
    points           BIGINT  DEFAULT 0,            -- cached total (ledger is source of truth)
    referred_by      BIGINT,
    status           TEXT    DEFAULT 'active',     -- active | flagged | banned
    streak_count     INT     DEFAULT 0,
    last_daily_claim TIMESTAMPTZ,
    created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS energy (
    user_id     BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    current     INT DEFAULT 100,
    max_cap     INT DEFAULT 100,
    regen_rate  INT DEFAULT 5,                     -- per hour
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS missions (
    id            SERIAL PRIMARY KEY,
    code          TEXT UNIQUE,                     -- stable key, e.g. 'social_x'
    title         TEXT NOT NULL,
    description   TEXT,
    category      TEXT,                            -- daily | learn | social | referral
    platform      TEXT,                            -- facebook | x | instagram | ...
    energy_cost   INT  DEFAULT 0,
    xp_reward     INT  DEFAULT 0,
    cooldown_sec  INT  DEFAULT 0,
    repeatable    BOOLEAN DEFAULT FALSE,
    verification  TEXT DEFAULT 'manual',           -- auto | manual
    url           TEXT,
    quiz_question TEXT,
    quiz_options  JSONB,                           -- [{"text": "...", "correct": true}]
    is_active     BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS mission_completions (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT REFERENCES users(id) ON DELETE CASCADE,
    mission_id      INT REFERENCES missions(id),
    completed_at    TIMESTAMPTZ DEFAULT now(),
    next_eligible_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_completions_user ON mission_completions(user_id, mission_id);

CREATE TABLE IF NOT EXISTS social_accounts (
    id        BIGSERIAL PRIMARY KEY,
    user_id   BIGINT REFERENCES users(id) ON DELETE CASCADE,
    platform  TEXT,
    handle    TEXT,
    verified  BOOLEAN DEFAULT FALSE,
    UNIQUE(platform, handle)
);

CREATE TABLE IF NOT EXISTS proof_submissions (
    id            BIGSERIAL PRIMARY KEY,
    user_id       BIGINT REFERENCES users(id) ON DELETE CASCADE,
    mission_id    INT REFERENCES missions(id),
    platform      TEXT,
    claimed_handle TEXT,
    file_id       TEXT,                            -- telegram photo file_id
    status        TEXT DEFAULT 'pending',          -- pending | approved | rejected
    reviewed_by   BIGINT,
    reject_reason TEXT,
    created_at    TIMESTAMPTZ DEFAULT now(),
    reviewed_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_proof_status ON proof_submissions(status, created_at);

CREATE TABLE IF NOT EXISTS referrals (
    id           BIGSERIAL PRIMARY KEY,
    referrer_id  BIGINT REFERENCES users(id) ON DELETE CASCADE,
    invitee_id   BIGINT UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    status       TEXT DEFAULT 'pending',           -- pending | activated | rejected
    reward_given BOOLEAN DEFAULT FALSE,
    created_at   TIMESTAMPTZ DEFAULT now(),
    activated_at TIMESTAMPTZ
);

-- Immutable points ledger — source of truth. UNIQUE guards against double-pay.
CREATE TABLE IF NOT EXISTS points_ledger (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT REFERENCES users(id) ON DELETE CASCADE,
    amount     INT,
    reason     TEXT,                               -- daily | proof | referral | quiz | admin_grant
    ref_id     TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, reason, ref_id)
);

CREATE TABLE IF NOT EXISTS leaderboard_snapshots (
    user_id    BIGINT,
    board      TEXT,
    period_key TEXT,
    score      BIGINT,
    rank       INT,
    PRIMARY KEY(user_id, board, period_key)
);

CREATE TABLE IF NOT EXISTS admin_actions (
    id         BIGSERIAL PRIMARY KEY,
    admin_id   BIGINT,
    action     TEXT,
    target_id  BIGINT,
    detail     JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bans (
    user_id    BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    reason     TEXT,
    banned_by  BIGINT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- Seed missions (idempotent via ON CONFLICT on code)
-- Social-follow URLs are overwritten from .env at startup (seed_links()).
-- ============================================================
INSERT INTO missions (code, title, description, category, platform, xp_reward, verification, url) VALUES
 ('social_telegram_official','Join Telegram Official','Join the official ZelionTech Telegram channel.','social','telegram_official',50,'manual','https://t.me/zeliontechofficial'),
 ('social_telegram_global','Join Telegram Global','Join the ZelionTech Global community group.','social','telegram_global',50,'manual','https://t.me/zelionglobal'),
 ('social_x','Follow on X','Follow @zelion_tech on X (Twitter).','social','x',40,'manual','https://x.com/zelion_tech'),
 ('social_facebook','Follow on Facebook','Follow ZelionTech on Facebook.','social','facebook',40,'manual','https://www.facebook.com/share/17ikJfJe84/?mibextid=wwXIfr'),
 ('social_instagram','Follow on Instagram','Follow @zeliontech_zev on Instagram.','social','instagram',40,'manual','https://www.instagram.com/zeliontech_zev'),
 ('social_linkedin','Follow on LinkedIn','Follow ZelionTech on LinkedIn.','social','linkedin',40,'manual','https://www.linkedin.com/company/zeliontech/'),
 ('social_whatsapp','Join WhatsApp Channel','Follow the ZelionTech WhatsApp channel.','social','whatsapp',40,'manual','https://whatsapp.com/channel/0029VbCfgk34tRrtdCdS392k'),
 ('social_tiktok','Follow on TikTok','Follow @zeliontech_zev on TikTok.','social','tiktok',40,'manual','https://www.tiktok.com/@zeliontech_zev'),
 ('social_discord','Join Discord','Join the ZelionTech Discord server.','social','discord',40,'manual','https://discord.gg/7n8NCExs5'),
 ('social_youtube','Subscribe on YouTube','Subscribe to ZelionTech on YouTube.','social','youtube',40,'manual','https://www.youtube.com/@ZelionTech')
ON CONFLICT (code) DO NOTHING;

-- Learn / quiz missions (auto-verified)
INSERT INTO missions (code, title, description, category, xp_reward, energy_cost, cooldown_sec, repeatable, verification, quiz_question, quiz_options) VALUES
 ('quiz_zev','Clearance Test: ZEV','What does the ZEV pillar represent for ZelionTech?','learn',25,10,21600,true,'auto',
   'ZEV is best described as ZelionTech''s…',
   '[{"text":"Energy / vehicle product line","correct":true},{"text":"A competitor","correct":false},{"text":"A meme","correct":false}]'),
 ('quiz_community','Clearance Test: Community','Where does the ZelionTech community gather?','learn',25,10,21600,true,'auto',
   'The official community lives on…',
   '[{"text":"Telegram, X, Discord & more","correct":true},{"text":"Nowhere","correct":false},{"text":"Fax","correct":false}]')
ON CONFLICT (code) DO NOTHING;
