-- ============================================================
-- Phase 11 migration — balanced tap economy (anti-farm). Idempotent.
-- Live heat/fatigue/cooldown are kept in Redis; these columns persist state.
-- ============================================================
ALTER TABLE tap_state ADD COLUMN IF NOT EXISTS daily_tap_reset_at   TIMESTAMPTZ;
ALTER TABLE tap_state ADD COLUMN IF NOT EXISTS overheat_value       INT DEFAULT 0;     -- 0..100
ALTER TABLE tap_state ADD COLUMN IF NOT EXISTS cooldown_until       TIMESTAMPTZ;
ALTER TABLE tap_state ADD COLUMN IF NOT EXISTS fatigue_stage        INT DEFAULT 0;     -- 0,1,2
ALTER TABLE tap_state ADD COLUMN IF NOT EXISTS suspicious_tap_score INT DEFAULT 0;
ALTER TABLE tap_state ADD COLUMN IF NOT EXISTS last_tap_window      BIGINT DEFAULT 0;
