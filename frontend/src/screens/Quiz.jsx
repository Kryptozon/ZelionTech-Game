import React, { useEffect, useState } from 'react'
import { api } from '../api'
import { Card, Btn, Chip, Spinner, Progress, Logo } from '../ui'
import { hapticOk, hapticErr } from '../telegram'

const TIER_TONE = { beginner: 'green', intermediate: 'gold', advanced: 'blue', expert: 'red' }
const QTYPE_LABEL = {
  mcq: 'Multiple Choice', true_false: 'True / False', scenario: 'Scenario',
  architecture: 'Architecture', tokenomics: 'Tokenomics',
}

export default function Quiz({ me, refresh, flash }) {
  const [mode, setMode] = useState('practice')
  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {[['practice', '🧠 Practice'], ['daily', '🗓 Daily Challenge']].map(([id, l]) => (
          <button key={id} onClick={() => setMode(id)}
            className={`flex-1 btn ${mode === id ? 'btn-gold' : 'btn-ghost'}`}>{l}</button>
        ))}
      </div>
      {mode === 'practice'
        ? <Practice me={me} refresh={refresh} flash={flash} />
        : <Daily me={me} refresh={refresh} flash={flash} />}
    </div>
  )
}

function QuestionCard({ q, onAnswered, refresh, flash }) {
  const [picked, setPicked] = useState(null)
  const [result, setResult] = useState(null)
  const isTF = q.qtype === 'true_false' || q.options.length === 2

  const answer = async (i) => {
    if (result) return
    setPicked(i)
    try {
      const r = await api.quizAnswer(q.id, i)
      if (r.error) { flash(r.error, 'red'); setPicked(null); return }
      setResult(r)
      if (r.correct) {
        hapticOk()
        flash(`+${r.awarded}💎${r.bonus ? ` (+${r.bonus} streak)` : ''}${r.special ? ' 🏅 RANK UP!' : ''}`)
      } else hapticErr()
      refresh()
      onAnswered && onAnswered(r)
    } catch (e) { flash(e.message, 'red'); setPicked(null) }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <Chip tone={TIER_TONE[q.tier] || 'gold'}>{q.tier || `D${q.difficulty}`}</Chip>
        <Chip tone="gray">{QTYPE_LABEL[q.qtype] || 'Quiz'}</Chip>
        {q.category && <Chip tone="blue">{q.category}</Chip>}
        <span className="ml-auto"><Chip tone="green">+{q.reward}💎</Chip></span>
      </div>

      <Card><div className="text-base font-semibold leading-snug">{q.question}</div></Card>

      <div className={isTF ? 'grid grid-cols-2 gap-2' : 'space-y-2'}>
        {q.options.map((opt, i) => {
          let cls = 'btn-ghost'
          if (result) {
            if (i === result.correct_index) cls = 'btn-gold'
            else if (i === picked) cls = 'btn !bg-rose-600/80'
          } else if (i === picked) cls = 'btn-gold'
          return (
            <button key={i} disabled={!!result} onClick={() => answer(i)}
              className={`${cls} ${isTF ? 'text-center' : 'text-left'}`}>
              {!isTF && <span className="opacity-50 mr-2">{String.fromCharCode(65 + i)}.</span>}{opt}
            </button>
          )
        })}
      </div>

      {result && (
        <Card className="space-y-2">
          <div className={`font-bold ${result.correct ? 'text-emerald-400' : 'text-rose-400'}`}>
            {result.correct ? `✅ Correct! +${result.awarded}💎` : '❌ Not quite'}
          </div>
          {result.explanation && <div className="text-sm text-white/70">{result.explanation}</div>}
          <a href={result.source_url?.startsWith('http') ? result.source_url : 'https://zeliontech.com'}
            target="_blank" rel="noreferrer" className="text-xs text-gold underline">
            📖 Based on {result.source_type === 'document' ? 'the ZelionTech whitepaper' : 'the ZelionTech website'}
          </a>
          <div className="text-[11px] text-white/40">Quiz rank: {result.rank}</div>
        </Card>
      )}
    </div>
  )
}

function Practice({ me, refresh, flash }) {
  const [q, setQ] = useState(null)
  const [loading, setLoading] = useState(true)
  const [key, setKey] = useState(0)

  const load = async () => {
    setLoading(true)
    try { setQ(await api.quizNext()) } catch (e) { flash(e.message, 'red') } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  if (loading) return <Spinner />
  if (q?.cooldown) return (
    <Card className="text-center">
      <div className="text-4xl">⏳</div>
      <div className="font-bold mt-2">Cooldown</div>
      <div className="text-sm text-white/50">Wrong answer — retry in {q.cooldown}s.</div>
      <Btn className="mt-4" onClick={load}>Retry</Btn>
    </Card>
  )
  if (q?.empty) return (
    <Card className="text-center">
      <Logo size={56} />
      <div className="font-bold mt-3">No questions yet</div>
      <div className="text-sm text-white/50">An admin must run <b>/kbrefresh</b> + <b>/genquiz</b> first.</div>
    </Card>
  )

  return (
    <div>
      <QuestionCard key={key} q={q} refresh={refresh} flash={flash} />
      <Btn gold className="w-full mt-4" onClick={() => { setKey(key + 1); load() }}>Next question →</Btn>
      <div className="mt-4">
        <div className="label mb-1">Progress to harder questions</div>
        <Progress value={me.points} max={me.next_threshold || me.points} />
        <div className="text-[11px] text-white/40 mt-1">Level up to unlock advanced & expert tiers.</div>
      </div>
    </div>
  )
}

function Daily({ me, refresh, flash }) {
  const [data, setData] = useState(null)
  const load = async () => { try { setData(await api.quizDaily()) } catch (e) { flash(e.message, 'red') } }
  useEffect(() => { load() }, [])
  if (!data) return <Spinner />
  if (data.empty) return <Card className="text-center text-white/50">No daily challenge yet — KB needs questions.</Card>

  const done = data.questions.filter((q) => q.answered).length
  const next = data.questions.find((q) => !q.answered)

  return (
    <div className="space-y-4">
      <Card className="glow text-center">
        <Logo size={40} />
        <div className="font-extrabold mt-2">Daily Challenge</div>
        <div className="text-xs text-white/50">{data.date} · complete all {data.questions.length} for +{data.bonus}💎</div>
        <div className="mt-3"><Progress value={done} max={data.questions.length} /></div>
        <div className="text-[11px] text-white/40 mt-1">{done}/{data.questions.length} answered</div>
        {data.completed && <div className="text-emerald-400 font-bold mt-2">✅ Completed! {data.reward_just_paid ? `+${data.reward_just_paid}💎` : 'Bonus claimed'}</div>}
      </Card>

      {next
        ? <QuestionCard key={next.id} q={next} refresh={refresh} flash={flash} onAnswered={() => setTimeout(load, 700)} />
        : !data.completed && <Spinner />}
    </div>
  )
}
