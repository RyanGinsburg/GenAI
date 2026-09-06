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

// --- Chat / profile-building ---

export async function postChatMessage(history, resumeProfile) {
  const res = await fetch(`${API_BASE}/chat/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ history, resume_profile: resumeProfile }),
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

// --- Browse ---

export async function browseClubs({ search = '', category = 'All', page = 1 } = {}) {
  const params = new URLSearchParams({ search, category, page: String(page) })
  const res = await fetch(`${API_BASE}/clubs?${params}`)
  return asJson(res, 'Browsing clubs')
}
