import { initData } from './telegram'

const BASE = '/api'

export const adminToken = {
  get: () => { try { return localStorage.getItem('zln_admin_token') || '' } catch (_) { return '' } },
  set: (t) => { try { localStorage.setItem('zln_admin_token', t) } catch (_) {} },
  clear: () => { try { localStorage.removeItem('zln_admin_token') } catch (_) {} },
}

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      'X-Init-Data': initData(),
      'X-Admin-Token': adminToken.get(),     // attached only when present; verified server-side
      ...(opts.headers || {}),
    },
  })
  if (!res.ok) {
    const e = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error(e.error || 'request_failed')
  }
  return res.json()
}

export const api = {
  me: () => req('/me'),
  claim: () => req('/claim-energy', { method: 'POST' }),

  // tap-to-earn
  tapState: () => req('/tap/state'),
  tap: (taps, nonce) => req('/tap', { method: 'POST', body: JSON.stringify({ taps, nonce }) }),
  upgrades: () => req('/upgrades'),
  buyUpgrade: (code) => req(`/upgrades/${code}/buy`, { method: 'POST' }),
  passive: () => req('/passive'),
  claimPassive: () => req('/passive/claim', { method: 'POST' }),
  tapMissions: () => req('/tap/missions'),
  claimTapMission: (id) => req(`/tap/missions/${id}/claim`, { method: 'POST' }),
  missions: () => req('/missions'),
  completeMission: (id, answer_index) =>
    req(`/missions/${id}/complete`, { method: 'POST', body: JSON.stringify({ answer_index }) }),
  verifyMission: (id) => req(`/missions/${id}/verify`, { method: 'POST' }),
  submitProof: (mission_id, handle, image_base64, mime) =>
    req('/proof/submit', { method: 'POST', body: JSON.stringify({ mission_id, handle, image_base64, mime }) }),
  leaderboard: () => req('/leaderboard'),
  referrals: () => req('/referrals'),
  profile: () => req('/profile'),

  quizNext: () => req('/quiz/next'),
  quizAnswer: (question_id, choice) =>
    req('/quiz/answer', { method: 'POST', body: JSON.stringify({ question_id, choice }) }),
  quizHistory: () => req('/quiz/history'),
  quizDaily: () => req('/quiz/daily'),
  quizRank: () => req('/quiz/rank'),

  // admin
  adminMe: () => req('/admin/me'),
  adminLogin: (password) => req('/admin/login', { method: 'POST', body: JSON.stringify({ password }) }),
  adminUsers: (q = '') => req('/admin/users?q=' + encodeURIComponent(q)),
  adminRanking: () => req('/admin/ranking'),
  adminUserXp: (id, delta) => req(`/admin/users/${id}/xp`, { method: 'POST', body: JSON.stringify({ delta }) }),
  adminUserReset: (id, reason) => req(`/admin/users/${id}/reset`, { method: 'POST', body: JSON.stringify({ reason }) }),
  adminUserBan: (id, banned) => req(`/admin/users/${id}/ban`, { method: 'POST', body: JSON.stringify({ banned }) }),
  puzzleOverview: () => req('/admin/puzzles/overview'),
  puzzleRelease: (id) => req(`/admin/puzzles/${id}/release`, { method: 'POST' }),
  puzzleReopen: (id) => req(`/admin/puzzles/${id}/reopen`, { method: 'POST' }),
  puzzleSave: (data) => req('/admin/puzzles/save', { method: 'POST', body: JSON.stringify(data) }),
  // admin proof dashboard
  adminProofs: (status = 'pending') => req('/admin/proofs?status=' + status),
  adminProofStats: () => req('/admin/proof-stats'),
  adminBanned: () => req('/admin/banned'),
  approveProof: (id) => req(`/admin/proofs/${id}/approve`, { method: 'POST' }),
  rejectProof: (id, reason) =>
    req(`/admin/proofs/${id}/reject`, { method: 'POST', body: JSON.stringify({ reason }) }),
  banProof: (id) => req(`/admin/proofs/${id}/ban`, { method: 'POST' }),
  adminQuestions: (status = 'pending') => req('/admin/questions?status=' + status),
  approveQuestion: (id) => req(`/admin/questions/${id}/approve`, { method: 'POST' }),
  rejectQuestion: (id) => req(`/admin/questions/${id}/reject`, { method: 'POST' }),
  kbRefresh: () => req('/admin/kb/refresh', { method: 'POST' }),

  // tasks / achievements
  tasks: () => req('/tasks'),
  claimTask: (id) => req(`/tasks/${id}/claim`, { method: 'POST' }),

  // puzzles / intelligence
  puzzlesDaily: () => req('/puzzles/daily'),
  puzzleAnswer: (puzzle_id, answer) =>
    req('/puzzles/answer', { method: 'POST', body: JSON.stringify({ puzzle_id, answer }) }),
  puzzlesStatus: () => req('/puzzles/status'),
  puzzlesHistory: () => req('/puzzles/history'),
  puzzlesLeaderboard: (period = 'week') => req('/puzzles/leaderboard?period=' + period),
  adminPuzzles: (difficulty) => req('/admin/puzzles' + (difficulty ? '?difficulty=' + difficulty : '')),
  puzzleHints: (id) => req(`/admin/puzzles/${id}/hints`),
  puzzleScript: (id) => req(`/admin/puzzles/${id}/youtube-script`),
  puzzleTelegram: (id) => req(`/admin/puzzles/${id}/telegram-post`),
  puzzleActivate: (id) => req(`/admin/puzzles/${id}/activate`, { method: 'POST' }),
  puzzleClose: (id) => req(`/admin/puzzles/${id}/deactivate`, { method: 'POST' }),
  puzzleSkip: (id) => req(`/admin/puzzles/${id}/skip`, { method: 'POST' }),
  puzzleReleaseHint: (id, n) => req(`/admin/puzzles/${id}/release-hint`, { method: 'POST', body: JSON.stringify({ n }) }),
  puzzleMarkPosted: (id, platform) => req(`/admin/puzzles/${id}/mark-posted/${platform}`, { method: 'POST' }),

  // community
  community: () => req('/community'),
  claimGroupMission: (id) => req(`/community/missions/${id}/claim`, { method: 'POST' }),
  groupActivity: () => req('/group/activity'),
  groupMissions: () => req('/group/missions'),
  groupLeaderboard: (period = 'today') => req('/group/leaderboard?period=' + period),
  groupDiscussion: () => req('/group/daily-discussion'),
  groupHealth: () => req('/group/health'),
}
