import React, { useEffect, useState } from 'react'
import { api } from '../api'
import { Card, Btn, Stat, Spinner, Progress, RankBadge } from '../ui'
import { tg } from '../telegram'

export default function Profile({ isAdmin, go }) {
  const [p, setP] = useState(null)
  const [ref, setRef] = useState(null)
  const [qr, setQr] = useState(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    api.profile().then(setP).catch(() => {})
    api.referrals().then(setRef).catch(() => {})
    api.quizRank().then(setQr).catch(() => {})
  }, [])

  const share = () => {
    if (!ref) return
    const text = 'Join me on Zelion Reactor ⚡'
    const url = `https://t.me/share/url?url=${encodeURIComponent(ref.link)}&text=${encodeURIComponent(text)}`
    if (tg?.openTelegramLink) tg.openTelegramLink(url); else window.open(url, '_blank')
  }
  const copy = async () => {
    try { await navigator.clipboard.writeText(ref.link); setCopied(true); setTimeout(() => setCopied(false), 1500) } catch (_) {}
  }

  if (!p) return <Spinner />

  return (
    <div className="space-y-4">
      {isAdmin && (
        <button onClick={() => go && go('admin')}
          className="card w-full text-left flex items-center gap-3 active:scale-[0.98] transition"
          style={{ borderColor: 'rgba(245,197,66,0.4)' }}>
          <div className="text-2xl">🛡</div>
          <div className="flex-1">
            <div className="font-bold text-gold">Admin Dashboard</div>
            <div className="text-[11px] text-white/45">Proofs · puzzles · hints · scripts · users</div>
          </div>
          <div className="text-white/40">→</div>
        </button>
      )}

      <button onClick={() => go && go('ranks')}
        className="card w-full text-left flex items-center gap-3 active:scale-[0.98] transition">
        <div className="text-2xl">🏆</div>
        <div className="flex-1">
          <div className="font-bold text-gold">Ranks & Leaderboard</div>
          <div className="text-[11px] text-white/45">Top operators · weekly & all-time · your position</div>
        </div>
        <div className="text-white/40">→</div>
      </button>

      <Card className="flex items-center justify-between">
        <RankBadge rank={qr?.rank || 'Reactor Cadet'}
          sub={qr?.next_rank ? `${qr.correct}/${qr.next_at} correct → ${qr.next_rank}` : `${qr?.correct ?? 0} correct`} />
        <div className="text-right">
          <div className="label">Quiz badge</div>
          <div className="text-xs text-white/50">ZelionTech mastery</div>
        </div>
      </Card>

      <Card className="glow text-center">
        <div className="text-xl font-extrabold text-gold">{p.rank}</div>
        <div className="text-sm text-white/50">Level {p.level} · @{p.username || p.first_name}</div>
        <div className="flex mt-4">
          <Stat label="Points" value={`${p.points} ZLN-XP`} accent />
          <Stat label="Energy" value={`${p.energy}/${p.energy_cap}`} />
          <Stat label="Streak" value={`${p.streak}🔥`} />
        </div>
        {p.next_threshold && (
          <div className="mt-4">
            <Progress value={p.points} max={p.next_threshold} />
            <div className="text-[11px] text-white/40 mt-1">{p.points}/{p.next_threshold} to next rank</div>
          </div>
        )}
      </Card>

      <Card>
        <div className="label">Referrals</div>
        <div className="flex">
          <Stat label="Activated" value={ref?.activated ?? '—'} accent />
          <Stat label="Pending" value={ref?.pending ?? '—'} />
          <Stat label="All-time #" value={p.all_time_rank || '—'} />
        </div>
        {ref && (
          <>
            <div className="mt-3 text-xs bg-black/40 border border-gold/15 rounded-xl px-3 py-2 break-all">{ref.link}</div>
            <div className="flex gap-2 mt-2">
              <Btn className="flex-1" onClick={copy}>{copied ? 'Copied ✓' : 'Copy link'}</Btn>
              <Btn gold className="flex-1" onClick={share}>📤 Share</Btn>
            </div>
            <div className="text-[11px] text-white/40 mt-2">
              Earn +150 ZLN-XP +50⚡ when a recruit stays 24h and reaches 50 ZLN-XP. Fake invites don’t count.
            </div>
          </>
        )}
      </Card>
    </div>
  )
}
