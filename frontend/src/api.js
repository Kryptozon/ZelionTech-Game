import { initData } from './telegram'

const BASE = '/api'

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      'X-Init-Data': initData(),
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

  // community
  community: () => req('/community'),
  claimGroupMission: (id) => req(`/community/missions/${id}/claim`, { method: 'POST' }),
}
