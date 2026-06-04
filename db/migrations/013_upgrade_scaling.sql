-- ============================================================
-- Phase 13 migration — upgrade cost scaling (cost = base * 1.65^level)
-- + max levels per spec. Idempotent.
-- ============================================================
UPDATE upgrades SET cost_growth = 1.65;

UPDATE upgrades SET max_level = 20 WHERE code = 'reactor_core';
UPDATE upgrades SET max_level = 20 WHERE code = 'battery_pack';
UPDATE upgrades SET max_level = 15 WHERE code = 'solar_amplifier';
UPDATE upgrades SET max_level = 10 WHERE code = 'fusion_reactor';
UPDATE upgrades SET max_level = 5  WHERE code = 'quantum_reactor';
