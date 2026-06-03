-- ============================================================
-- Phase 3 migration — shadow-ban + analytics
-- Idempotent.
-- ============================================================

-- Shadow-ban: user keeps playing but earns 0 real points (silent penalty).
ALTER TABLE users ADD COLUMN IF NOT EXISTS shadow_banned BOOLEAN DEFAULT FALSE;

-- Analytics event stream.
CREATE TABLE IF NOT EXISTS analytics_events (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT,
    event      TEXT,
    props      JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_analytics_event_time ON analytics_events(event, created_at);
CREATE INDEX IF NOT EXISTS idx_analytics_user ON analytics_events(user_id, created_at);
