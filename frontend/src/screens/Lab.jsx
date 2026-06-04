import React, { useEffect, useState } from 'react'
import { api } from '../api'
import { Card, Btn, Chip, Spinner, Progress } from '../ui'
import { hapticOk } from '../telegram'

export default function Lab({ refresh, flash }) {
  const [data, setData] = useState(null)
  const [missions, setMissions] = useState([])
  const [stats, setStats] = useState(null)   // live tap stats (per-tap, max energy, recharge)

  const load = async () => {
    try {
      setData(await api.upgrades())
      setMissions((await api.tapMissions()).missions)
      setStats(await api.tapState())          // refresh tap stats so effects show instantly
    } catch (e) { flash(e.message, 'red') }
  }
  useEffect(() => { load() }, [])

  const buy = async (code) => {
    try {
      const r = await api.buyUpgrade(code)
      if (r.error) { flash(r.error.replace('_', ' '), 'red'); return }
      flash(`✅ Upgraded! -${r.spent} ZLN-XP`); hapticOk(); refresh(); load()
    } catch (e) { flash(e.message, 'red') }
  }

  const claimMission = async (id) => {
    try {
      const r = await api.claimTapMission(id)
      if (r.error) { flash(r.error.replace('_', ' '), 'red'); return }
      flash(`🎁 +${r.reward} ZLN-XP`); refresh(); load()
    } catch (e) { flash(e.message, 'red') }
  }

  if (!data) return <Spinner />

  return (
    <div className="space-y-4">
      <Card className="text-center">
        <div className="label">Reactor Lab — your balance</div>
        <div className="text-2xl font-black text-gold">{data.zp.toLocaleString()} ZLN-XP</div>
        {stats && (
          <div className="flex justify-center gap-4 mt-2 text-[11px] text-white/55">
            <span>⚡ <b className="text-gold">+{stats.points_per_tap}</b>/tap</span>
            <span>🔋 max <b>{stats.max_energy}</b></span>
            <span>☀️ <b>+{stats.recharge_rate}</b>/s</span>
          </div>
        )}
      </Card>

      <div className="label">⚙️ Upgrades</div>
      {data.upgrades.map((u) => (
        <Card key={u.code}>
          <div className="flex items-center gap-3">
            <div className="text-2xl">{u.icon}</div>
            <div className="flex-1">
              <div className="font-bold">{u.name} <Chip tone="gray">Lv.{u.level}</Chip></div>
              <div className="text-[11px] text-white/45">{u.description}</div>
            </div>
            {u.maxed
              ? <Chip tone="green">MAX</Chip>
              : <Btn gold={u.affordable} disabled={!u.affordable} onClick={() => buy(u.code)}>
                  {u.next_cost.toLocaleString()} ZLN-XP
                </Btn>}
          </div>
          {!u.maxed && <div className="mt-2"><Progress value={u.level} max={u.max_level} /></div>}
        </Card>
      ))}

      <div className="label pt-2">🎯 Tasks</div>
      {missions.map((m) => (
        <Card key={m.id}>
          <div className="flex items-center gap-3">
            <div className="text-xl">{m.icon}</div>
            <div className="flex-1">
              <div className="font-semibold text-sm">{m.title}</div>
              <Progress value={m.progress} max={m.goal} />
              <div className="text-[11px] text-white/40 mt-1">{m.progress}/{m.goal} · +{m.reward} ZLN-XP</div>
            </div>
            {m.claimed
              ? <Chip tone="green">✓</Chip>
              : <Btn gold={m.done} disabled={!m.done} onClick={() => claimMission(m.id)}>Claim</Btn>}
          </div>
        </Card>
      ))}
    </div>
  )
}
