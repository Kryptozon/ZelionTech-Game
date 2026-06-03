import React, { useEffect, useState } from 'react'
import { api } from '../api'
import { Card, Btn, Chip, Spinner } from '../ui'
import { hapticOk, hapticErr } from '../telegram'

export default function Missions({ refresh, flash }) {
  const [data, setData] = useState(null)
  const [proofFor, setProofFor] = useState(null)
  const [handle, setHandle] = useState('')

  const load = async () => { try { setData(await api.missions()) } catch (e) { flash(e.message, 'red') } }
  useEffect(() => { load() }, [])

  const submitProof = async (m) => {
    if (!handle.trim()) return flash('Enter your username/profile', 'red')
    try {
      const r = await api.submitProof(m.id, handle.trim())
      flash(`Proof sent! +${r.reward}💎 after review`); hapticOk()
      setProofFor(null); setHandle(''); load()
    } catch (e) { flash(e.message === 'duplicate' ? 'Already submitted' : e.message, 'red'); hapticErr() }
  }

  const answerLearn = async (m, i) => {
    try {
      const r = await api.completeMission(m.id, i)
      if (r.correct) { flash(`✅ +${r.awarded || m.reward}💎`); hapticOk(); refresh(); load() }
      else { flash('❌ Wrong answer', 'red'); hapticErr() }
    } catch (e) { flash(e.message, 'red') }
  }

  if (!data) return <Spinner />
  const stateTone = { approved: 'green', pending: 'gold', rejected: 'red', none: 'gray' }

  return (
    <div className="space-y-4">
      <div className="label">📡 Follow ZelionTech — earn points</div>
      {data.social.map((m) => (
        <Card key={m.id}>
          <div className="flex items-center justify-between">
            <div className="font-bold">{m.title}</div>
            <Chip tone={stateTone[m.state]}>{m.state === 'none' ? `+${m.reward}💎` : m.state}</Chip>
          </div>
          <div className="text-xs text-white/50 mt-1">{m.description}</div>
          {m.state !== 'approved' && (
            <div className="flex gap-2 mt-3">
              <a href={m.url} target="_blank" rel="noreferrer" className="btn-ghost flex-1">🔗 Open</a>
              {m.verification === 'auto'
                ? <a href={m.url} target="_blank" rel="noreferrer" className="btn-gold flex-1">Join in app then bot</a>
                : <Btn gold className="flex-1" onClick={() => setProofFor(proofFor === m.id ? null : m.id)}>Submit proof</Btn>}
            </div>
          )}
          {proofFor === m.id && (
            <div className="mt-3 space-y-2">
              <input value={handle} onChange={(e) => setHandle(e.target.value)}
                placeholder="@yourhandle or profile link"
                className="w-full bg-black/40 border border-gold/20 rounded-xl px-3 py-2 text-sm outline-none" />
              <Btn gold className="w-full" onClick={() => submitProof(m)}>Send for review (24h)</Btn>
              <div className="text-[11px] text-white/40">Tip: attach a screenshot in the bot DM for faster approval.</div>
            </div>
          )}
        </Card>
      ))}

      <div className="label pt-2">🧩 Quick clearance quizzes</div>
      {data.learn.map((m) => (
        <Card key={m.id}>
          <div className="flex items-center justify-between">
            <div className="font-bold">{m.title}</div>
            <Chip tone={m.eligible ? 'green' : 'gray'}>{m.eligible ? `+${m.reward}💎` : 'cooldown'}</Chip>
          </div>
          <div className="text-sm mt-2">{m.question}</div>
          {m.eligible && (
            <div className="grid grid-cols-1 gap-2 mt-2">
              {m.options.map((o, i) => (
                <Btn key={i} onClick={() => answerLearn(m, i)} className="text-left">{o}</Btn>
              ))}
            </div>
          )}
        </Card>
      ))}
    </div>
  )
}
