import { useState } from 'react'

export default function ChatForm({ onSubmit, loading }) {
  const [message, setMessage] = useState('')
  const [resumeFile, setResumeFile] = useState(null)

  function handleSubmit(e) {
    e.preventDefault()
    if (!message.trim() || loading) return
    onSubmit(message, resumeFile)
  }

  return (
    <form className="chat-form" onSubmit={handleSubmit}>
      <textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="What kind of clubs are you looking for? e.g. &quot;low time commitment sustainability clubs&quot; or &quot;something in quant finance&quot;"
        rows={3}
      />
      <div className="chat-form__row">
        <label className="chat-form__file">
          {resumeFile ? resumeFile.name : 'Attach resume (optional, PDF)'}
          <input
            type="file"
            accept="application/pdf"
            onChange={(e) => setResumeFile(e.target.files[0] || null)}
          />
        </label>
        <button type="submit" disabled={loading || !message.trim()}>
          {loading ? 'Searching…' : 'Find clubs'}
        </button>
      </div>
    </form>
  )
}
