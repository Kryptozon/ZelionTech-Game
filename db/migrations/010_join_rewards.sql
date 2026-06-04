-- ============================================================
-- Phase 10 migration — Telegram join rewards + correct links. Idempotent.
-- ============================================================

-- Join Telegram CHANNEL (@zeliontechofficial) -> +30 ZLN-XP
UPDATE missions
   SET xp_reward = 30, url = 'https://t.me/zeliontechofficial',
       description = 'Join the official ZelionTech Telegram channel for +30 ZLN-XP.'
 WHERE code = 'social_telegram_official';

-- Join Telegram GROUP (@zelionglobal) -> +35 ZLN-XP
UPDATE missions
   SET xp_reward = 35, url = 'https://t.me/zelionglobal',
       description = 'Join the Zelion Global community group for +35 ZLN-XP.'
 WHERE code = 'social_telegram_global';
