-- ============================================================
-- Phase 17 migration — manual puzzle release + walkthrough/tiktok. Idempotent.
-- ============================================================
ALTER TABLE puzzles        ADD COLUMN IF NOT EXISTS walkthrough   TEXT;
ALTER TABLE puzzle_scripts ADD COLUMN IF NOT EXISTS tiktok_script TEXT;

-- Backfill so the admin dashboard has content without re-seeding.
UPDATE puzzles SET walkthrough = explanation WHERE walkthrough IS NULL;
UPDATE puzzle_scripts SET tiktok_script = youtube_script WHERE tiktok_script IS NULL;

-- Key/value game settings (active puzzle pointer + editable rewards/multipliers).
-- The daily puzzle shown to users is driven by the 'active_puzzle' pointer below
-- (set only by an admin) — puzzles NEVER auto-release.
CREATE TABLE IF NOT EXISTS game_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
