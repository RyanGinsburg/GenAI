// Thin wrappers around backend/main.py's routes. No retries - matches the
// backend's own "keep it simple" scope. Authenticated calls take a token
// and send it as Authorization: Bearer <token>.

const API_BASE = 'http://localhost:8000'

async function asJson(res, label) {
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail || `${label} failed (${res.status})`)
  }
  return res.json()
}

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// --- Auth ---

export async function registerUser(name, email, password) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, email, password }),
  })
  return asJson(res, 'Sign up')
}

export async function loginUser(email, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  return asJson(res, 'Log in')
}

export async function getCurrentUser(token) {
  const res = await fetch(`${API_BASE}/auth/me`, { headers: authHeaders(token) })
  return asJson(res, 'Fetching account')
}

export async function googleSignIn(credential) {
  const res = await fetch(`${API_BASE}/auth/google`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credential }),
  })
  return asJson(res, 'Google sign-in')
}

export async function requestPasswordReset(email) {
  const res = await fetch(`${API_BASE}/auth/forgot-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })
  return asJson(res, 'Requesting password reset')
}

export async function resetPassword(token, newPassword) {
  const res = await fetch(`${API_BASE}/auth/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, new_password: newPassword }),
  })
  return asJson(res, 'Resetting password')
}

// --- Chat / profile-building ---

export async function postChatMessage(history, profile, resumeProfile) {
  const res = await fetch(`${API_BASE}/chat/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ history, profile, resume_profile: resumeProfile }),
  })
  return asJson(res, 'Chat')
}

export async function uploadResume(file) {
  const formData = new FormData()
  formData.append('resume', file)
  const res = await fetch(`${API_BASE}/chat/resume`, { method: 'POST', body: formData })
  return asJson(res, 'Resume upload')
}

// --- Matching ---

export async function postMatchingFromProfile(profile) {
  const res = await fetch(`${API_BASE}/matching/from-profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile }),
  })
  return asJson(res, 'Matching')
}

export async function postMatchingRefine(profile, message) {
  const res = await fetch(`${API_BASE}/matching/refine`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile, message }),
  })
  return asJson(res, 'Refining matches')
}

// --- Research (unchanged route; always an explicit per-club action) ---

export async function postResearch(websiteUrl) {
  const res = await fetch(`${API_BASE}/research`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ website_urls: [websiteUrl] }),
  })
  const data = await asJson(res, 'Research')
  return data.results[0]
}

// --- Saved clubs ("My Clubs") ---

export async function getSavedClubs(token) {
  const res = await fetch(`${API_BASE}/clubs/saved`, { headers: authHeaders(token) })
  return asJson(res, 'Loading saved clubs')
}

export async function saveClub(token, websiteUrl) {
  const res = await fetch(`${API_BASE}/clubs/saved`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({ website_url: websiteUrl }),
  })
  return asJson(res, 'Saving club')
}

export async function unsaveClub(token, websiteUrl) {
  const res = await fetch(`${API_BASE}/clubs/saved/remove`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({ website_url: websiteUrl }),
  })
  return asJson(res, 'Removing club')
}

// --- Saved chats ("My Clubs" -> "Saved Chats") ---

export async function getSavedChats(token) {
  const res = await fetch(`${API_BASE}/chats/saved`, { headers: authHeaders(token) })
  return asJson(res, 'Loading saved chats')
}

export async function getSavedChatDetail(token, chatId) {
  const res = await fetch(`${API_BASE}/chats/saved/${chatId}`, { headers: authHeaders(token) })
  return asJson(res, 'Loading saved chat')
}

export async function saveChat(token, profile, groups, label) {
  const res = await fetch(`${API_BASE}/chats/saved`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({ profile, groups, label }),
  })
  return asJson(res, 'Saving chat')
}

export async function removeSavedChat(token, chatId) {
  const res = await fetch(`${API_BASE}/chats/saved/remove`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({ chat_id: chatId }),
  })
  return asJson(res, 'Removing saved chat')
}

// --- Browse ---

export async function browseClubs({ search = '', category = 'All', page = 1 } = {}) {
  const params = new URLSearchParams({ search, category, page: String(page) })
  const res = await fetch(`${API_BASE}/clubs?${params}`)
  return asJson(res, 'Browsing clubs')
}

export async function aiSearchClubs({ q, category = 'All', topK = 24 } = {}) {
  const params = new URLSearchParams({ q, category, top_k: String(topK) })
  const res = await fetch(`${API_BASE}/clubs/ai-search?${params}`)
  return asJson(res, 'AI search')
}

// --- Google Calendar ---

export async function getCalendarStatus(token) {
  const res = await fetch(`${API_BASE}/calendar/status`, { headers: authHeaders(token) })
  return asJson(res, 'Checking calendar connection')
}

export async function getCalendarConnectUrl(token) {
  const res = await fetch(`${API_BASE}/calendar/connect`, { headers: authHeaders(token) })
  return asJson(res, 'Connecting to Google Calendar')
}

// A 409 means "not connected" - a UI branch App.jsx needs to act on (start
// the connect flow), not a generic error to just display, so it's handled
// here rather than left to asJson's one-size-fits-all Error throw.
export async function addEventsToCalendar(token, events) {
  const res = await fetch(`${API_BASE}/calendar/add-events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({ events }),
  })
  if (res.status === 409) {
    return { notConnected: true }
  }
  return asJson(res, 'Adding to calendar')
}
