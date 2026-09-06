// Thin wrappers around backend/main.py's two routes. No auth, no retries -
// matches the backend's own "keep it simple" scope for this step.

const API_BASE = 'http://localhost:8000'

export async function postChat(message, resumeFile) {
  const formData = new FormData()
  formData.append('message', message)
  if (resumeFile) formData.append('resume', resumeFile)

  const res = await fetch(`${API_BASE}/chat`, { method: 'POST', body: formData })
  if (!res.ok) throw new Error(`Chat request failed (${res.status})`)
  return res.json()
}

// Research is always an explicit, per-club action from the UI (a "Get info"
// button click) - never called automatically alongside postChat(). See
// CLAUDE.md's Step 5 note on why /chat and /research are kept decoupled.
export async function postResearch(websiteUrl) {
  const res = await fetch(`${API_BASE}/research`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ website_urls: [websiteUrl] }),
  })
  if (!res.ok) throw new Error(`Research request failed (${res.status})`)
  const data = await res.json()
  return data.results[0]
}
