import React, { useState } from 'react'
import { api } from '../api'
import { Card, Btn, Stat, Progress } from '../ui'
import { hapticOk, hapticErr } from '../telegram'

export default function Home({ me, refresh, flash, go }) {
  const [busy, setBusy] = useState(false)

  const claim = async () => {
    setBusy(true)
    try {
      const r = await api.claim()
      if (r.status === 'cooldown') {
        const h = Math.floor(r.seconds / 3600), m = Math.floor((r.seconds % 3600) / 60)
        flash(`Next charge in ${h}h ${m}m`, 'red'); hapticErr()
      } else {
        const surge = r.award?.multiplier > 1 ? ` ⚡x${r.award.multiplier}` : ''
        flash(`+${r.energy}⚡ +${r.xp}💎  Day ${r.streak}${surge}`); hapticOk()
        await refresh()
      }
    } catch (e) { flash(e.message, 'red') } finally { setBusy(false) }
  }

  return (
    <div className="space-y-4">
      <Card className="glow">
        <div className="flex justify-between items-center">
          <div>
            <div className="label">Rank</div>
            <div className="text-xl font-extrabold text-gold">{me.rank}</div>
            <div className="text-xs text-white/50">Level {me.level}</div>
          </div>
          <div className="text-right">
            <div className="label">Points</div>
            <div className="text-2xl font-black">{me.points}💎</div>
          </div>
        </div>
        {me.next_threshold && (
          <div className="mt-3">
            <Progress value={me.points} max={me.next_threshold} />
            <div className="text-[11px] text-white/40 mt-1">{me.points}/{me.next_threshold} to next rank</div>
          </div>
        )}
      </Card>

      <Card>
        <div className="flex">
          <Stat label="Energy" value={`${me.energy}/${me.energy_cap}`} accent />
          <Stat label="Streak" value={`${me.streak}🔥`} />
          <Stat label="Level" value={me.level} />
        </div>
        <Btn gold className="w-full mt-4" disabled={busy} onClick={claim}>
          {busy ? '…' : '⚡ Claim Daily Energy'}
        </Btn>
      </Card>

      <div className="grid grid-cols-2 gap-3">
        <Tile icon="🧠" title="Play Quiz" sub="Earn XP on ZelionTech" onClick={() => go('quiz')} />
        <Tile icon="🎯" title="Missions" sub="Follow & earn" onClick={() => go('missions')} />
        <Tile icon="🏆" title="Leaderboard" sub="Climb the ranks" onClick={() => go('ranks')} />
        <Tile icon="👥" title="Invite" sub="Recruit operators" onClick={() => go('profile')} />
      </div>
    </div>
  )
}

const Tile = ({ icon, title, sub, onClick }) => (
  <button onClick={onClick} className="card text-left active:scale-[0.98] transition">
    <div className="text-2xl">{icon}</div>
    <div className="font-bold mt-1">{title}</div>
    <div className="text-[11px] text-white/45">{sub}</div>
  </button>
)
