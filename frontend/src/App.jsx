import { useState } from 'react'
import './App.css'
import ChatForm from './components/ChatForm'
import ClubCard from './components/ClubCard'
import CalendarBar from './components/CalendarBar'
import { postChat, postResearch } from './api'

export default function App() {
  const [chatLoading, setChatLoading] = useState(false)
  const [chatError, setChatError] = useState(null)
  const [matches, setMatches] = useState([])
  const [resumeProfile, setResumeProfile] = useState(null)

  // Keyed by website_url: { loading, result, error }
  const [research, setResearch] = useState({})
  // Keyed by website_url -> { [fieldKey]: boolean }
  const [selections, setSelections] = useState({})
  const [calendarStatus, setCalendarStatus] = useState(null)

  async function handleChatSubmit(message, resumeFile) {
    setChatLoading(true)
    setChatError(null)
    setCalendarStatus(null)
    try {
      const data = await postChat(message, resumeFile)
      setMatches(data.matches)
      setResumeProfile(data.resume_profile)
      setResearch({})
      setSelections({})
    } catch (err) {
      setChatError(err.message)
    } finally {
      setChatLoading(false)
    }
  }

  async function handleGetInfo(websiteUrl) {
    setResearch((prev) => ({ ...prev, [websiteUrl]: { loading: true, result: null, error: null } }))
    try {
      const result = await postResearch(websiteUrl)
      setResearch((prev) => ({ ...prev, [websiteUrl]: { loading: false, result, error: null } }))
    } catch (err) {
      setResearch((prev) => ({
        ...prev,
        [websiteUrl]: { loading: false, result: null, error: err.message },
      }))
    }
  }

  function handleToggleSelection(websiteUrl, fieldKey) {
    setSelections((prev) => ({
      ...prev,
      [websiteUrl]: {
        ...prev[websiteUrl],
        [fieldKey]: !prev[websiteUrl]?.[fieldKey],
      },
    }))
  }

  const selectedCount = Object.values(selections).reduce(
    (total, fields) => total + Object.values(fields).filter(Boolean).length,
    0,
  )

  function handleAddToCalendar() {
    // Stub - Step 7 wires this to real Google Calendar OAuth + event
    // creation. For now this just confirms the selection flow works.
    setCalendarStatus(
      `Google Calendar isn't connected yet (that's Step 7) — ${selectedCount} event${
        selectedCount === 1 ? '' : 's'
      } would have been added.`,
    )
  }

  return (
    <div className="app">
      <header>
        <h1>Cornell Club Matching Agent</h1>
        <p className="tagline">Tell us what you're looking for — we'll match you to real clubs.</p>
      </header>

      <ChatForm onSubmit={handleChatSubmit} loading={chatLoading} />

      {chatError && <p className="error-banner">{chatError}</p>}

      {resumeProfile && resumeProfile.error && (
        <p className="error-banner">Resume couldn't be read: {resumeProfile.error}</p>
      )}

      {matches.length > 0 && (
        <section className="results">
          {matches.map((club, index) => (
            <ClubCard
              key={club.website_url}
              club={club}
              index={index}
              researchState={research[club.website_url]}
              selections={selections[club.website_url] || {}}
              onGetInfo={() => handleGetInfo(club.website_url)}
              onToggleSelection={(fieldKey) => handleToggleSelection(club.website_url, fieldKey)}
            />
          ))}
        </section>
      )}

      <CalendarBar
        selectedCount={selectedCount}
        onAddToCalendar={handleAddToCalendar}
        statusMessage={calendarStatus}
      />
    </div>
  )
}
