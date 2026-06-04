-- ============================================================
-- Phase 8 migration — Mini App moderation dashboard (DB-stored screenshots)
--                   + community / group engagement
-- Idempotent.
-- ============================================================

-- ---- Proof: store the screenshot in the DB (no more Telegram forwarding) ----
ALTER TABLE proof_submissions ADD COLUMN IF NOT EXISTS screenshot       BYTEA;
ALTER TABLE proof_submissions ADD COLUMN IF NOT EXISTS screenshot_mime  TEXT;
ALTER TABLE proof_submissions ADD COLUMN IF NOT EXISTS submitted_link   TEXT;
ALTER TABLE proof_submissions ADD COLUMN IF NOT EXISTS username_snapshot TEXT;
CREATE INDEX IF NOT EXISTS idx_proof_status_created ON proof_submissions(status, created_at DESC);

-- ---- Community: extend group_activity to distinguish replies / discussion ----
-- (group_activity already exists: user_id, chat_id, kind, scored, created_at)
ALTER TABLE group_activity ADD COLUMN IF NOT EXISTS meta TEXT;

-- Daily discussion topics posted to the group.
CREATE TABLE IF NOT EXISTS daily_discussions (
    id              BIGSERIAL PRIMARY KEY,
    discussion_date DATE UNIQUE,
    topic           TEXT,
    message_id      BIGINT,           -- the bot's message id in the group (replies to it count)
    replies         INT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Group missions (daily / weekly) + per-user claims.
CREATE TABLE IF NOT EXISTS group_missions (
    id         SERIAL PRIMARY KEY,
    code       TEXT UNIQUE,
    period     TEXT,                  -- daily | weekly
    title      TEXT,
    metric     TEXT,                  -- messages | replies | reactions | discussion | days | referrals
    goal       INT,
    reward     INT,
    icon       TEXT,
    active     BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS user_group_missions (
    user_id    BIGINT REFERENCES users(id) ON DELETE CASCADE,
    mission_id INT REFERENCES group_missions(id) ON DELETE CASCADE,
    period_key TEXT,                  -- e.g. 2026-06-03 (daily) or 2026-W23 (weekly)
    claimed_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, mission_id, period_key)
);

-- Discussion topic pool (rotates).
CREATE TABLE IF NOT EXISTS discussion_topics (
    id     SERIAL PRIMARY KEY,
    topic  TEXT UNIQUE,
    active BOOLEAN DEFAULT TRUE
);

-- ---- Seed group missions ----
INSERT INTO group_missions (code, period, title, metric, goal, reward, icon) VALUES
 ('d_msg3',     'daily',  'Send 3 meaningful messages', 'messages',  3,  30, '💬'),
 ('d_reply2',   'daily',  'Reply to 2 members',         'replies',   2,  20, '↩️'),
 ('d_react5',   'daily',  'React to 5 messages',        'reactions', 5,  15, '👍'),
 ('d_discuss',  'daily',  'Answer the daily discussion','discussion',1,  40, '🗣️'),
 ('w_active5',  'weekly', 'Be active 5 days this week', 'days',      5, 150, '🔥'),
 ('w_reply20',  'weekly', 'Reply to 20 members',        'replies',   20,120, '🤝'),
 ('w_react25',  'weekly', 'React 25 times',             'reactions', 25, 80, '⚡'),
 ('w_invite3',  'weekly', 'Invite 3 active operators',  'referrals', 3, 200, '👥')
ON CONFLICT (code) DO NOTHING;

-- ---- Seed discussion topics ----
INSERT INTO discussion_topics (topic) VALUES
 ('What problem does Zelion solve better than traditional ESG reporting systems?'),
 ('How can hardware verification improve trust in renewable energy data?'),
 ('Which DePIN use case for Zelion excites you most, and why?'),
 ('Why is AI / data-center energy demand becoming so important for verification?'),
 ('Why anchor trust in a physical device instead of software oracles?'),
 ('How could tamper-resistant energy proof change carbon credit markets?'),
 ('What makes the 3-layer Zelion architecture resilient to failure?'),
 ('How does source-level capture help with CSRD / SEC climate disclosure?'),
 ('What role does the ZLN coordination protocol play in the network?'),
 ('Why is BNB Chain a good fit for Zelion''s coordination & record layer?'),
 ('How can RWA tokenization benefit from hardware-attested energy data?'),
 ('What kind of enterprise would adopt ZEV devices first, and why?')
ON CONFLICT (topic) DO NOTHING;
