export const tg = window.Telegram?.WebApp

export function initTelegram() {
  if (!tg) return
  tg.ready()
  tg.expand()
  try {
    tg.setHeaderColor('#0a0a0f')
    tg.setBackgroundColor('#0a0a0f')
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
