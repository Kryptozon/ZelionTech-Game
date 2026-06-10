-- ============================================================
-- Phase 19 migration — separate Ranking XP from Game XP. Idempotent.
--   users.points     = Game XP / ZLN-XP (spendable, in-game)
--   users.ranking_xp = Ranking XP (leaderboard position only)
-- ============================================================
ALTER TABLE users ADD COLUMN IF NOT EXISTS ranking_xp BIGINT DEFAULT 0;

-- One-time backfill: start ranking_xp equal to game XP so the leaderboard is
-- unchanged at first. Guarded by a flag so reboots NEVER overwrite later admin
-- ranking adjustments (game_settings exists from migration 017).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM game_settings WHERE key = 'ranking_xp_backfilled') THEN
        UPDATE users SET ranking_xp = points;
        INSERT INTO game_settings(key, value) VALUES ('ranking_xp_backfilled', '1')
            ON CONFLICT (key) DO NOTHING;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_users_ranking_xp ON users(ranking_xp DESC);
