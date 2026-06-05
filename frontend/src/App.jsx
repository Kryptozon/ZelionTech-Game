import React, { useEffect, useState, useCallback } from 'react'
import { api } from './api'
import { Logo, Spinner, Toast, Splash } from './ui'
import Tap from './screens/Tap'
import Lab from './screens/Lab'
import Missions from './screens/Missions'
import Quiz from './screens/Quiz'
import Leaderboard from './screens/Leaderboard'
import Profile from './screens/Profile'
import Community from './screens/Community'
import Intelligence from './screens/Intelligence'
import Tasks from './screens/Tasks'
import Admin from './screens/Admin'

const TABS = [
  { id: 'reactor', label: 'Reactor', icon: '⚛️' },
  { id: 'quiz', label: 'Quiz', icon: '🧠' },
  { id: 'intel', label: 'Intel', icon: '🧩' },
  { id: 'community', label: 'Group', icon: '💬' },
  { id: 'admin', label: 'Admin', icon: '🛡' },   // visible to all; gated inside
]

export default function App() {
  const [me, setMe] = useState(null)
  const [tab, setTab] = useState('reactor')
  const [err, setErr] = useState('')
  const [toast, setToast] = useState(null)
  const [admin, setAdmin] = useState(null)   // { is_admin, id } from /api/admin/me

  const refresh = useCallback(async () => {
    try { setMe(await api.me()) } catch (e) { setErr(e.message) }
  }, [])

  useEffect(() => { refresh() }, [refresh])
  // Server is the source of truth for admin status (frontend never decides).
  useEffect(() => { api.adminMe().then(setAdmin).catch(() => setAdmin({ is_admin: false })) }, [])

  const flash = (msg, tone) => { setToast({ msg, tone }); setTimeout(() => setToast(null), 1800) }

  if (err) return (
    <Center>
      <Logo size={80} />
      <p className="mt-4 text-white/70 text-sm text-center">
        Couldn’t authenticate.<br />Open this from inside Telegram via <b>🎮 Open Zelion Reactor</b>.
      </p>
      <p className="mt-2 text-xs text-rose-400">{err}</p>
    </Center>
  )
  if (!me) return <Center><Splash /></Center>

  const isAdmin = !!admin?.is_admin

  return (
    <div className="app-shell max-w-md mx-auto">
      <header className="app-header flex items-center gap-3 px-4 pt-4 pb-2">
        <Logo size={34} />
        <div className="flex-1">
          <div className="font-extrabold leading-tight">ZELION <span className="text-gold">REACTOR</span></div>
          <div className="text-[11px] text-white/40">Operator @{me.username || me.first_name}</div>
        </div>
        {/* Tap to open Profile (Profile holds the Ranks/Leaderboard link). */}
        <button onClick={() => setTab('profile')} className="text-right">
          <div className="label">Quiz rank</div>
          <div className="text-xs font-bold text-gold">{me.quiz_rank} 👤</div>
        </button>
      </header>

      {isAdmin && (
        <div className="px-4 -mt-1 mb-1 text-[10px] text-emerald-400/80">
          🛡 Admin mode active — ID {admin.id}
        </div>
      )}

      <main className="app-main px-4">
        {tab === 'reactor' && <Tap me={me} refresh={refresh} flash={flash} go={setTab} />}
        {tab === 'lab' && <Lab refresh={refresh} flash={flash} />}
        {tab === 'missions' && <Missions refresh={refresh} flash={flash} />}
        {tab === 'quiz' && <Quiz me={me} refresh={refresh} flash={flash} />}
        {tab === 'intel' && <Intelligence refresh={refresh} flash={flash} />}
        {tab === 'tasks' && <Tasks refresh={refresh} flash={flash} go={setTab} />}
        {tab === 'community' && <Community refresh={refresh} flash={flash} go={setTab} />}
        {tab === 'ranks' && <Leaderboard />}
        {tab === 'profile' && <Profile isAdmin={isAdmin} go={setTab} />}
        {tab === 'admin' && <Admin me={me} admin={admin} flash={flash} />}
      </main>

      <nav className="app-nav">
        <div className="flex max-w-md mx-auto h-[72px] items-center">
          {TABS.map((t) => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`flex-1 text-center text-[11px] font-semibold ${tab === t.id ? 'text-gold' : 'text-white/45'}`}>
              <div className="text-lg leading-none mb-0.5">{t.icon}</div>{t.label}
            </button>
          ))}
        </div>
      </nav>

      <Toast msg={toast?.msg} tone={toast?.tone} />
    </div>
  )
}

const Center = ({ children }) => (
  <div className="min-h-full flex flex-col items-center justify-center px-8">{children}</div>
)
