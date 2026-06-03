-- ============================================================
-- Phase 6 migration — tap-to-earn reactor game + proof delivery fix
-- Idempotent.
-- ============================================================

-- Per-user reactor/tap state (energy is the tap resource; ZP = users.points ledger).
CREATE TABLE IF NOT EXISTS tap_state (
    user_id                 BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    energy_balance          INT DEFAULT 1000,
    last_energy_ts          TIMESTAMPTZ DEFAULT now(),
    last_passive_ts         TIMESTAMPTZ DEFAULT now(),
    total_taps              BIGINT DEFAULT 0,
    total_energy_generated  BIGINT DEFAULT 0,   -- lifetime ZP from taps ("Verified Energy")
    daily_taps              INT DEFAULT 0,
    daily_date              DATE DEFAULT CURRENT_DATE,
    best_combo              INT DEFAULT 0,
    created_at              TIMESTAMPTZ DEFAULT now()
);

-- Aggregated tap batches (audit / anti-cheat).
CREATE TABLE IF NOT EXISTS tap_events (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(id) ON DELETE CASCADE,
    taps        INT,
    zp          INT,
    combo       INT,
    nonce       TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tap_events_user ON tap_events(user_id, created_at);

-- Upgrade catalogue (Reactor Lab).
CREATE TABLE IF NOT EXISTS upgrades (
    code            TEXT PRIMARY KEY,
    name            TEXT,
    description     TEXT,
    stat            TEXT,            -- points_per_tap | max_energy | recharge_rate | passive_rate | combo_mult
    icon            TEXT,
    base_cost       INT,
    cost_growth     NUMERIC,         -- cost = base_cost * growth^level
    base_effect     NUMERIC,         -- effect added per level
    max_level       INT,
    sort            INT DEFAULT 0
);

-- Per-user upgrade levels.
CREATE TABLE IF NOT EXISTS user_upgrades (
    user_id    BIGINT REFERENCES users(id) ON DELETE CASCADE,
    code       TEXT REFERENCES upgrades(code),
    level      INT DEFAULT 0,
    PRIMARY KEY (user_id, code)
);

-- Passive (Validator Yield) claim log.
CREATE TABLE IF NOT EXISTS passive_rewards (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(id) ON DELETE CASCADE,
    amount      INT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Tap missions / daily tasks.
CREATE TABLE IF NOT EXISTS tap_missions (
    id          SERIAL PRIMARY KEY,
    code        TEXT UNIQUE,
    title       TEXT,
    goal_type   TEXT,        -- taps | energy | combo | upgrade | yield | quiz
    goal        BIGINT,
    reward      INT,
    icon        TEXT,
    is_active   BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS user_tap_missions (
    user_id     BIGINT REFERENCES users(id) ON DELETE CASCADE,
    mission_id  INT REFERENCES tap_missions(id) ON DELETE CASCADE,
    claimed_at  TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, mission_id)
);

-- Proof delivery fix: track reward + whether the admin actually received it.
ALTER TABLE proof_submissions ADD COLUMN IF NOT EXISTS reward    INT DEFAULT 0;
ALTER TABLE proof_submissions ADD COLUMN IF NOT EXISTS delivered BOOLEAN DEFAULT FALSE;

-- ---------------- Seed: upgrades ----------------
INSERT INTO upgrades (code, name, description, stat, icon, base_cost, cost_growth, base_effect, max_level, sort) VALUES
 ('reactor_core',   'Reactor Core',    'Increases ZP per tap.',                 'points_per_tap', '⚛️', 50,  1.6, 1,   20, 1),
 ('battery_pack',   'Battery Pack',    'Increases max Reactor Energy.',         'max_energy',     '🔋', 75,  1.6, 500, 20, 2),
 ('solar_amplifier','Solar Amplifier', 'Increases energy recharge speed.',      'recharge_rate',  '☀️', 100, 1.7, 1,   15, 3),
 ('zev_validator',  'ZEV Validator',   'Passive Validator Yield (ZP / hour).',  'passive_rate',   '🛰️', 150, 1.8, 50,  15, 4),
 ('proof_engine',   'Proof Engine',    'Boosts Power Surge & quiz multipliers.','combo_mult',     '⚡', 200, 1.9, 0.1, 10, 5)
ON CONFLICT (code) DO NOTHING;

-- ---------------- Seed: tap missions ----------------
INSERT INTO tap_missions (code, title, goal_type, goal, reward, icon) VALUES
 ('tap_100',     'Validate 100 taps',          'taps',    100,   100, '👆'),
 ('energy_500',  'Generate 500 Verified Energy','energy',  500,   150, '⚡'),
 ('combo_5',     'Reach a x5 Power Surge',      'combo',   50,    200, '🔥'),
 ('upgrade_core','Upgrade the Reactor Core',    'upgrade', 1,     250, '⚛️'),
 ('claim_yield', 'Claim Validator Yield',       'yield',   1,     120, '🛰️'),
 ('quiz_one',    'Complete a Zelion quiz',      'quiz',    1,     120, '🧠')
ON CONFLICT (code) DO NOTHING;
