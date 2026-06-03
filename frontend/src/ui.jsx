import React from 'react'

// The uploaded ZelionTech gold Z. Drop a /public/zelion-logo.png to override the SVG.
const LOGO_SRC = `${import.meta.env.BASE_URL}zelion-logo.svg`

export const Logo = ({ size = 56, glow = true }) => (
  <img src={LOGO_SRC} width={size} height={size} alt="Zelion" draggable="false"
    className={glow ? 'drop-shadow-[0_0_16px_rgba(245,197,66,0.7)] select-none' : 'select-none'} />
)

export const Card = ({ children, className = '' }) => (
  <div className={`card fade-in ${className}`}>{children}</div>
)

export const Btn = ({ gold, children, className = '', ...p }) => (
  <button className={`${gold ? 'btn-gold' : 'btn-ghost'} ${className}`} {...p}>{children}</button>
)

export const Stat = ({ label, value, accent }) => (
  <div className="flex-1 text-center">
    <div className="label">{label}</div>
    <div className={`text-lg font-extrabold ${accent ? 'text-gold' : 'text-white'}`}>{value}</div>
  </div>
)

export const Chip = ({ children, tone = 'gold' }) => {
  const tones = {
    gold: 'bg-gold/15 text-gold',
    green: 'bg-emerald-500/15 text-emerald-300',
    red: 'bg-rose-500/15 text-rose-300',
    gray: 'bg-white/10 text-white/60',
    blue: 'bg-sky-500/15 text-sky-300',
  }
  return <span className={`chip ${tones[tone]}`}>{children}</span>
}

export const Spinner = () => (
  <div className="flex justify-center py-10">
    <div className="w-7 h-7 rounded-full border-2 border-gold/30 border-t-gold animate-spin" />
  </div>
)

export const Progress = ({ value, max }) => {
  const pct = max ? Math.min(100, Math.round((value / max) * 100)) : 0
  return (
    <div className="h-2 rounded-full bg-white/10 overflow-hidden">
      <div className="h-full bg-gold glow" style={{ width: pct + '%' }} />
    </div>
  )
}

// Profile badge: the gold Z + a quiz rank.
export const RankBadge = ({ rank, sub }) => (
  <div className="flex items-center gap-3">
    <Logo size={44} />
    <div>
      <div className="font-extrabold text-gold leading-tight">{rank}</div>
      {sub && <div className="text-[11px] text-white/45">{sub}</div>}
    </div>
  </div>
)

export const Toast = ({ msg, tone = 'gold' }) =>
  msg ? (
    <div className="fixed left-1/2 -translate-x-1/2 bottom-24 z-50 fade-in">
      <div className={`px-4 py-2 rounded-xl text-sm font-semibold ${tone === 'red' ? 'bg-rose-600' : 'bg-gold text-black'}`}>
        {msg}
      </div>
    </div>
  ) : null

export const Splash = () => (
  <div className="min-h-full flex flex-col items-center justify-center gap-5 fade-in">
    <div className="animate-pulse"><Logo size={96} /></div>
    <div className="text-center">
      <div className="text-2xl font-black tracking-wide">ZELION <span className="text-gold">REACTOR</span></div>
      <div className="text-xs text-white/40 mt-1">Infrastructure-grade energy game</div>
    </div>
    <div className="w-7 h-7 rounded-full border-2 border-gold/30 border-t-gold animate-spin" />
  </div>
)
