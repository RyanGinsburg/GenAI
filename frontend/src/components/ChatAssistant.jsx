import { useState } from 'react'
import LoadingIndicator from './LoadingIndicator'
import { postChatMessage, uploadResume } from '../api'

const GREETING =
  "Hi! I'm here to help you find clubs at Cornell. Tell me a bit about what you're interested in, or attach your resume to get started."

export default function ChatAssistant({ onProfileReady }) {
  const [history, setHistory] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [resumeProfile, setResumeProfile] = useState(null)
  const [resumeName, setResumeName] = useState(null)
  const [resumeUploading, setResumeUploading] = useState(false)
  const [error, setError] = useState(null)

  async function sendTurn(content, currentResumeProfile) {
    const nextHistory = [...history, { role: 'user', content }]
    setHistory(nextHistory)
    setSending(true)
    setError(null)
    try {
      const data = await postChatMessage(nextHistory, currentResumeProfile)
      if (data.error) {
        setError(data.error)
      }
      setHistory([...nextHistory, { role: 'assistant', content: data.reply }])
      if (data.ready_for_matching) {
        onProfileReady(data.profile)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setSending(false)
    }
  }

  const busy = sending || resumeUploading

  function handleSubmit(e) {
    e.preventDefault()
    const message = input.trim()
    if (!message || busy) return
    setInput('')
    sendTurn(message, resumeProfile)
  }

  async function handleResumeChange(e) {
    const file = e.target.files[0]
    if (!file) return
    setResumeUploading(true)
    setError(null)
    try {
      const data = await uploadResume(file)
      setResumeProfile(data.resume_profile)
      setResumeName(file.name)
      if (data.resume_profile?.error) {
        setError(`Resume couldn't be read: ${data.resume_profile.error}`)
      } else {
        await sendTurn('I attached my resume.', data.resume_profile)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setResumeUploading(false)
    }
  }

  return (
    <div className="chat-assistant">
      <div className="chat-log">
        <div className="chat-bubble chat-bubble--assistant">{GREETING}</div>
        {history.map((turn, i) => (
          <div key={i} className={`chat-bubble chat-bubble--${turn.role}`}>
            {turn.content}
          </div>
        ))}
        {resumeUploading && !sending && <LoadingIndicator label="Reading your resume..." />}
        {sending && <LoadingIndicator label="Thinking..." />}
      </div>

      {error && <p className="error-banner">{error}</p>}

      <form className="chat-assistant__form" onSubmit={handleSubmit}>
        <label className="chat-assistant__file">
          {resumeUploading ? 'Uploading...' : resumeName || 'Attach resume'}
          <input type="file" accept="application/pdf" onChange={handleResumeChange} disabled={busy} />
        </label>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your reply..."
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  )
}
