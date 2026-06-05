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
              <div>
                <div className="font-semibold">{r.name}</div>
                {(r.level != null || r.rank) && (
                  <div className="text-[11px] text-white/40">
                    {r.rank || ''}{r.level != null ? ` · Lv.${r.level}` : ''}
                  </div>
                )}
              </div>
            </div>
            <span className="text-gold font-bold">{(r.score ?? 0).toLocaleString()} ZLN-XP</span>
          </div>
        ))}
      </Card>

      <Card className="text-center">
        <div className="label">Your standing</div>
        <div className="font-bold mt-1">
          All-time #{data.my_rank || '—'} · This week {data.my_week || 0} ZLN-XP
        </div>
        {(data.my_rank_name || data.my_level != null) && (
          <div className="text-xs text-white/50 mt-1">
            {data.my_rank_name || ''}{data.my_level != null ? ` · Level ${data.my_level}` : ''}
          </div>
        )}
      </Card>
    </div>
  )
}
