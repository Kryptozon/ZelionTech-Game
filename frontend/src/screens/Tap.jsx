import React, { useEffect, useRef, useState, useCallback } from 'react'
import { api } from '../api'
import { Card, Btn, Progress, Logo, Spinner } from '../ui'
import { hapticTap, hapticOk } from '../telegram'

let floatId = 0

export default function Tap({ me, refresh, flash, go }) {
  const [st, setSt] = useState(null)
  const [floats, setFloats] = useState([])
  const [combo, setCombo] = useState(0)
  const [surge, setSurge] = useState(false)

  // optimistic local mirror; server is authoritative on each flush
  const energy = useRef(0)
  const buffer = useRef(0)
  const flushing = useRef(false)
  const wrapRef = useRef(null)

  const load = useCallback(async () => {
    const s = await api.tapState()
    setSt(s); energy.current = s.energy
  }, [])
  useEffect(() => { load() }, [load])

  // passive recharge tick (visual only; server recomputes on flush)
  useEffect(() => {
    const t = setInterval(() => {
      setSt((s) => {
        if (!s) return s
        const e = Math.min(s.max_energy, energy.current + s.recharge_rate)
        energy.current = e
        return { ...s, energy: e }
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
      setCombo(r.combo || 0)
      if (r.combo_tier === 'surge' || r.combo_tier === 'overdrive') {
        setSurge(true); setTimeout(() => setSurge(false), 500); hapticOk()
        if (r.combo_tier === 'overdrive') flash('⚡ REACTOR OVERDRIVE!')
      }
      refresh()
    } catch (e) { /* keep playing; next flush retries */ } finally {
      flushing.current = false
      if (buffer.current > 0) flush()
    }
  }, [refresh, flash])

  useEffect(() => {
    const t = setInterval(flush, 350)
    return () => clearInterval(t)
  }, [flush])

  const onTap = (e) => {
    if (!st || energy.current <= 0) return
    const ppt = st.points_per_tap || 1
    energy.current = Math.max(0, energy.current - 1)
    setSt((s) => ({ ...s, energy: energy.current, zp: (s.zp || 0) + ppt }))
    buffer.current += 1
    setCombo((c) => c + 1)
    hapticTap()

    // floating +ZLN-XP at touch point
    const rect = wrapRef.current?.getBoundingClientRect()
    const pt = e.touches?.[0] || e
    const x = rect ? (pt.clientX - rect.left) : rect.width / 2
    const y = rect ? (pt.clientY - rect.top) : rect.height / 2
    const id = ++floatId
    setFloats((f) => [...f, { id, x, y, v: ppt }])
    setTimeout(() => setFloats((f) => f.filter((z) => z.id !== id)), 850)
  }

  if (!st) return <Spinner />

  const energyPct = st.max_energy ? Math.round((st.energy / st.max_energy) * 100) : 0

  return (
    <div className={`space-y-4 ${surge ? 'surge-flash rounded-2xl' : ''}`}>
      <Card className="flex items-center justify-between">
        <div>
          <div className="label">Verified Energy Generated</div>
          <div className="text-2xl font-black text-gold">{(st.zp ?? me.points).toLocaleString()} ZLN-XP</div>
        </div>
        <div className="text-right">
          <div className="label">Per tap</div>
          <div className="font-bold">+{st.points_per_tap} ⚡</div>
        </div>
      </Card>

      {combo >= 10 && (
        <div className="text-center font-extrabold text-gold fade-in">
          ⚡ POWER SURGE x{combo} ⚡
        </div>
      )}

      {/* Reactor Core button — the real Zelion PNG with neon energy aura */}
      <div ref={wrapRef} className="relative mx-auto" style={{ width: 280, height: 280 }}>
        <div className="energy-aura" />
        <div className="energy-aura-2" />
        <div className="reactor-ring reactor-pulse" />
        <div className="reactor-ring" style={{ inset: 18, opacity: 0.5 }} />
        <button
          onPointerDown={onTap}
          className="reactor-core absolute inset-6 rounded-full flex items-center justify-center"
          style={{ background: 'radial-gradient(circle at 50% 35%, #1b1b27, #0b0b12 70%)',
                   border: '2px solid rgba(245,197,66,0.5)' }}>
          <span className="logo-glow"><Logo size={150} /></span>
          <span className="tap-wave" key={combo} />
        </button>
        {floats.map((f) => (
          <span key={f.id} className="float-zp" style={{ left: f.x, top: f.y }}>+{f.v}</span>
        ))}
      </div>

      <Card>
        <div className="flex justify-between text-sm mb-1">
          <span className="text-white/60">⚡ Reactor Energy</span>
          <span className="font-bold">{st.energy}/{st.max_energy}</span>
        </div>
        <Progress value={st.energy} max={st.max_energy} />
        <div className="text-[11px] text-white/40 mt-1">+{st.recharge_rate}/s recharge · {energyPct}%</div>
      </Card>

      <PassiveCard st={st} flash={flash} reload={load} refresh={refresh} />

      <div className="grid grid-cols-2 gap-3">
        <Btn className="text-center" onClick={() => go('lab')}>🛠 Reactor Lab</Btn>
        <Btn className="text-center" onClick={() => go('missions')}>🎯 Missions</Btn>
      </div>
      <div className="text-center text-[11px] text-white/35">🟢 ZEV Validator Active · tap to Validate Energy</div>
    </div>
  )
}

function PassiveCard({ st, flash, reload, refresh }) {
  const [busy, setBusy] = useState(false)
  if (!st.passive_rate) {
    return (
      <Card className="text-center">
        <div className="font-bold">🛰️ Validator Yield</div>
        <div className="text-xs text-white/50 mt-1">Buy <b>ZEV Validator</b> in the Reactor Lab to earn passive ZLN-XP.</div>
      </Card>
    )
  }
  const claim = async () => {
    setBusy(true)
    try {
      const r = await api.claimPassive()
      if (r.claimed) { flash(`🛰️ +${r.claimed} ZLN-XP yield claimed`); refresh(); reload() }
      else flash('Nothing to claim yet', 'red')
    } catch (e) { flash(e.message, 'red') } finally { setBusy(false) }
  }
  return (
    <Card className="flex items-center justify-between">
      <div>
        <div className="font-bold">🛰️ Validator Yield</div>
        <div className="text-xs text-white/50">{st.passive_rate} ZLN-XP/h · max {st.passive_cap_hours}h offline</div>
      </div>
      <Btn gold disabled={busy || st.passive_pending <= 0} onClick={claim}>
        Claim {st.passive_pending > 0 ? `+${st.passive_pending}` : ''}
      </Btn>
    </Card>
  )
}
