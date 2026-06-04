import React, { useEffect, useState } from 'react'
import { api } from '../api'
import { Card, Btn, Chip, Spinner, Progress, Logo } from '../ui'
import { tg } from '../telegram'

const EMPTY = {
  discussion: null, missions: [], top_today: [], top_week: [], top_month: [],
  score: { today: 0, messages: 0, replies: 0, reactions: 0, discussion: 0, days_week: 0 },
  surge_multiplier: 1, group_link: null,
}

export default function Community({ refresh, flash }) {
  const [d, setD] = useState(null)
  const [board, setBoard] = useState('today')

  // Never surface technical errors — fall back to a warming-up empty state.
  const load = async () => {
    try { setD(await api.community()) } catch (e) { setD(EMPTY) }
  }
  useEffect(() => { load() }, [])

  const claim = async (id) => {
    try {
      const r = await api.claimGroupMission(id)
      if (r.error) { flash(r.error.replace(/_/g, ' '), 'red'); return }
      flash(`🎁 +${r.reward} ZLN-XP`); refresh(); load()
    } catch (e) { flash(e.message, 'red') }
  }

  const openGroup = () => {
    if (d?.group_link && tg?.openTelegramLink) tg.openTelegramLink(d.group_link)
    else if (d?.group_link) window.open(d.group_link, '_blank')
    else flash('Group link unavailable', 'red')
  }

  if (!d) return <Spinner />
  const rows = board === 'today' ? d.top_today : board === 'week' ? d.top_week : (d.top_month || [])
  const medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']

  return (
    <div className="space-y-4">
      <Card className="flex items-center gap-3">
        <Logo size={34} />
        <div className="flex-1">
          <div className="font-extrabold">Zelion Community</div>
          <div className="text-[11px] text-white/45">Talk, reply, react — earn ZLN-XP daily</div>
        </div>
        <Btn gold onClick={openGroup}>Open Group</Btn>
      </Card>

      {d.surge_multiplier > 1 && (
        <Card className="glow text-center">
          <div className="font-extrabold text-gold">⚡ POWER SURGE ACTIVE — x{d.surge_multiplier} ZLN-XP!</div>
          <div className="text-[11px] text-white/50">All group activity earns more right now.</div>
        </Card>
      )}

      <Card>
        <div className="label">🗣️ Daily Discussion</div>
        {d.discussion ? (
          <>
            <div className="text-sm mt-1">{d.discussion.topic}</div>
            <div className="text-[11px] text-white/40 mt-1">{d.discussion.replies} replies · reply in the group to earn</div>
          </>
        ) : <div className="text-sm text-white/50 mt-1">Today's topic will post soon. Stay tuned!</div>}
      </Card>

      <Card>
        <div className="label">📈 Your contribution today</div>
        <div className="flex mt-1">
          <Stat v={d.score.messages} l="Messages" />
          <Stat v={d.score.replies} l="Replies" />
          <Stat v={d.score.reactions} l="Reactions" />
          <Stat v={d.score.today} l="Score" gold />
        </div>
      </Card>

      <div className="label">🎯 Group Missions</div>
      {d.missions.length === 0 && (
        <Card className="text-center text-white/40 text-sm">Community warming up — missions appear once activity starts.</Card>
      )}
      {d.missions.map((m) => (
        <Card key={m.id}>
          <div className="flex items-center gap-3">
            <div className="text-xl">{m.icon}</div>
            <div className="flex-1">
              <div className="font-semibold text-sm">{m.title} <Chip tone="gray">{m.period}</Chip></div>
              <Progress value={m.progress} max={m.goal} />
              <div className="text-[11px] text-white/40 mt-1">{m.progress}/{m.goal} · +{m.reward} ZLN-XP</div>
            </div>
            {m.claimed ? <Chip tone="green">✓</Chip>
              : <Btn gold={m.done} disabled={!m.done} onClick={() => claim(m.id)}>Claim</Btn>}
          </div>
        </Card>
      ))}

      <div className="label">🏆 Top Contributors</div>
      <div className="flex gap-2">
        {[['today', 'Today'], ['week', 'Week'], ['month', 'Month']].map(([id, l]) => (
          <button key={id} onClick={() => setBoard(id)}
            className={`flex-1 btn text-xs ${board === id ? 'btn-gold' : 'btn-ghost'}`}>{l}</button>
        ))}
      </div>
      <Card>
        {rows.length === 0 ? <div className="text-center text-white/40 py-4">No leaderboard data yet — be the first to contribute!</div>
          : rows.map((r, i) => (
            <div key={i} className="flex justify-between py-1.5 border-b border-white/5 last:border-0">
              <span>{medals[i] || `${i + 1}.`} {r.name}</span>
              <span className="text-gold font-bold">{r.score} pts</span>
            </div>
          ))}
      </Card>
    </div>
  )
}

const Stat = ({ v, l, gold }) => (
  <div className="flex-1 text-center">
    <div className={`text-lg font-extrabold ${gold ? 'text-gold' : ''}`}>{v}</div>
    <div className="text-[10px] uppercase tracking-wide text-white/40">{l}</div>
  </div>
)
