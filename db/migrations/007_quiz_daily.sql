-- ============================================================
-- Phase 7 migration — daily quiz sessions, seeded question bank, generation logs
-- Idempotent. Extends existing quiz_questions (keeps options JSONB + correct_index).
-- ============================================================

-- Extra columns required by the daily-quiz system.
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS source_section TEXT;
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS reward         INT;
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS active         BOOLEAN DEFAULT TRUE;
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS slug           TEXT;   -- unique hash for idempotent seeding
-- Full unique index (Postgres allows multiple NULLs) so ON CONFLICT (slug) works.
CREATE UNIQUE INDEX IF NOT EXISTS uq_quiz_slug ON quiz_questions(slug);

-- Backfill reward from difficulty for any pre-existing rows.
UPDATE quiz_questions
   SET reward = CASE difficulty WHEN 1 THEN 5 WHEN 2 THEN 10 WHEN 3 THEN 20 ELSE 35 END
 WHERE reward IS NULL;

-- 5-question rolling-24h session per user.
CREATE TABLE IF NOT EXISTS daily_quiz_sessions (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT REFERENCES users(id) ON DELETE CASCADE,
    session_date    DATE DEFAULT CURRENT_DATE,
    question_ids    JSONB NOT NULL,
    completed_count INT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now(),
    expires_at      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_dqs_user_active ON daily_quiz_sessions(user_id, expires_at);

-- Generation/seed audit.
CREATE TABLE IF NOT EXISTS question_generation_logs (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT,            -- curated | kb_generated | website | ai
    count_generated INT,
    status          TEXT,            -- ok | error
    detail          TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_quiz_active_diff ON quiz_questions(active, status, difficulty);
