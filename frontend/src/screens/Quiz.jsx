import React, { useEffect, useState, useRef } from 'react'
import { api } from '../api'
import { Card, Btn, Chip, Spinner, Logo } from '../ui'
import { hapticOk, hapticErr } from '../telegram'

const TIER_TONE = { beginner: 'green', intermediate: 'gold', advanced: 'blue', expert: 'red' }

function fmt(secs) {
  secs = Math.max(0, secs | 0)
  const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60), s = secs % 60
  return `${h}h ${m}m ${s}s`
}

export default function Quiz({ me, refresh, flash }) {
  const [data, setData] = useState(null)
  const [picked, setPicked] = useState(null)
  const [result, setResult] = useState(null)
  const [cd, setCd] = useState(0)
  const timer = useRef(null)

  const load = async () => {
    setPicked(null); setResult(null)
    try {
      const d = await api.quizDaily()
      setData(d); setCd(d.countdown_seconds || 0)
    } catch (e) { flash(e.message, 'red') }
  }
  useEffect(() => { load() }, [])

  useEffect(() => {
    clearInterval(timer.current)
    if (data?.completed) timer.current = setInterval(() => setCd((c) => Math.max(0, c - 1)), 1000)
    return () => clearInterval(timer.current)
  }, [data?.completed])

  if (!data) return <Spinner />

  if (data.empty) return (
    <Card className="text-center">
      <Logo size={56} />
      <div className="font-bold mt-3">Quiz warming up</div>
      <div className="text-sm text-white/50">An admin needs to run <b>/seedquestions</b> once.</div>
    </Card>
  )

  const answered = data.questions.filter((q) => q.answered).length
  const current = data.questions.find((q) => !q.answered)

  const header = (
    <Card className="glow">
      <div className="flex items-center gap-3">
        <Logo size={38} />
        <div className="flex-1">
          <div className="font-extrabold">Daily Zelion Challenge</div>
          <div className="text-[11px] text-white/45">5 questions every 24h · {me.quiz_rank}</div>
        </div>
        <Chip tone="gold">{answered}/{data.total}</Chip>
      </div>
      <div className="mt-3 flex gap-1">
        {data.questions.map((q, i) => (
          <div key={i} className={`flex-1 h-2 rounded-full ${q.answered ? (q.was_correct ? 'bg-emerald-400' : 'bg-rose-500') : 'bg-white/12'}`} />
        ))}
      </div>
    </Card>
  )

  if (data.completed || !current) return (
    <div className="space-y-4">
      {header}
      <Card className="text-center">
        <div className="text-4xl">✅</div>
        <div className="font-extrabold mt-2">Daily quiz completed!</div>
        <div className="text-sm text-white/50 mt-1">You answered all {data.total}. Come back for 5 fresh questions.</div>
        <div className="mt-3 text-gold font-bold">⏳ Next quiz in {fmt(cd)}</div>
      </Card>
    </div>
  )

  const answer = async (i) => {
    if (result) return
    setPicked(i)
    try {
      const r = await api.quizAnswer(current.id, i)
      if (r.error) { flash(r.error.replace(/_/g, ' '), 'red'); setPicked(null); return }
      setResult(r)
      if (r.correct) { hapticOk(); flash(`+${r.awarded} ZLN-XP${r.bonus ? ` (+${r.bonus} streak)` : ''}${r.special ? ' 🏅 RANK UP!' : ''}`) }
      else hapticErr()
      refresh()
    } catch (e) { flash(e.message, 'red'); setPicked(null) }
  }

  return (
    <div className="space-y-4">
      {header}

      <div className="flex items-center gap-2">
        <Chip tone={TIER_TONE[current.tier] || 'gold'}>{current.tier || `D${current.difficulty}`}</Chip>
        {current.category && <Chip tone="blue">{current.category.replace(/_/g, ' ')}</Chip>}
        <span className="ml-auto"><Chip tone="green">+{current.reward} ZLN-XP</Chip></span>
      </div>

      <Card><div className="text-base font-semibold leading-snug">{current.question}</div></Card>

      <div className="space-y-2">
        {current.options.map((opt, i) => {
          let cls = 'btn-ghost'
          if (result) {
            if (i === result.correct_index) cls = 'btn-gold'
            else if (i === picked) cls = 'btn !bg-rose-600/80'
          } else if (i === picked) cls = 'btn-gold'
          return (
            <button key={i} disabled={!!result} onClick={() => answer(i)} className={`${cls} w-full text-left`}>
              <span className="opacity-50 mr-2">{String.fromCharCode(65 + i)}.</span>{opt}
            </button>
          )
        })}
      </div>

      {result && (
        <Card className="space-y-2">
          <div className={`font-bold ${result.correct ? 'text-emerald-400' : 'text-rose-400'}`}>
            {result.correct
              ? `✅ Correct +${result.awarded} XP${result.bonus ? ` (incl. +${result.bonus} streak)` : ''}`
              : `❌ Wrong −${result.penalty ?? 10} XP`}
          </div>
          {!result.correct && result.correct_answer && (
            <div className="text-sm"><span className="text-white/50">Correct answer:</span>{' '}
              <span className="text-emerald-300 font-semibold">{result.correct_answer}</span></div>
          )}
          {result.explanation && <div className="text-sm text-white/70">{result.explanation}</div>}
          <div className="text-xs text-gold">📖 Source: {result.source_section || 'ZelionTech knowledge base'}</div>
          {result.training_required && (
            <div className="text-[12px] text-amber-300 border border-amber-400/30 rounded-lg p-2 mt-1">
              ⚠ Operator Training Required. Review Zelion materials on 📢 Telegram & 📺 YouTube, then return.
            </div>
          )}
          <Btn gold className="w-full mt-1" onClick={load}>
            {result.remaining > 0 ? `Next question (${result.completed_count}/${data.total}) →` : 'Finish'}
          </Btn>
        </Card>
      )}
    </div>
  )
}
