import React, { useEffect, useState } from 'react'
import { api } from '../api'
import { Card, Btn, Chip, Spinner, Progress, Logo } from '../ui'
import { hapticOk } from '../telegram'

const TIER_TONE = {
  Bronze: 'gray', Silver: 'gray', Gold: 'gold', Platinum: 'blue',
  Diamond: 'blue', 'Reactor Elite': 'gold', 'Reactor Legend': 'red', 'Reactor Oracle': 'red',
}

export default function Tasks({ refresh, flash, go }) {
  const [d, setD] = useState(null)
  const [unlock, setUnlock] = useState(null)

  const load = async () => { try { setD(await api.tasks()) } catch (e) { flash(e.message, 'red') } }
  useEffect(() => { load() }, [])

  const claim = async (t) => {
    try {
      const r = await api.claimTask(t.id)
      if (r.error) { flash(r.error.replace(/_/g, ' '), 'red'); return }
      hapticOk(); flash(`🎁 +${r.reward} ZLN-XP — ${r.tier_name}`)
      if (r.new_tier) setUnlock(r.new_tier)            // "⚡ New task unlocked!"
      refresh(); load()
    } catch (e) { flash(e.message, 'red') }
  }

  if (!d) return <Spinner />

  return (
    <div className="space-y-4">
      <Card className="flex items-center gap-3">
        <Logo size={34} />
        <div className="flex-1">
          <div className="font-extrabold">🎯 Reactor Missions</div>
          <div className="text-[11px] text-white/45">Complete tasks — harder tiers unlock forever</div>
        </div>
      </Card>

      <Card>
        <div className="flex justify-between text-sm mb-1">
          <span className="text-white/60">Total completion</span>
          <span className="font-bold text-gold">{d.completion_percent}% · {d.completed}/{d.total}</span>
        </div>
        <Progress value={d.completed} max={d.total || 1} />
      </Card>

      {d.chains.map((c) => {
        const active = c.tasks.filter((t) => t.status !== 'completed')
        const done = c.tasks.filter((t) => t.status === 'completed')
        return (
          <div key={c.code} className="space-y-2">
            <div className="label">{c.icon} {c.name}</div>
            {active.map((t) => (
              <Card key={t.id} className={t.status === 'locked' ? 'opacity-50' : ''}>
                <div className="flex items-center gap-2">
                  <Chip tone={TIER_TONE[t.tier_name] || 'gray'}>{t.tier_name}</Chip>
                  <div className="flex-1 text-sm font-semibold">{t.title}</div>
                  <Chip tone="green">+{t.reward}</Chip>
                </div>
                {t.status !== 'locked' && (
                  <div className="mt-2">
                    <Progress value={t.progress} max={t.goal} />
                    <div className="flex items-center justify-between mt-1">
                      <span className="text-[11px] text-white/40">
                        {Number(t.progress).toLocaleString()}/{Number(t.goal).toLocaleString()}
                      </span>
                      {t.status === 'claimable'
                        ? <Btn gold onClick={() => claim(t)}>Claim</Btn>
                        : <span className="text-[11px] text-white/40">in progress…</span>}
                    </div>
                  </div>
                )}
              </Card>
            ))}
            {done.length > 0 && (
              <details className="text-[11px] text-white/40">
                <summary className="cursor-pointer">✅ {done.length} completed</summary>
                {done.map((t) => (
                  <div key={t.id} className="flex justify-between py-1">
                    <span>{t.tier_name} · {t.title}</span><span className="text-emerald-400">+{t.reward}</span>
                  </div>
                ))}
              </details>
            )}
          </div>
        )
      })}

      <Btn className="w-full" onClick={() => go && go('reactor')}>⬅ Back to Reactor</Btn>

      {unlock && (
        <div onClick={() => setUnlock(null)}
          className="fixed inset-0 z-50 bg-black/85 flex items-center justify-center p-6 fade-in">
          <div onClick={(e) => e.stopPropagation()} className="card max-w-sm w-full text-center glow">
            <div className="text-4xl">🎉</div>
            <div className="font-extrabold text-gold text-lg mt-1">New Task Unlocked</div>
            <div className="text-sm text-white/70 mt-2">{unlock.title}</div>
            <div className="text-[12px] text-white/45 mt-1">Reward +{unlock.reward} ZLN-XP</div>
            <Btn gold className="w-full mt-4" onClick={() => setUnlock(null)}>Let's go</Btn>
          </div>
        </div>
      )}
    </div>
  )
}
