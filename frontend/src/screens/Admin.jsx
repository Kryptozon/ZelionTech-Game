import React, { useEffect, useState } from 'react'
import { api } from '../api'
import { Card, Btn, Chip, Spinner, Logo } from '../ui'

export default function Admin({ me, flash }) {
  // Hard client gate (server also enforces). me.is_admin is set only for ADMIN_IDS.
  if (!me?.is_admin) {
    return (
      <Card className="text-center">
        <Logo size={56} />
        <div className="font-extrabold mt-3 text-rose-400">Unauthorized</div>
        <div className="text-sm text-white/50">This area is restricted to the ZelionTech admin.</div>
      </Card>
    )
  }

  const [tab, setTab] = useState('proofs')
  return (
    <div className="space-y-4">
      <Counters />
      <div className="flex gap-2 flex-wrap">
        {[['proofs', 'Proofs'], ['questions', 'Quiz'], ['puzzles', 'Puzzles'], ['kb', 'KB']].map(([id, l]) => (
          <button key={id} onClick={() => setTab(id)}
            className={`flex-1 btn ${tab === id ? 'btn-gold' : 'btn-ghost'}`}>{l}</button>
        ))}
      </div>
      {tab === 'proofs' && <Proofs flash={flash} />}
      {tab === 'questions' && <Questions flash={flash} />}
      {tab === 'puzzles' && <Puzzles flash={flash} />}
      {tab === 'kb' && <KB flash={flash} />}
    </div>
  )
}

function Puzzles({ flash }) {
  const [rows, setRows] = useState(null)
  const [diff, setDiff] = useState('')
  const [open, setOpen] = useState(null)
  const load = () => api.adminPuzzles(diff).then((d) => setRows(d.puzzles)).catch((e) => flash(e.message, 'red'))
  useEffect(() => { load() }, [diff])
  const setActive = async (id, active) => {
    try {
      await fetch(`/api/admin/puzzles/${id}/${active ? 'activate' : 'deactivate'}`, {
        method: 'POST', headers: { 'X-Init-Data': window.Telegram?.WebApp?.initData || '' } })
      flash(active ? 'Activated' : 'Deactivated'); load()
    } catch (e) { flash(e.message, 'red') }
  }
  if (!rows) return <Spinner />
  return (
    <div className="space-y-3">
      <select value={diff} onChange={(e) => setDiff(e.target.value)}
        className="w-full bg-black/40 border border-gold/20 rounded-xl px-2 py-2 text-sm">
        <option value="">All difficulties</option>
        {['easy', 'medium', 'hard', 'legendary'].map((d) => <option key={d} value={d}>{d}</option>)}
      </select>
      <div className="text-[11px] text-white/40">{rows.length} puzzles · answers are admin-only</div>
      {rows.slice(0, 60).map((p) => (
        <Card key={p.id}>
          <div className="flex items-center gap-2">
            <Chip tone="gray">{p.difficulty}</Chip>
            <div className="flex-1 text-sm font-semibold truncate">{p.title}</div>
            <Chip tone="green">+{p.reward}</Chip>
          </div>
          <div className="text-[11px] text-white/45 mt-1">#{p.id} · {p.category}</div>
          <div className="text-xs text-gold mt-1">🔑 {p.answer}</div>
          <div className="flex gap-2 mt-2">
            <Btn className="flex-1" onClick={() => setActive(p.id, !p.active)}>{p.active ? 'Deactivate' : 'Activate'}</Btn>
            <Btn className="flex-1" onClick={() => setOpen(open === p.id ? null : p.id)}>Hints/Script</Btn>
          </div>
          {open === p.id && <PuzzleDetail id={p.id} flash={flash} />}
        </Card>
      ))}
    </div>
  )
}

function PuzzleDetail({ id, flash }) {
  const [h, setH] = useState(null)
  useEffect(() => { api.puzzleHints(id).then(setH).catch((e) => flash(e.message, 'red')) }, [id])
  if (!h) return <Spinner />
  return (
    <div className="mt-2 text-[11px] text-white/60 space-y-1 border-t border-white/10 pt-2">
      <div>Hint1: {h.daily_hint1}</div>
      <div>Hint2: {h.daily_hint2}</div>
      <div>Hint3: {h.daily_hint3}</div>
      <div>YT timestamp: {h.youtube_timestamp}</div>
      <div>TG post: {h.telegram_post_text}</div>
      <div className="text-gold">Placement: {h.hidden_answer_placement}</div>
    </div>
  )
}

function Counters() {
  const [s, setS] = useState(null)
  useEffect(() => { api.adminProofStats().then(setS).catch(() => {}) }, [])
  if (!s) return null
  const Item = ({ label, value, tone }) => (
    <div className="flex-1 text-center">
      <div className={`text-lg font-black ${tone || 'text-gold'}`}>{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-white/40">{label}</div>
    </div>
  )
  return (
    <Card className="flex">
      <Item label="Pending" value={s.pending} />
      <Item label="Appr. today" value={s.approved_today} tone="text-emerald-400" />
      <Item label="Rej. today" value={s.rejected_today} tone="text-rose-400" />
      <Item label="ZLN-XP out" value={s.zln_distributed} />
      <Item label="Banned" value={s.banned} tone="text-rose-400" />
    </Card>
  )
}

const STATUSES = [['pending', 'Pending'], ['approved', 'Approved'], ['rejected', 'Rejected'], ['banned', 'Banned']]

function Proofs({ flash }) {
  const [status, setStatus] = useState('pending')
  const [rows, setRows] = useState(null)
  const [platform, setPlatform] = useState('')
  const [search, setSearch] = useState('')
  const [modal, setModal] = useState(null)

  const load = async () => {
    setRows(null)
    try {
      if (status === 'banned') {
        const d = await api.adminBanned(); setRows(d.banned.map((b) => ({ ...b, _ban: true })))
      } else {
        const d = await api.adminProofs(status); setRows(d.proofs)
      }
    } catch (e) { flash(e.message, 'red') }
  }
  useEffect(() => { load() }, [status])

  const act = async (id, kind) => {
    try {
      if (kind === 'approve') await api.approveProof(id)
      else if (kind === 'ban') await api.banProof(id)
      else {
        const reason = prompt('Rejection reason (optional):') || 'Not valid'
        await api.rejectProof(id, reason)
      }
      flash(kind === 'approve' ? 'Approved ✅' : kind === 'ban' ? 'User banned 🚫' : 'Rejected'); load()
    } catch (e) { flash(e.message, 'red') }
  }

  const platforms = rows ? [...new Set(rows.map((r) => r.platform).filter(Boolean))] : []
  const filtered = (rows || []).filter((r) =>
    (!platform || r.platform === platform) &&
    (!search || (r.username || '').toLowerCase().includes(search.toLowerCase()) || String(r.user_id).includes(search)))

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        {STATUSES.map(([id, l]) => (
          <button key={id} onClick={() => setStatus(id)}
            className={`flex-1 btn text-xs ${status === id ? 'btn-gold' : 'btn-ghost'}`}>{l}</button>
        ))}
      </div>

      {status !== 'banned' && (
        <div className="flex gap-2">
          <select value={platform} onChange={(e) => setPlatform(e.target.value)}
            className="flex-1 bg-black/40 border border-gold/20 rounded-xl px-2 py-2 text-sm">
            <option value="">All platforms</option>
            {platforms.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="search user…"
            className="flex-1 bg-black/40 border border-gold/20 rounded-xl px-3 py-2 text-sm outline-none" />
        </div>
      )}

      {!rows ? <Spinner /> : filtered.length === 0 ? (
        <Card className="text-center text-white/50">Nothing here.</Card>
      ) : filtered.map((r) => r._ban ? (
        <Card key={r.user_id}>
          <div className="font-bold text-rose-400">🚫 @{r.username || r.first_name || r.user_id}</div>
          <div className="text-xs text-white/50">ID {r.user_id} · {r.reason} · {String(r.created_at).slice(0, 16)}</div>
        </Card>
      ) : (
        <Card key={r.id}>
          <div className="flex gap-3">
            {r.image_url ? (
              <img src={r.image_url} onClick={() => setModal(r.image_url)} alt="proof"
                className="w-16 h-16 rounded-lg object-cover border border-gold/20 cursor-pointer" />
            ) : <div className="w-16 h-16 rounded-lg bg-white/5 grid place-items-center text-[10px] text-white/30">no img</div>}
            <div className="flex-1 min-w-0">
              <div className="font-bold truncate">{r.mission}</div>
              <div className="text-[11px] text-white/50">@{r.username || '—'} · ID {r.user_id}</div>
              <div className="text-[11px] text-white/50">{r.platform} · 🔗 {r.handle || r.link || '—'}</div>
              <div className="text-[11px] text-white/40">{String(r.created_at).slice(0, 16)} · +{r.reward} ZLN-XP</div>
              {r.reject_reason && <div className="text-[11px] text-rose-300">Reason: {r.reject_reason}</div>}
            </div>
          </div>
          {status === 'pending' && (
            <div className="grid grid-cols-3 gap-2 mt-3">
              <Btn gold onClick={() => act(r.id, 'approve')}>✅</Btn>
              <Btn onClick={() => act(r.id, 'reject')}>❌</Btn>
              <Btn className="!bg-rose-600/80" onClick={() => act(r.id, 'ban')}>🚫</Btn>
            </div>
          )}
        </Card>
      ))}

      {modal && (
        <div onClick={() => setModal(null)}
          className="fixed inset-0 z-50 bg-black/85 flex items-center justify-center p-4 fade-in">
          <img src={modal} alt="proof" className="max-w-full max-h-full rounded-xl border border-gold/30" />
        </div>
      )}
    </div>
  )
}

function Questions({ flash }) {
  const [rows, setRows] = useState(null)
  const load = () => api.adminQuestions('pending').then((d) => setRows(d.questions)).catch((e) => flash(e.message, 'red'))
  useEffect(() => { load() }, [])
  if (!rows) return <Spinner />
  if (!rows.length) return <Card className="text-center text-white/50">No pending questions.</Card>
  const act = async (id, ok) => {
    try { ok ? await api.approveQuestion(id) : await api.rejectQuestion(id); flash(ok ? 'Approved' : 'Rejected'); load() }
    catch (e) { flash(e.message, 'red') }
  }
  return rows.map((q) => (
    <Card key={q.id}>
      <div className="font-semibold text-sm">{q.question}</div>
      <div className="text-[11px] text-white/40 mt-1">D{q.difficulty} · {q.created_by}</div>
      <div className="flex gap-2 mt-2">
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
    try { setRes(await api.kbRefresh()); flash('KB refreshed ✅') }
    catch (e) { flash(e.message, 'red') } finally { setBusy(false) }
  }
  return (
    <Card>
      <div className="font-bold">Knowledge Base</div>
      <div className="text-xs text-white/50 mt-1">Re-crawl zeliontech.com + import the whitepaper, then generate questions.</div>
      <Btn gold className="w-full mt-3" disabled={busy} onClick={refresh}>{busy ? 'Working…' : '🔄 Refresh KB'}</Btn>
      {res && <div className="text-xs text-white/60 mt-2">Generated: {res.generated} · website chunks: {res.website?.chunks}</div>}
    </Card>
  )
}
