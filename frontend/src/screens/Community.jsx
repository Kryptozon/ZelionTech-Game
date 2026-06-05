import React, { useEffect, useState } from 'react'
import { api } from '../api'
import { Card, Btn, Chip, Spinner, Progress, Logo } from '../ui'
import { tg } from '../telegram'

// Exact public links — hard fallbacks so the buttons are NEVER "unavailable".
const GROUP_URL = 'https://t.me/zelionglobal'
const CHANNEL_URL = 'https://t.me/zeliontechofficial'
const RULE_TEXT = 'Earn +1 ZLN-XP for every valid group message after joining Zelion Global.'

const EMPTY = {
  discussion: null, missions: [], top_today: [], top_week: [], top_month: [],
  score: { today: 0, messages: 0, replies: 0, reactions: 0, discussion: 0, days_week: 0 },
  surge_multiplier: 1, group_link: GROUP_URL, channel_link: CHANNEL_URL, msg_reward: 1,
}

function openLink(url) {
  if (tg?.openTelegramLink) tg.openTelegramLink(url)
  else window.open(url, '_blank')
}

export default function Community({ refresh, flash, go }) {
  const [d, setD] = useState(null)
  const [board, setBoard] = useState('today')
  const [showInfo, setShowInfo] = useState(false)

  const load = async () => {
    // Never surface technical errors — fall back to a warming-up empty state.
    try { setD(await api.community()) } catch (e) { setD(EMPTY) }
  }
  useEffect(() => {
    load()
    try {
      if (!localStorage.getItem('zln_comm_info_seen')) setShowInfo(true)
    } catch (_) { setShowInfo(true) }
  }, [])

  const dismissInfo = () => {
    setShowInfo(false)
    try { localStorage.setItem('zln_comm_info_seen', '1') } catch (_) {}
  }

  const claim = async (id) => {
    try {
      const r = await api.claimGroupMission(id)
      if (r.error) { flash(r.error.replace(/_/g, ' '), 'red'); return }
      flash(`🎁 +${r.reward} ZLN-XP`); refresh(); load()
    } catch (e) { flash(e.message, 'red') }
  }

  if (!d) return <Spinner />
  const groupUrl = d.group_link || GROUP_URL
  const channelUrl = d.channel_link || CHANNEL_URL
  const rows = board === 'today' ? d.top_today : board === 'week' ? d.top_week : (d.top_month || [])
  const medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']

  return (
    <div className="space-y-4">
      {go && (
        <Btn gold className="w-full" onClick={() => go('ranks')}>🏆 Ranks & Leaderboard</Btn>
      )}
      <Card className="flex items-center gap-3">
        <Logo size={34} />
        <div className="flex-1">
          <div className="font-extrabold">Zelion Community</div>
          <div className="text-[11px] text-white/45">Talk, reply, react — earn ZLN-XP daily</div>
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-3">
        <Btn gold onClick={() => openLink(groupUrl)}>💬 Open Group</Btn>
        <Btn onClick={() => openLink(channelUrl)}>📣 Open Channel</Btn>
      </div>

      {/* Always-visible "How to earn ZLN-XP" panel */}
      <Card className="glow">
        <div className="text-sm font-bold text-gold">⚡ How to earn ZLN-XP</div>
        <div className="text-[12px] text-white/70 mt-2 grid grid-cols-1 gap-1">
          <div>💬 Valid group message — <b>+1</b></div>
          <div>↩️ Reply to a member — <b>+2</b></div>
          <div>🗣️ Daily discussion answer — <b>+5</b></div>
          <div>🧠 Quiz correct — <b>+5 to +35</b> (wrong −1)</div>
          <div>🧩 Puzzle solved — <b>+20 to +250</b></div>
          <div>📡 Social: channel <b>+30</b> · group <b>+35</b> · follow <b>+50</b></div>
          <div>🎯 Reactor missions, daily claim & referrals</div>
        </div>
        <div className="text-[11px] text-white/40 mt-2">
          Valid message = min {d.msg_min_len || 10} chars · not emoji-only · no spam · max 1 / 60s · daily cap.
        </div>
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

      {/* First-open info popup */}
      {showInfo && (
        <div onClick={dismissInfo}
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-6 fade-in">
          <div onClick={(e) => e.stopPropagation()} className="card max-w-sm w-full text-center">
            <div className="flex justify-center mb-2"><Logo size={48} /></div>
            <div className="font-extrabold text-gold text-lg">How to earn ZLN-XP</div>
            <div className="text-[12px] text-white/75 mt-2 text-left space-y-1">
              <div>💬 Valid message <b>+1</b> · ↩️ reply <b>+2</b> · 🗣️ discussion <b>+5</b></div>
              <div>🧠 Quiz correct <b>+5–35</b> (wrong −1) · 🧩 puzzle <b>+20–250</b></div>
              <div>📡 Channel <b>+30</b> · group <b>+35</b> · follow <b>+50</b></div>
              <div>🎯 Reactor missions, daily claim & referrals</div>
            </div>
            <div className="text-[11px] text-white/45 mt-2">
              Join Zelion Global, then chat meaningfully (min {d.msg_min_len || 10} chars, no spam, max 1 / 60s).
            </div>
            <div className="grid grid-cols-2 gap-2 mt-4">
              <Btn gold onClick={() => { openLink(groupUrl); dismissInfo() }}>Join Group</Btn>
              <Btn onClick={dismissInfo}>Got it</Btn>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const Stat = ({ v, l, gold }) => (
  <div className="flex-1 text-center">
    <div className={`text-lg font-extrabold ${gold ? 'text-gold' : ''}`}>{v}</div>
    <div className="text-[10px] uppercase tracking-wide text-white/40">{l}</div>
  </div>
)
