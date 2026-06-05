import React, { useEffect, useState } from 'react'
import { api, adminToken } from '../api'
import { Card, Btn, Chip, Spinner, Logo } from '../ui'

export default function Admin({ me, admin, flash }) {
  // The Admin tab is visible to ALL users, but access is gated server-side.
  // admin = /api/admin/me => { is_admin, id, authed }
  const [authed, setAuthed] = useState(!!admin?.authed)
  const [tab, setTab] = useState('puzzles')

  // 1) Not the super-admin Telegram ID -> hard "Restricted Area" (server returns 403 too).
  if (!admin?.is_admin) {
    return (
      <Card className="text-center py-10">
        <div className="text-5xl">🔒</div>
        <div className="font-extrabold mt-3 text-rose-400 text-lg">Restricted Area</div>
        <div className="text-sm text-white/50 mt-1">You do not have permission to access this dashboard.</div>
      </Card>
    )
  }

  // 2) Correct Telegram ID but no valid password token yet -> password prompt.
  if (!authed) return <PasswordGate onPass={() => setAuthed(true)} flash={flash} />

  return (
    <div className="space-y-4">
      <Counters />
      <div className="flex items-center justify-between">
        <div className="text-[10px] text-emerald-400/80">🛡 Admin mode active — ID {admin?.id || 8883747941}</div>
        <button className="text-[10px] text-white/40 underline"
          onClick={() => { adminToken.clear(); setAuthed(false); flash('Locked 🔒') }}>Lock</button>
      </div>
      <div className="flex gap-2 flex-wrap">
        {[['puzzles', 'Puzzles'], ['proofs', 'Missions'], ['questions', 'Quiz'], ['users', 'Users'], ['kb', 'KB']].map(([id, l]) => (
          <button key={id} onClick={() => setTab(id)}
            className={`flex-1 btn ${tab === id ? 'btn-gold' : 'btn-ghost'}`}>{l}</button>
        ))}
      </div>
      {tab === 'proofs' && <Proofs flash={flash} />}
      {tab === 'questions' && <Questions flash={flash} />}
      {tab === 'puzzles' && <Puzzles flash={flash} />}
      {tab === 'users' && <Users flash={flash} />}
      {tab === 'kb' && <KB flash={flash} />}
    </div>
  )
}

function PasswordGate({ onPass, flash }) {
  const [pw, setPw] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async () => {
    if (!pw) return
    setBusy(true)
    try {
      const r = await api.adminLogin(pw)   // server verifies hash + Telegram ID
      adminToken.set(r.token)
      flash('Access granted ✅')
      onPass()
    } catch (e) {
      flash(e.message === 'wrong_password' ? 'Wrong password' : e.message, 'red')
    } finally { setBusy(false) }
  }
  return (
    <Card className="text-center py-8">
      <div className="text-4xl">🛡</div>
      <div className="font-extrabold mt-2">Admin Authentication</div>
      <div className="text-xs text-white/50 mt-1">Enter the admin password to unlock the dashboard.</div>
      <input type="password" value={pw} autoFocus
        onChange={(e) => setPw(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
        placeholder="Password"
        className="w-full mt-4 bg-black/40 border border-gold/20 rounded-xl px-3 py-2 text-sm outline-none text-center" />
      <Btn gold className="w-full mt-3" disabled={busy} onClick={submit}>{busy ? 'Verifying…' : 'Unlock'}</Btn>
    </Card>
  )
}

function Users({ flash }) {
  const [q, setQ] = useState('')
  const [rows, setRows] = useState(null)
  const search = async () => {
    try { setRows((await api.adminUsers(q)).users) } catch (e) { flash(e.message, 'red') }
  }
  useEffect(() => { search() }, [])
  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Telegram ID or username…"
          onKeyDown={(e) => e.key === 'Enter' && search()}
          className="flex-1 bg-black/40 border border-gold/20 rounded-xl px-3 py-2 text-sm outline-none" />
        <Btn gold onClick={search}>Search</Btn>
      </div>
      {!rows ? <Spinner /> : rows.length === 0 ? (
        <Card className="text-center text-white/40">No users found.</Card>
      ) : rows.map((u) => (
        <Card key={u.id}>
          <div className="flex items-center justify-between">
            <div className="font-bold">@{u.username || u.first_name || u.id}</div>
            <Chip tone={u.status === 'banned' ? 'red' : 'green'}>{u.status}</Chip>
          </div>
          <div className="text-[11px] text-white/50 mt-1">
            ID {u.id} · Lv.{u.level} · {Number(u.points).toLocaleString()} ZLN-XP
          </div>
        </Card>
      ))}
    </div>
  )
}

function copy(text, flash) {
  try { navigator.clipboard.writeText(text || ''); flash('Copied ✓') } catch (_) { flash('Copy failed', 'red') }
}

function Puzzles({ flash }) {
  const [rows, setRows] = useState(null)
  const [ov, setOv] = useState(null)
  const [diff, setDiff] = useState('')
  const [open, setOpen] = useState(null)
  const [reveal, setReveal] = useState({})   // per-puzzle: show answer/scripts inline
  const load = () => {
    api.adminPuzzles(diff).then((d) => setRows(d.puzzles)).catch((e) => flash(e.message, 'red'))
    api.puzzleOverview().then(setOv).catch(() => {})
  }
  useEffect(() => { load() }, [diff])

  const act = async (fn, ok) => { try { await fn(); flash(ok); load() } catch (e) { flash(e.message, 'red') } }
  const statusTone = { active: 'green', closed: 'red', skipped: 'gray' }

  if (!rows) return <Spinner />
  return (
    <div className="space-y-3">
      {/* Manual-release overview — only ONE puzzle is ever live; admins release it here. */}
      {ov && (
        <Card>
          <div className="text-sm font-bold">🧩 Puzzle Control</div>
          <div className="text-[11px] text-white/60 mt-1">
            {ov.active_puzzle
              ? <>Live now: <span className="text-emerald-400 font-semibold">#{ov.active_puzzle} {ov.active_title}</span></>
              : <span className="text-amber-400">No puzzle live — waiting for admin to release the next one.</span>}
          </div>
          <div className="flex flex-wrap gap-2 mt-2 text-[10px] text-white/50">
            {Object.entries(ov.by_status || {}).map(([s, c]) => <Chip key={s} tone={statusTone[s] || 'gray'}>{s}: {c}</Chip>)}
            <Chip tone="green">solved: {ov.solved}</Chip>
            <Chip tone="gray">missed: {ov.missed}</Chip>
          </div>
        </Card>
      )}

      <select value={diff} onChange={(e) => setDiff(e.target.value)}
        className="w-full bg-black/40 border border-gold/20 rounded-xl px-2 py-2 text-sm">
        <option value="">All difficulties</option>
        {['easy', 'medium', 'hard', 'legendary'].map((d) => <option key={d} value={d}>{d}</option>)}
      </select>
      <div className="text-[11px] text-white/40">Puzzles NEVER auto-release. Answers/hints never sent to users.</div>
      {rows.slice(0, 80).map((p) => {
        const isLive = ov?.active_puzzle === p.id
        const rv = reveal[p.id]
        return (
        <Card key={p.id}>
          <div className="flex items-center gap-2">
            <Chip tone="gray">{p.difficulty}</Chip>
            <Chip tone={statusTone[p.status] || 'gray'}>{p.status}</Chip>
            {isLive && <Chip tone="green">LIVE</Chip>}
            <div className="flex-1 text-sm font-semibold truncate">#{p.id} {p.title}</div>
            <Chip tone="green">+{p.reward}</Chip>
          </div>
          <div className="text-[11px] text-white/45 mt-1">{p.category} · {p.source_topic}</div>
          <div className="text-[11px] text-white/50 mt-1">Released hints: {p.released_hints}/3 ·
            YT {p.youtube_posted ? '✅' : '⬜'} · TG {p.telegram_posted ? '✅' : '⬜'}</div>

          {/* Manual release / lifecycle controls */}
          <div className="flex gap-2 mt-2">
            {isLive
              ? <Btn className="flex-1" onClick={() => act(() => api.puzzleClose(p.id), 'Closed')}>Close</Btn>
              : <Btn gold className="flex-1" onClick={() => act(() => api.puzzleRelease(p.id), 'Released ✅')}>Release</Btn>}
            <Btn className="flex-1 !bg-rose-600/70" onClick={() => act(() => api.puzzleSkip(p.id), 'Skipped')}>Skip</Btn>
            {p.status === 'skipped' || p.status === 'closed'
              ? <Btn className="flex-1" onClick={() => act(() => api.puzzleReopen(p.id), 'Reopened')}>Reopen</Btn>
              : null}
            <Btn className="flex-1" onClick={() => setOpen(open === p.id ? null : p.id)}>{open === p.id ? '▲' : 'More'}</Btn>
          </div>

          {open === p.id && (
            <div className="mt-2 border-t border-white/10 pt-2 space-y-2">
              <div className="text-[11px] text-white/60">Q: {p.question}</div>

              {/* Answers/walkthrough/scripts live in the dashboard — reveal instantly, no JSON hunting. */}
              <Btn gold className="w-full" onClick={() => setReveal({ ...reveal, [p.id]: !rv })}>
                {rv ? '🙈 Hide answer & scripts' : '👁 View answer / walkthrough / scripts'}
              </Btn>
              {rv && (
                <div className="space-y-1 text-[11px]">
                  <div className="text-gold">🔑 Answer: {p.answer}
                    {p.accepted_variations && <span className="text-white/40"> · also: {p.accepted_variations}</span>}</div>
                  {[['Hint 1', p.hint1], ['Hint 2', p.hint2], ['Hint 3', p.hint3]].map(([l, v]) => v && (
                    <div key={l} className="text-white/60">{l}: {v}</div>
                  ))}
                  {p.explanation && <div className="text-white/60">📘 Explanation: {p.explanation}</div>}
                  {p.walkthrough && p.walkthrough !== p.explanation && <div className="text-white/60">🧭 Walkthrough: {p.walkthrough}</div>}
                  <div className="grid grid-cols-2 gap-1 pt-1">
                    <Btn onClick={() => copy(p.answer, flash)}>Copy Answer</Btn>
                    <Btn onClick={() => copy(p.walkthrough || p.explanation, flash)}>Copy Walkthrough</Btn>
                    <Btn onClick={async () => { try { const s = await api.puzzleScript(p.id); copy(s.youtube_script, flash) } catch (e) { flash(e.message, 'red') } }}>Copy YouTube Script</Btn>
                    <Btn onClick={async () => { try { const s = await api.puzzleScript(p.id); copy(s.tiktok_script || s.youtube_script, flash) } catch (e) { flash(e.message, 'red') } }}>Copy TikTok Script</Btn>
                    <Btn onClick={async () => { try { const s = await api.puzzleTelegram(p.id); copy(s.telegram_post, flash) } catch (e) { flash(e.message, 'red') } }}>Copy TG Post</Btn>
                  </div>
                </div>
              )}

              {/* Hints are only announced in-game; real hints live on YouTube/TikTok. */}
              <div className="text-[10px] text-white/40">Announce a hint release (no hint text shown in-app):</div>
              <div className="grid grid-cols-3 gap-1">
                {[1, 2, 3].map((n) => (
                  <Btn key={n} gold={p.released_hints >= n}
                    onClick={() => act(() => api.puzzleReleaseHint(p.id, n), `Hint ${n} announced`)}>
                    Announce H{n}
                  </Btn>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-1">
                <Btn gold={p.youtube_posted} onClick={() => act(() => api.puzzleMarkPosted(p.id, 'youtube'), 'Marked YT')}>Mark YT Posted</Btn>
                <Btn gold={p.telegram_posted} onClick={() => act(() => api.puzzleMarkPosted(p.id, 'telegram'), 'Marked TG')}>Mark TG Posted</Btn>
              </div>
            </div>
          )}
        </Card>
      )})}
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
