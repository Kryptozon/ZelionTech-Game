import React, { useEffect, useState, useCallback } from 'react'
import { api } from './api'
import { Logo, Spinner, Toast } from './ui'
import Home from './screens/Home'
import Missions from './screens/Missions'
import Quiz from './screens/Quiz'
import Leaderboard from './screens/Leaderboard'
import Profile from './screens/Profile'
import Admin from './screens/Admin'

const TABS = [
  { id: 'home', label: 'Home', icon: '🏠' },
  { id: 'missions', label: 'Missions', icon: '🎯' },
  { id: 'quiz', label: 'Quiz', icon: '🧠' },
  { id: 'ranks', label: 'Ranks', icon: '🏆' },
  { id: 'profile', label: 'Profile', icon: '👤' },
]

export default function App() {
  const [me, setMe] = useState(null)
  const [tab, setTab] = useState('home')
  const [err, setErr] = useState('')
  const [toast, setToast] = useState(null)

  const refresh = useCallback(async () => {
    try { setMe(await api.me()) } catch (e) { setErr(e.message) }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const flash = (msg, tone) => { setToast({ msg, tone }); setTimeout(() => setToast(null), 1800) }

  if (err) return (
    <Center>
      <Logo />
      <p className="mt-4 text-white/70 text-sm text-center">
        Couldn’t authenticate.<br />Open this from inside Telegram via <b>🎮 Open Zelion Reactor</b>.
      </p>
      <p className="mt-2 text-xs text-rose-400">{err}</p>
    </Center>
  )
  if (!me) return <Center><Spinner /></Center>

  const tabs = me.is_admin ? [...TABS, { id: 'admin', label: 'Admin', icon: '🛡' }] : TABS

  return (
    <div className="max-w-md mx-auto min-h-full pb-24">
      <header className="flex items-center gap-3 px-4 pt-4 pb-2">
        <Logo sm />
        <div>
          <div className="font-extrabold leading-tight">ZELION <span className="text-gold">REACTOR</span></div>
          <div className="text-[11px] text-white/40">Operator @{me.username || me.first_name}</div>
        </div>
      </header>

      <main className="px-4">
        {tab === 'home' && <Home me={me} refresh={refresh} flash={flash} go={setTab} />}
        {tab === 'missions' && <Missions refresh={refresh} flash={flash} />}
        {tab === 'quiz' && <Quiz me={me} refresh={refresh} flash={flash} />}
        {tab === 'ranks' && <Leaderboard />}
        {tab === 'profile' && <Profile />}
        {tab === 'admin' && me.is_admin && <Admin flash={flash} />}
      </main>

      <nav className="fixed bottom-0 left-0 right-0 max-w-md mx-auto bg-ink/95 backdrop-blur border-t border-gold/15">
        <div className="flex">
          {tabs.map((t) => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`flex-1 py-3 text-center text-[11px] font-semibold ${tab === t.id ? 'text-gold' : 'text-white/45'}`}>
              <div className="text-lg">{t.icon}</div>{t.label}
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
