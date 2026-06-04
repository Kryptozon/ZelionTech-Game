-- ============================================================
-- Phase 14 migration — progressive / infinite task chains. Idempotent.
-- ============================================================
CREATE TABLE IF NOT EXISTS task_chains (
    id          SERIAL PRIMARY KEY,
    code        TEXT UNIQUE,
    name        TEXT,
    category    TEXT,
    icon        TEXT,
    sequential  BOOLEAN DEFAULT TRUE,    -- tiers unlock one after another
    prestige    BOOLEAN DEFAULT FALSE,   -- auto-generate harder tiers when finished
    period      TEXT DEFAULT 'permanent',-- permanent | daily | weekly | seasonal
    hidden      BOOLEAN DEFAULT FALSE,
    active      BOOLEAN DEFAULT TRUE,
    sort        INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS task_definitions (
    id         BIGSERIAL PRIMARY KEY,
    chain_id   INT REFERENCES task_chains(id) ON DELETE CASCADE,
    tier_index INT,
    title      TEXT,
    metric     TEXT,                     -- taps | surge | reactor_core | messages | quiz_correct |
                                         -- puzzles | referrals | level | social_*
    goal       BIGINT,
    reward     INT,
    tier_name  TEXT,                     -- Bronze..Reactor Oracle
    badge      TEXT,
    active     BOOLEAN DEFAULT TRUE,
    UNIQUE(chain_id, tier_index)
);
CREATE INDEX IF NOT EXISTS idx_taskdef_chain ON task_definitions(chain_id, tier_index);

CREATE TABLE IF NOT EXISTS task_claims (
    user_id    BIGINT REFERENCES users(id) ON DELETE CASCADE,
    task_id    BIGINT REFERENCES task_definitions(id) ON DELETE CASCADE,
    reward     INT,
    claimed_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, task_id)
);

-- Optional cache + unlock log (progress is computed live; these support analytics).
CREATE TABLE IF NOT EXISTS user_task_progress (
    user_id    BIGINT REFERENCES users(id) ON DELETE CASCADE,
    metric     TEXT,
    value      BIGINT DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, metric)
);
CREATE TABLE IF NOT EXISTS user_task_unlocks (
    user_id     BIGINT REFERENCES users(id) ON DELETE CASCADE,
    task_id     BIGINT REFERENCES task_definitions(id) ON DELETE CASCADE,
    unlocked_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, task_id)
);

CREATE TABLE IF NOT EXISTS achievement_tiers (
    name  TEXT PRIMARY KEY,
    rank  INT,
    color TEXT,
    icon  TEXT
);
INSERT INTO achievement_tiers (name, rank, color, icon) VALUES
 ('Bronze', 1, '#cd7f32', '🥉'),
 ('Silver', 2, '#c0c0c0', '🥈'),
 ('Gold', 3, '#f5c542', '🥇'),
 ('Platinum', 4, '#7fd6e0', '💠'),
 ('Diamond', 5, '#8ad4ff', '💎'),
 ('Reactor Elite', 6, '#a78bfa', '🛡️'),
 ('Reactor Legend', 7, '#fb7185', '🔥'),
 ('Reactor Oracle', 8, '#ffd700', '🔮')
ON CONFLICT (name) DO NOTHING;
