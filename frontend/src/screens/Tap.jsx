import React, { useEffect, useRef, useState, useCallback } from 'react'
import { api } from '../api'
import { Card, Btn, Progress, Logo, Spinner } from '../ui'
import { hapticTap, hapticOk } from '../telegram'

let floatId = 0
function fmt(s) { s = Math.max(0, s | 0); return `${Math.floor(s / 60)}m ${s % 60}s` }

export default function Tap({ me, refresh, flash, go }) {
  const [st, setSt] = useState(null)
  const [floats, setFloats] = useState([])
  const [combo, setCombo] = useState(0)
  const [surge, setSurge] = useState(false)
  const [capModal, setCapModal] = useState(false)
  const energy = useRef(0)
  const buffer = useRef(0)
  const flushing = useRef(false)
  const wrapRef = useRef(null)

  const load = useCallback(async () => {
    const s = await api.tapState(); setSt(s); energy.current = s.energy
  }, [])
  useEffect(() => { load() }, [load])

  // local ticks: energy regen + cooldown countdown (visual)
  useEffect(() => {
    const t = setInterval(() => {
      setSt((s) => {
        if (!s) return s
        const e = Math.min(s.max_energy, energy.current + s.recharge_rate)
        energy.current = e
        const cd = Math.max(0, (s.cooldown_seconds || 0) - 1)
        const hr = Math.max(0, (s.hourly_reset_seconds || 0) - 1)
        return { ...s, energy: e, cooldown_seconds: cd, hourly_reset_seconds: hr }
      })
    }, 1000)
    return () => clearInterval(t)
  }, [])

  const flush = useCallback(async () => {
    if (flushing.current || buffer.current <= 0) return
    flushing.current = true
    const taps = buffer.current; buffer.current = 0
    const nonce = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    try {
      const r = await api.tap(taps, nonce)
      energy.current = r.energy
      setSt((s) => ({ ...s, ...r }))
      if (r.hourly_cap_reached) setCapModal(true)
      if (r.message && (r.cooldown_seconds > 0)) { setSurge(false) }
      refresh()
    } catch (e) { /* keep playing */ } finally {
      flushing.current = false
      if (buffer.current > 0) flush()
    }
  }, [refresh])

  useEffect(() => { const t = setInterval(flush, 350); return () => clearInterval(t) }, [flush])

  const overheated = (st?.cooldown_seconds || 0) > 0 || (st?.overheat_percent || 0) >= 100

  const onTap = (e) => {
    if (!st) return
    // Still allow taps when capped/overheated/empty — animation only (server returns 0).
    if (energy.current > 0 && !overheated && (st.hourly_taps_remaining > 0)) {
      energy.current = Math.max(0, energy.current - 1)
      setSt((s) => ({ ...s, energy: energy.current }))
    }
    buffer.current += 1
    setCombo((c) => c + 1)
    hapticTap()
    const rect = wrapRef.current?.getBoundingClientRect()
    const pt = e.touches?.[0] || e
    const x = rect ? pt.clientX - rect.left : 140
    const y = rect ? pt.clientY - rect.top : 140
    const id = ++floatId
    const v = (overheated || st.hourly_taps_remaining <= 0 || energy.current <= 0) ? 0 : st.points_per_tap
    setFloats((f) => [...f, { id, x, y, v }])
    setTimeout(() => setFloats((f) => f.filter((z) => z.id !== id)), 850)
  }

  if (!st) return <Spinner />

  const lvlSpan = Math.max(1, (st.next_level_xp || 0) - (st.level_xp_floor || 0))
  const lvlInto = Math.max(0, (st.zp || 0) - (st.level_xp_floor || 0))

  return (
    <div className={`space-y-4 ${surge ? 'surge-flash rounded-2xl' : ''}`}>
      <Card className="flex items-center justify-between">
        <div>
          <div className="label">Verified Energy</div>
          <div className="text-2xl font-black text-gold">{(st.zp ?? 0).toLocaleString()} ZLN-XP</div>
        </div>
        <div className="text-right">
          <div className="label">Per tap</div>
          <div className="font-bold">+{st.points_per_tap} ⚡</div>
        </div>
      </Card>

      {/* Level progress */}
      <Card>
        <div className="flex justify-between text-sm mb-1">
          <span className="text-white/60">🏅 {st.rank} · Lv.{st.level}</span>
          <span className="text-white/50 text-xs">{st.zp}/{st.next_level_xp} to Lv.{st.level + 1}</span>
        </div>
        <Progress value={lvlInto} max={lvlSpan} />
      </Card>

      {/* Hourly reactor capacity + overheat */}
      <div className="grid grid-cols-2 gap-3">
        <Card>
          <div className="label">Hourly Reactor Capacity</div>
          <div className="text-lg font-extrabold text-gold">
            {st.hourly_taps_remaining}<span className="text-white/40 text-xs">/{st.hourly_tap_limit}</span>
          </div>
          {st.hourly_taps_remaining <= 0 && (
            <div className="text-[11px] text-rose-300 mt-0.5">Refill in {fmt(st.hourly_reset_seconds)}</div>
          )}
        </Card>
        <Card>
          <div className="label">Reactor heat</div>
          <div className="h-2 rounded-full bg-white/10 overflow-hidden mt-2">
            <div className="h-full" style={{ width: `${st.overheat_percent || 0}%`,
              background: (st.overheat_percent || 0) > 70 ? '#f43f5e' : '#f5c542' }} />
          </div>
          <div className="text-[11px] text-white/40 mt-1">{st.overheat_percent || 0}%</div>
        </Card>
      </div>

      {overheated && (
        <Card className="text-center fade-in" style={{ borderColor: 'rgba(244,63,94,0.5)' }}>
          <div className="font-extrabold text-rose-400">⚠ Reactor Overheating</div>
          <div className="text-sm text-white/60">Cooling cycle engaged — {fmt(st.cooldown_seconds)} left.</div>
        </Card>
      )}
      {!overheated && st.fatigue_stage > 0 && (
        <div className="text-center text-[12px] text-amber-300">
          🔥 Reactor warming — rewards at {Math.round((st.fatigue_multiplier || 1) * 100)}%. Slow down to cool.
        </div>
      )}

      {/* Reactor button */}
      <div ref={wrapRef} className="relative mx-auto" style={{ width: 280, height: 280 }}>
        <div className="energy-aura" />
        <div className="energy-aura-2" />
        <div className="reactor-ring reactor-pulse" />
        <button onPointerDown={onTap}
          className="reactor-core absolute inset-6 rounded-full flex items-center justify-center"
          style={{ background: 'radial-gradient(circle at 50% 35%, #1b1b27, #0b0b12 70%)',
                   border: '2px solid rgba(245,197,66,0.5)', opacity: overheated ? 0.6 : 1 }}>
          <span className="logo-glow"><Logo size={150} /></span>
          <span className="tap-wave" key={combo} />
        </button>
        {floats.map((f) => (
          <span key={f.id} className="float-zp" style={{ left: f.x, top: f.y }}>{f.v > 0 ? `+${f.v}` : '0'}</span>
        ))}
      </div>

      <Card>
        <div className="flex justify-between text-sm mb-1">
          <span className="text-white/60">⚡ Reactor Energy</span>
          <span className="font-bold">{st.energy}/{st.max_energy}</span>
        </div>
        <Progress value={st.energy} max={st.max_energy} />
        <div className="text-[11px] text-white/40 mt-1">+{st.recharge_rate}/s · {st.energy_per_tap} energy/tap</div>
      </Card>

      {st.passive_rate > 0 && (
        <Card className="flex items-center justify-between">
          <div>
            <div className="font-bold">🛰️ Validator Yield</div>
            <div className="text-xs text-white/50">{st.passive_rate} ZLN-XP/h · max {st.passive_cap_hours}h</div>
          </div>
          <Btn gold disabled={st.passive_pending <= 0} onClick={async () => {
            try { const r = await api.claimPassive(); if (r.claimed) { flash(`🛰️ +${r.claimed} ZLN-XP`); refresh(); load() } else flash('Nothing to claim', 'red') }
            catch (e) { flash(e.message, 'red') }
          }}>Claim {st.passive_pending > 0 ? `+${st.passive_pending}` : ''}</Btn>
        </Card>
      )}

      <div className="text-center text-[12px] text-white/45">
        💡 Earn more by completing <b className="text-gold">quizzes, puzzles & missions</b>.
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Btn onClick={() => go('lab')}>🛠 Reactor Lab</Btn>
        <Btn onClick={() => go('tasks')}>🎯 Missions</Btn>
      </div>

      {capModal && (
        <div onClick={() => setCapModal(false)}
          className="fixed inset-0 z-50 bg-black/85 flex items-center justify-center p-6 fade-in">
          <div onClick={(e) => e.stopPropagation()} className="card max-w-sm w-full text-center">
            <Logo size={48} />
            <div className="font-extrabold text-gold text-lg mt-2">Reactor capacity depleted</div>
            <div className="text-sm text-white/70 mt-1">
              Next refill in: <b className="text-gold">{fmt(st.hourly_reset_seconds)}</b>
            </div>
            <div className="text-sm text-white/60 mt-2">
              Meanwhile, earn ZLN-XP via quizzes, puzzles, missions and community tasks.
            </div>
            <Btn gold className="w-full mt-4" onClick={() => setCapModal(false)}>Got it</Btn>
          </div>
        </div>
      )}
    </div>
  )
}
