export const tg = window.Telegram?.WebApp

// Pin layout to a STABLE pixel height so the nav never jumps when Telegram's
// iframe viewport oscillates (timers, energy refresh, swipe recalculation).
function setAppHeight(px) {
  if (px && px > 0) document.documentElement.style.setProperty('--app-height', px + 'px')
}

export function initTelegram() {
  if (!tg) {
    setAppHeight(window.innerHeight)
    window.addEventListener('resize', () => setAppHeight(window.innerHeight))
    return
  }
  tg.ready()
  tg.expand()
  // Stop the swipe-to-collapse gesture that causes per-second viewport jitter (Bot API 7.7+).
  try { tg.disableVerticalSwipes && tg.disableVerticalSwipes() } catch (_) {}
  try {
    tg.setHeaderColor('#0a0a0f')
    tg.setBackgroundColor('#0a0a0f')
  } catch (_) {}

  // Use the STABLE height (does not change every second); fall back to viewportHeight.
  const apply = () => setAppHeight(tg.viewportStableHeight || tg.viewportHeight || window.innerHeight)
  apply()
  try {
    tg.onEvent('viewportChanged', (e) => {
      // Only react to stable state changes (real resizes), ignore transient jitter.
      if (!e || e.isStateStable) apply()
    })
  } catch (_) {}
}

export function initData() {
  return tg?.initData || ''
}

export function tgUser() {
  return tg?.initDataUnsafe?.user || null
}

export function hapticOk() { try { tg?.HapticFeedback?.notificationOccurred('success') } catch (_) {} }
export function hapticErr() { try { tg?.HapticFeedback?.notificationOccurred('error') } catch (_) {} }
export function hapticTap() { try { tg?.HapticFeedback?.impactOccurred('light') } catch (_) {} }
