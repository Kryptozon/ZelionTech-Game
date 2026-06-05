-- ============================================================
-- Phase 16 migration — hourly reactor capacity (replaces daily tap cap).
-- The live hourly window lives in Redis; these columns mirror it. Idempotent.
-- ============================================================
ALTER TABLE tap_state ADD COLUMN IF NOT EXISTS hourly_tap_count    INT DEFAULT 0;
ALTER TABLE tap_state ADD COLUMN IF NOT EXISTS hourly_tap_reset_at TIMESTAMPTZ;
-- (legacy daily_taps / daily_date columns are kept but no longer used for the cap.)
