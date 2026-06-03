import React, { useEffect, useState } from 'react'
import { api } from '../api'
import { Card, Btn, Chip, Spinner } from '../ui'

export default function Admin({ flash }) {
  const [tab, setTab] = useState('proofs')
  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {[['proofs', 'Proofs'], ['questions', 'Questions'], ['kb', 'Knowledge']].map(([id, l]) => (
          <button key={id} onClick={() => setTab(id)}
            className={`flex-1 btn ${tab === id ? 'btn-gold' : 'btn-ghost'}`}>{l}</button>
        ))}
      </div>
      {tab === 'proofs' && <Proofs flash={flash} />}
      {tab === 'questions' && <Questions flash={flash} />}
      {tab === 'kb' && <KB flash={flash} />}
    </div>
  )
}

function Proofs({ flash }) {
  const [rows, setRows] = useState(null)
  const load = () => api.adminProofs().then((d) => setRows(d.proofs)).catch((e) => flash(e.message, 'red'))
  useEffect(() => { load() }, [])
  if (!rows) return <Spinner />
  if (!rows.length) return <Card className="text-center text-white/50">✅ Queue clear</Card>

  const act = async (id, ok) => {
    try {
      ok ? await api.approveProof(id) : await api.rejectProof(id, 'Rejected from Mini App')
      flash(ok ? 'Approved ✅' : 'Rejected'); load()
    } catch (e) { flash(e.message, 'red') }
  }
  return rows.map((p) => (
    <Card key={p.id}>
      <div className="flex justify-between"><b>#{p.id} {p.title}</b><Chip tone="green">+{p.reward}💎</Chip></div>
      <div className="text-xs text-white/50 mt-1">@{p.username} ({p.user_id}) · handle: {p.handle || '—'}</div>
      <div className="flex gap-2 mt-3">
        <Btn gold className="flex-1" onClick={() => act(p.id, true)}>Approve</Btn>
        <Btn className="flex-1" onClick={() => act(p.id, false)}>Reject</Btn>
      </div>
    </Card>
  ))
}

function Questions({ flash }) {
  const [rows, setRows] = useState(null)
  const load = () => api.adminQuestions('pending').then((d) => setRows(d.questions)).catch((e) => flash(e.message, 'red'))
  useEffect(() => { load() }, [])
  if (!rows) return <Spinner />
  if (!rows.length) return <Card className="text-center text-white/50">No pending questions. Refresh the knowledge base to generate more.</Card>

  const act = async (id, ok) => {
    try { ok ? await api.approveQuestion(id) : await api.rejectQuestion(id); flash(ok ? 'Approved ✅' : 'Rejected'); load() }
    catch (e) { flash(e.message, 'red') }
  }
  return rows.map((q) => (
    <Card key={q.id}>
      <div className="flex justify-between items-center">
        <Chip>D{q.difficulty}</Chip><Chip tone="gray">{q.created_by}</Chip>
      </div>
      <div className="font-semibold mt-2">{q.question}</div>
      <ul className="text-sm mt-2 space-y-1">
        {q.options.map((o, i) => (
          <li key={i} className={i === q.correct_index ? 'text-emerald-400' : 'text-white/60'}>
            {String.fromCharCode(65 + i)}. {o} {i === q.correct_index && '✓'}
          </li>
        ))}
      </ul>
      <a href={q.source_url} target="_blank" rel="noreferrer" className="text-xs text-gold underline block mt-2">source</a>
      <div className="flex gap-2 mt-3">
        <Btn gold className="flex-1" onClick={() => act(q.id, true)}>Approve</Btn>
        <Btn className="flex-1" onClick={() => act(q.id, false)}>Reject</Btn>
      </div>
    </Card>
  ))
}

function KB({ flash }) {
  const [busy, setBusy] = useState(false)
  const [res, setRes] = useState(null)
  const refresh = async () => {
    setBusy(true)
    try { setRes(await api.kbRefresh()); flash('Knowledge base refreshed ✅') }
    catch (e) { flash(e.message, 'red') } finally { setBusy(false) }
  }
  return (
    <Card>
      <div className="font-bold">ZelionTech Knowledge Base</div>
      <div className="text-xs text-white/50 mt-1">
        Crawls zeliontech.com, stores text chunks, and AI-generates grounded quiz questions
        (saved as pending for review). Every question cites a source URL.
      </div>
      <Btn gold className="w-full mt-3" disabled={busy} onClick={refresh}>
        {busy ? 'Crawling…' : '🔄 Refresh & generate'}
      </Btn>
      {res && (
        <div className="text-xs text-white/60 mt-3">
          Pages: {res.kb?.pages} · Chunks: {res.kb?.chunks} · Generated: {res.generated?.inserted} ({res.generated?.mode})
        </div>
      )}
    </Card>
  )
}
