import React, { useEffect, useState } from 'react'
import { api } from '../api'
import { Card, Spinner, Logo } from '../ui'

export default function Leaderboard() {
  const [data, setData] = useState(null)
  const [tab, setTab] = useState('weekly')
  useEffect(() => { api.leaderboard().then(setData).catch(() => {}) }, [])
  if (!data) return <Spinner />

  const rows = data[tab] || []
  const medal = (i) => ['🥇', '🥈', '🥉'][i] || `${i + 1}.`

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-center gap-2 py-1">
        <Logo size={30} />
        <div className="font-extrabold tracking-wide">ZELION <span className="text-gold">LEADERBOARD</span></div>
      </div>
      <div className="flex gap-2">
        {['weekly', 'alltime'].map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`flex-1 btn ${tab === t ? 'btn-gold' : 'btn-ghost'}`}>
            {t === 'weekly' ? '📅 Weekly' : '⭐ All-time'}
          </button>
        ))}
      </div>

      <Card>
        {rows.length === 0 && <div className="text-center text-white/40 py-6">No operators yet — be first! ⚡</div>}
        {rows.map((r, i) => (
          <div key={i} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
            <div className="flex items-center gap-3">
              <span className="w-7 text-center">{medal(i)}</span>
              <span className="font-semibold">{r.name}</span>
            </div>
            <span className="text-gold font-bold">{r.score}💎</span>
          </div>
        ))}
      </Card>

      <Card className="text-center">
        <div className="label">Your standing</div>
        <div className="font-bold mt-1">
          All-time #{data.my_rank || '—'} · This week {data.my_week || 0}💎
        </div>
      </Card>
    </div>
  )
}
