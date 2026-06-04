-- ============================================================
-- Phase 12 migration — Zelion Intelligence puzzle system. Idempotent.
-- ============================================================
CREATE TABLE IF NOT EXISTS puzzles (
    id            BIGSERIAL PRIMARY KEY,
    slug          TEXT UNIQUE,
    title         TEXT,
    question      TEXT,
    answer        TEXT,                -- normalized (uppercase, no spaces) — never sent to users
    difficulty    TEXT,                -- easy | medium | hard | legendary
    reward        INT,
    penalty       INT,
    category      TEXT,
    hint1         TEXT,
    hint2         TEXT,
    hint3         TEXT,
    source        TEXT,
    youtube_instruction  TEXT,
    telegram_instruction TEXT,
    explanation   TEXT,
    active        BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_puzzles_active_diff ON puzzles(active, difficulty);

CREATE TABLE IF NOT EXISTS puzzle_attempts (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(id) ON DELETE CASCADE,
    puzzle_id   BIGINT REFERENCES puzzles(id) ON DELETE CASCADE,
    answer_text TEXT,
    correct     BOOLEAN,
    awarded     INT DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pz_attempts_user ON puzzle_attempts(user_id, puzzle_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pz_solved ON puzzle_attempts(user_id, puzzle_id) WHERE correct;

CREATE TABLE IF NOT EXISTS daily_puzzle_sessions (
    session_date DATE PRIMARY KEY,
    puzzle_id    BIGINT REFERENCES puzzles(id),
    created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS puzzle_hints (
    puzzle_id            BIGINT PRIMARY KEY REFERENCES puzzles(id) ON DELETE CASCADE,
    daily_hint1          TEXT,
    daily_hint2          TEXT,
    daily_hint3          TEXT,
    youtube_timestamp    TEXT,
    telegram_post_text   TEXT,
    hidden_answer_placement TEXT
);

CREATE TABLE IF NOT EXISTS puzzle_scripts (
    puzzle_id      BIGINT PRIMARY KEY REFERENCES puzzles(id) ON DELETE CASCADE,
    youtube_title  TEXT,
    youtube_script TEXT,
    clue_timestamp TEXT,
    visual_clue    TEXT,
    audio_clue     TEXT,
    caption_clue   TEXT,
    cta            TEXT,
    telegram_post  TEXT
);

CREATE TABLE IF NOT EXISTS puzzle_winners (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT REFERENCES users(id) ON DELETE CASCADE,
    period     TEXT,                 -- weekly | monthly
    period_key TEXT,
    score      BIGINT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, period, period_key)
);
