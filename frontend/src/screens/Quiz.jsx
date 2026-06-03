import React, { useEffect, useState } from 'react'
import { api } from '../api'
import { Card, Btn, Chip, Spinner, Progress } from '../ui'
import { hapticOk, hapticErr } from '../telegram'

const DIFF_LABEL = { 1: 'Basic', 2: 'Understanding', 3: 'Comparison', 4: 'Scenario', 5: 'Expert' }

export default function Quiz({ me, refresh, flash }) {
  const [q, setQ] = useState(null)
  const [loading, setLoading] = useState(true)
  const [picked, setPicked] = useState(null)
  const [result, setResult] = useState(null)

  const load = async () => {
    setLoading(true); setPicked(null); setResult(null)
    try { setQ(await api.quizNext()) } catch (e) { flash(e.message, 'red') } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const answer = async (i) => {
    if (result) return
    setPicked(i)
    try {
      const r = await api.quizAnswer(q.id, i)
      setResult(r)
      if (r.correct) { hapticOk(); flash(`+${r.awarded}💎${r.streak > 1 ? ` 🔥x${r.streak}` : ''}`) }
      else { hapticErr() }
      refresh()
    } catch (e) { flash(e.message, 'red'); setPicked(null) }
  }

  if (loading) return <Spinner />

  if (q?.cooldown) return (
    <Card className="text-center">
      <div className="text-4xl">⏳</div>
      <div className="font-bold mt-2">Cooldown active</div>
      <div className="text-sm text-white/50">Wrong answer — try again in {q.cooldown}s.</div>
      <Btn className="mt-4" onClick={load}>Retry</Btn>
    </Card>
  )
  if (q?.empty) return (
    <Card className="text-center">
      <div className="text-4xl">🧠</div>
      <div className="font-bold mt-2">No questions yet</div>
      <div className="text-sm text-white/50">An admin needs to refresh the ZelionTech knowledge base and approve questions.</div>
    </Card>
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Chip>D{q.difficulty} · {DIFF_LABEL[q.difficulty]}</Chip>
        <Chip tone="gray">unlocked ≤ L{q.unlocked_level}</Chip>
        <Chip tone="green">+{q.reward}💎</Chip>
      </div>

      <Card>
        <div className="text-base font-semibold leading-snug">{q.question}</div>
      </Card>

      <div className="space-y-2">
        {q.options.map((opt, i) => {
          let cls = 'btn-ghost'
          if (result) {
            if (i === result.correct_index) cls = 'btn-gold'
            else if (i === picked) cls = 'btn !bg-rose-600/80'
          } else if (i === picked) cls = 'btn-gold'
          return (
            <button key={i} disabled={!!result} onClick={() => answer(i)}
              className={`${cls} w-full text-left`}>
              <span className="opacity-50 mr-2">{String.fromCharCode(65 + i)}.</span>{opt}
            </button>
          )
        })}
      </div>

      {result && (
        <Card className="space-y-2">
          <div className={`font-bold ${result.correct ? 'text-emerald-400' : 'text-rose-400'}`}>
            {result.correct ? '✅ Correct!' : '❌ Not quite'}
          </div>
          {result.explanation && <div className="text-sm text-white/70">{result.explanation}</div>}
          <a href={result.source_url} target="_blank" rel="noreferrer" className="text-xs text-gold underline">
            📖 Based on the ZelionTech website
          </a>
          <Btn gold className="w-full mt-2" onClick={load}>Next question →</Btn>
        </Card>
      )}

      <div>
        <div className="label mb-1">Progress to harder questions</div>
        <Progress value={me.points} max={me.next_threshold || me.points} />
        <div className="text-[11px] text-white/40 mt-1">Level up to unlock higher difficulties (up to Expert).</div>
      </div>
    </div>
  )
}
