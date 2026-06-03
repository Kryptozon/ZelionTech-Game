-- ============================================================
-- Phase 2 migration — social auto-verify, group activity, events
-- Idempotent. Runs after init.sql on every startup.
-- ============================================================

-- The two Telegram missions can be auto-verified via getChatMember.
UPDATE missions SET verification='auto' WHERE code IN ('social_telegram_official','social_telegram_global');

-- Group activity (messages + reactions) for rewards / anti-cheat audit.
CREATE TABLE IF NOT EXISTS group_activity (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT REFERENCES users(id) ON DELETE CASCADE,
    chat_id    BIGINT,
    kind       TEXT,                              -- message | reaction
    scored     BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_group_activity_user_day ON group_activity(user_id, created_at);

-- Events log (surge hours, weekly resets, announcements).
CREATE TABLE IF NOT EXISTS events (
    id         BIGSERIAL PRIMARY KEY,
    kind       TEXT,                              -- surge | weekly_reset | announce
    detail     JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
