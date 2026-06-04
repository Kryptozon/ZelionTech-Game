-- ============================================================
-- Phase 9 migration — extra reactor upgrades (Fusion, Quantum). Idempotent.
-- ============================================================
INSERT INTO upgrades (code, name, description, stat, icon, base_cost, cost_growth, base_effect, max_level, sort) VALUES
 ('fusion_reactor',  'Fusion Reactor',  'Massively boosts ZLN-XP per tap.',   'points_per_tap', '🌟', 1000, 1.7, 3,   10, 6),
 ('quantum_reactor', 'Quantum Reactor', 'Huge passive Validator Yield boost.','passive_rate',   '🧪', 5000, 1.9, 200, 10, 7)
ON CONFLICT (code) DO NOTHING;
