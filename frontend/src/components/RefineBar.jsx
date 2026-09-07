import { useState } from 'react'

// Kept alive alongside MatchResults so a student can adjust results
// conversationally ("show me more social ones") instead of restarting the
// whole interview. Mirrors ChatAssistant.jsx's own form/busy-gating
// pattern (that gating was added there to fix a real race-condition bug,
// so the same shape is used here from the start).
export default function RefineBar({ onSubmit, busy }) {
  const [input, setInput] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    const message = input.trim()
    if (!message || busy) return
    setInput('')
    onSubmit(message)
  }

  return (
    <form className="refine-bar" onSubmit={handleSubmit}>
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Refine your results, e.g. &quot;show me more social ones&quot;"
        disabled={busy}
      />
      <button type="submit" disabled={busy || !input.trim()}>
        Update
      </button>
    </form>
  )
}
