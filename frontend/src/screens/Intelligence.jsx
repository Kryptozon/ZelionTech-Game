import React, { useEffect, useState, useRef } from 'react'
import { api } from '../api'
import { Card, Btn, Chip, Spinner, Logo } from '../ui'
import { tg, hapticOk, hapticErr } from '../telegram'

const GROUP_URL = 'https://t.me/zelionglobal'
const CHANNEL_URL = 'https://t.me/zeliontechofficial'
const YT_URL = 'https://www.youtube.com/@ZelionTech'
const TT_URL = 'https://www.tiktok.com/@zeliontech_zev'
const DIFF_TONE = { easy: 'green', medium: 'gold', hard: 'blue', legendary: 'red' }

function fmt(s) { s = Math.max(0, s | 0); return `${Math.floor(s / 60)}m ${s % 60}s` }
function openLink(u) { if (tg?.openTelegramLink && u.includes('t.me')) tg.openTelegramLink(u); else window.open(u, '_blank') }

export default function Intelligence({ refresh, flash }) {
  const [data, setData] = useState(null)
  const [mode, setMode] = useState('daily')
  const [val, setVal] = useState('')
  const [result, setResult] = useState(null)
  const [lb, setLb] = useState([])
  const [cd, setCd] = useState(0)
  const timer = useRef(null)

  const load = async () => {
    setResult(null); setVal('')
    try {
      const d = await api.puzzlesDaily(); setData(d)
      setLb((await api.puzzlesLeaderboard('week')).leaderboard)
    } catch (e) { setData({ daily: { empty: true }, weekly: { empty: true } }) }
  }
  useEffect(() => { load() }, [])

  const puzzle = data ? (mode === 'daily' ? data.daily : data.weekly) : null
  useEffect(() => { setCd(puzzle?.cooldown_seconds || 0) }, [puzzle])
  useEffect(() => {
    clearInterval(timer.current)
    if (cd > 0) timer.current = setInterval(() => setCd((c) => Math.max(0, c - 1)), 1000)
    return () => clearInterval(timer.current)
  }, [cd > 0])

  if (!data) return <Spinner />
  if (puzzle?.empty) return (
    <Wrap mode={mode} setMode={setMode}>
      <Card className="text-center"><Logo size={48} />
        <div className="font-bold mt-3">Intelligence warming up</div>
        <div className="text-sm text-white/50">Puzzles are being deployed. Check back soon, Operator.</div>
      </Card>
    </Wrap>
  )
  // Manual release: nothing is live until the admin releases the next puzzle.
  if (puzzle?.waiting) return (
    <Wrap mode={mode} setMode={setMode}>
      <Card className="text-center py-8"><div className="text-4xl">⏳</div>
        <div className="font-bold mt-2">No Active Puzzle</div>
        <div className="text-sm text-white/50 mt-1">{puzzle.message || 'Waiting for admin to release the next puzzle.'}</div>
      </Card>
    </Wrap>
  )
  // A skipped puzzle stays permanently missed.
  if (puzzle?.missed) return (
    <Wrap mode={mode} setMode={setMode}>
      <Card className="text-center py-8" style={{ borderColor: 'rgba(244,63,94,0.5)' }}>
        <div className="text-4xl">❌</div>
        <div className="font-extrabold text-rose-400 mt-2">Puzzle Missed</div>
        <div className="text-sm text-white/50 mt-1">{puzzle.message || 'This puzzle is no longer available.'}</div>
      </Card>
    </Wrap>
  )

  const submit = async () => {
    if (!val.trim()) return flash('Enter your answer', 'red')
    try {
      const r = await api.puzzleAnswer(puzzle.id, val.trim())
      if (r.error === 'cooldown') { setCd(r.cooldown_seconds); flash('Locked — cooldown active', 'red'); return }
      if (r.error) { flash(r.error.replace(/_/g, ' '), 'red'); return }
      setResult(r)
      if (r.correct) { hapticOk(); flash(`✅ +${r.awarded} ZLN-XP`); refresh() }
      else { hapticErr(); if (r.locked) setCd(r.cooldown_seconds) }
    } catch (e) { flash(e.message, 'red') }
  }

  const solved = puzzle.solved || result?.correct
  return (
    <Wrap mode={mode} setMode={setMode}>
      <div className="flex items-center gap-2">
        <Chip tone={DIFF_TONE[puzzle.difficulty]}>{puzzle.difficulty}</Chip>
        <Chip tone="gray">{puzzle.category}</Chip>
        <span className="ml-auto"><Chip tone="green">+{puzzle.reward} ZLN-XP</Chip></span>
      </div>

      <Card>
        <div className="font-bold mb-1">{puzzle.title}</div>
        <div className="text-sm whitespace-pre-line text-white/80">{puzzle.question}</div>
      </Card>

      {/* Hints are NEVER shown in-game. Real hints live ONLY on YouTube & TikTok;
          everywhere else we only announce that a new hint was released. */}
      <Card>
        <div className="label">🔎 Need a hint?</div>
        <div className="text-[12px] text-white/60 mt-1">
          Actual hints are revealed only on our <b>YouTube</b> and <b>TikTok</b>. Other channels just announce drops.
        </div>
        {puzzle.released_hints > 0 && (
          <div className="mt-2 text-[12px] text-gold">
            🔔 {puzzle.released_hints} new hint{puzzle.released_hints > 1 ? 's' : ''} released — watch YouTube / TikTok to decode.
          </div>
        )}
        <div className="grid grid-cols-2 gap-2 mt-2">
          <Btn onClick={() => openLink(YT_URL)}>📺 YouTube {puzzle.youtube_posted ? '🟢' : ''}</Btn>
          <Btn onClick={() => openLink(TT_URL)}>🎵 TikTok</Btn>
        </div>
      </Card>

      {puzzle.closed ? (
        <Card className="text-center" style={{ borderColor: 'rgba(244,63,94,0.5)' }}>
          <div className="text-3xl">⚠</div>
          <div className="font-extrabold text-rose-400 mt-1">Puzzle Closed Forever</div>
          <div className="text-sm text-white/50">This mystery has ended — no more submissions.</div>
        </Card>
      ) : solved ? (
        <Card className="text-center">
          <div className="text-3xl">✅</div>
          <div className="font-bold text-emerald-400 mt-1">Solved!</div>
          {(result?.explanation || puzzle.explanation) &&
            <div className="text-sm text-white/70 mt-1">{result?.explanation || puzzle.explanation}</div>}
        </Card>
      ) : cd > 0 ? (
        <Card className="text-center">
          <div className="font-bold text-rose-400">🔒 Too many attempts</div>
          <div className="text-sm text-white/50">Cooldown: {fmt(cd)} — review the clues meanwhile.</div>
        </Card>
      ) : (
        <Card className="space-y-2">
          <input value={val} onChange={(e) => setVal(e.target.value)} placeholder="Enter decoded answer…"
            className="w-full bg-black/40 border border-gold/20 rounded-xl px-3 py-2 outline-none uppercase" />
          <div className="text-[11px] text-white/40">Attempts left: {result?.attempts_remaining ?? puzzle.attempts_remaining}</div>
          {result && !result.correct && (
            <div className="text-rose-300 text-sm">❌ Incorrect −{result.penalty} ZLN-XP · {result.attempts_remaining} left</div>
          )}
          <Btn gold className="w-full" onClick={submit}>Submit answer</Btn>
        </Card>
      )}

      <div className="label">🏆 Intelligence Leaderboard (week)</div>
      <Card>
        {lb.length === 0 ? <div className="text-center text-white/40 py-3">No solvers yet — be first!</div>
          : lb.map((r, i) => (
            <div key={i} className="flex justify-between py-1 border-b border-white/5 last:border-0">
              <span>{['🥇', '🥈', '🥉'][i] || `${i + 1}.`} {r.name}</span>
              <span className="text-gold font-bold">{r.score} ZLN-XP</span>
            </div>
          ))}
      </Card>
    </Wrap>
  )
}

function Wrap({ mode, setMode, children }) {
  return (
    <div className="space-y-4">
      <Card className="flex items-center gap-3">
        <Logo size={34} />
        <div className="flex-1">
          <div className="font-extrabold">⚡ Zelion Intelligence</div>
          <div className="text-[11px] text-white/45">Decode mysteries · watch · read · solve</div>
        </div>
      </Card>
      <div className="flex gap-2">
        {[['daily', '🧩 Daily Puzzle'], ['weekly', '🗝 Weekly Hunt']].map(([id, l]) => (
          <button key={id} onClick={() => setMode(id)}
            className={`flex-1 btn ${mode === id ? 'btn-gold' : 'btn-ghost'}`}>{l}</button>
        ))}
      </div>
      {children}
    </div>
  )
}
