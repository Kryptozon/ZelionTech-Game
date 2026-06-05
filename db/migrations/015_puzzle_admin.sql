-- ============================================================
-- Phase 15 migration — puzzle admin control center fields. Idempotent.
-- ============================================================
ALTER TABLE puzzles ADD COLUMN IF NOT EXISTS accepted_variations TEXT;     -- comma-separated extra answers
ALTER TABLE puzzles ADD COLUMN IF NOT EXISTS source_topic        TEXT;
ALTER TABLE puzzles ADD COLUMN IF NOT EXISTS status              TEXT DEFAULT 'active';  -- active|closed|skipped
ALTER TABLE puzzles ADD COLUMN IF NOT EXISTS youtube_posted      BOOLEAN DEFAULT FALSE;
ALTER TABLE puzzles ADD COLUMN IF NOT EXISTS telegram_posted     BOOLEAN DEFAULT FALSE;
ALTER TABLE puzzles ADD COLUMN IF NOT EXISTS released_hints      INT DEFAULT 0;          -- 0..3 hints revealed in-app

-- Backfill existing puzzles so the admin dashboard has full data.
UPDATE puzzles SET source_topic = category WHERE source_topic IS NULL;
UPDATE puzzles SET accepted_variations = lower(answer) WHERE accepted_variations IS NULL;
UPDATE puzzles SET status = 'active' WHERE status IS NULL;
