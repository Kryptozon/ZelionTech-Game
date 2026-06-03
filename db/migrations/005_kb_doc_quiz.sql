-- ============================================================
-- Phase 5 migration — document KB, categories, question types,
-- difficulty tiers, daily challenges.  Idempotent.
-- ============================================================

-- Knowledge provenance: website vs document, plus section category.
ALTER TABLE knowledge_pages  ADD COLUMN IF NOT EXISTS source_type TEXT DEFAULT 'website';
ALTER TABLE knowledge_pages  ADD COLUMN IF NOT EXISTS category    TEXT;
ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS source_type TEXT DEFAULT 'website';
ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS category    TEXT;

-- Quiz question metadata.
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS qtype    TEXT DEFAULT 'mcq';  -- mcq|true_false|scenario|architecture|tokenomics
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS category TEXT;
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS tier     TEXT;                -- beginner|intermediate|advanced|expert
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS source_type TEXT DEFAULT 'website';

-- Deterministic daily challenge set (same questions for everyone that day).
CREATE TABLE IF NOT EXISTS daily_challenges (
    challenge_date DATE PRIMARY KEY,
    question_ids   JSONB NOT NULL,
    created_at     TIMESTAMPTZ DEFAULT now()
);

-- Index to pick questions by tier/category quickly.
CREATE INDEX IF NOT EXISTS idx_quiz_cat_tier ON quiz_questions(status, difficulty, category);
