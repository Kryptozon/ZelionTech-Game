-- ============================================================
-- Phase 20 migration — hard cap on mission/task ZLN-XP rewards. Idempotent.
-- Normal missions reward 10..500 ZLN-XP. Only tiers flagged legendary_admin_only
-- may exceed the cap (none do today).
-- ============================================================
ALTER TABLE task_definitions ADD COLUMN IF NOT EXISTS legendary_admin_only BOOLEAN DEFAULT FALSE;
-- Set when an admin edits a reward in the dashboard, so the boot re-seed won't overwrite it.
ALTER TABLE task_definitions ADD COLUMN IF NOT EXISTS admin_overridden BOOLEAN DEFAULT FALSE;

-- Clamp every existing NORMAL task reward down to the 500 cap (e.g. old 7,500 / 50,000 tiers).
UPDATE task_definitions
   SET reward = LEAST(reward, 500)
 WHERE COALESCE(legendary_admin_only, FALSE) = FALSE
   AND reward > 500;

-- Safety net for the other reward-bearing tables (already low, clamp defensively).
UPDATE tap_missions   SET reward    = LEAST(reward, 500)    WHERE reward    > 500;
UPDATE group_missions SET reward    = LEAST(reward, 500)    WHERE reward    > 500;
UPDATE missions       SET xp_reward = LEAST(xp_reward, 500) WHERE xp_reward > 500;
