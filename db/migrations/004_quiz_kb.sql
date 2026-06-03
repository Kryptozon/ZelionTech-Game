-- ============================================================
-- Phase 4 migration — ZelionTech knowledge base + AI quiz
-- Idempotent.
-- ============================================================

CREATE TABLE IF NOT EXISTS knowledge_pages (
    id           BIGSERIAL PRIMARY KEY,
    url          TEXT UNIQUE NOT NULL,
    title        TEXT,
    fetched_at   TIMESTAMPTZ DEFAULT now(),
    last_updated TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id          BIGSERIAL PRIMARY KEY,
    page_id     BIGINT REFERENCES knowledge_pages(id) ON DELETE CASCADE,
    chunk_index INT,
    content     TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chunks_page ON knowledge_chunks(page_id);

CREATE TABLE IF NOT EXISTS quiz_questions (
    id            BIGSERIAL PRIMARY KEY,
    question      TEXT NOT NULL,
    options       JSONB NOT NULL,          -- ["a","b","c","d"]
    correct_index INT NOT NULL,
    explanation   TEXT,
    difficulty    INT DEFAULT 1,           -- 1..5
    source_url    TEXT NOT NULL,           -- safety rule: every Q cites zeliontech.com
    chunk_id      BIGINT REFERENCES knowledge_chunks(id) ON DELETE SET NULL,
    status        TEXT DEFAULT 'pending',  -- pending | approved | rejected | disabled
    created_by    TEXT DEFAULT 'ai',       -- ai | admin
    times_asked   INT DEFAULT 0,
    created_at    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_quiz_status_diff ON quiz_questions(status, difficulty);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(id) ON DELETE CASCADE,
    question_id BIGINT REFERENCES quiz_questions(id) ON DELETE CASCADE,
    chosen_index INT,
    correct     BOOLEAN,
    awarded     INT DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_attempts_user ON quiz_attempts(user_id, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_attempt_user_question ON quiz_attempts(user_id, question_id);
