import { useEffect, useState } from 'react'
import './App.css'
import NavBar from './components/NavBar'
import AuthModal from './components/AuthModal'
import ChatSection from './components/ChatSection'
import BrowseClubs from './components/BrowseClubs'
import MyClubs from './components/MyClubs'
import CalendarBar from './components/CalendarBar'
import { getSavedClubs, postResearch, saveClub, unsaveClub } from './api'

export default function App() {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem('ccma_user')
    return stored ? JSON.parse(stored) : null
  })
  const [token, setToken] = useState(() => localStorage.getItem('ccma_token'))
  const [activeSection, setActiveSection] = useState('chat')
  const [authModalOpen, setAuthModalOpen] = useState(false)
  const [savedUrls, setSavedUrls] = useState(new Set())

  // Shared across Chat/Browse/My Clubs since ClubCard is reused everywhere.
  const [research, setResearch] = useState({})
  const [selections, setSelections] = useState({})
  const [calendarStatus, setCalendarStatus] = useState(null)

  useEffect(() => {
    if (!token) return
    getSavedClubs(token)
      .then((data) => setSavedUrls(new Set(data.clubs.map((c) => c.website_url))))
      .catch(() => {
        // Token expired/invalid - clear it quietly rather than looping errors.
        handleLogout()
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  function handleAuthSuccess(newUser, newToken) {
    setUser(newUser)
    setToken(newToken)
    localStorage.setItem('ccma_user', JSON.stringify(newUser))
    localStorage.setItem('ccma_token', newToken)
    setAuthModalOpen(false)
  }

  function handleLogout() {
    setUser(null)
    setToken(null)
    setSavedUrls(new Set())
    localStorage.removeItem('ccma_user')
    localStorage.removeItem('ccma_token')
  }

  async function handleToggleSave(websiteUrl) {
    if (!token) {
      setAuthModalOpen(true)
      return
    }
    const data = savedUrls.has(websiteUrl)
      ? await unsaveClub(token, websiteUrl)
      : await saveClub(token, websiteUrl)
    setSavedUrls(new Set(data.clubs.map((c) => c.website_url)))
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
      `Google Calendar isn't connected yet. ${selectedCount} event${
        selectedCount === 1 ? '' : 's'
      } would have been added.`,
    )
  }

  const sharedCardProps = {
    research,
    selections,
    onGetInfo: handleGetInfo,
    onToggleSelection: handleToggleSelection,
    savedUrls,
    onToggleSave: handleToggleSave,
  }

  return (
    <div className="app">
      <NavBar
        activeSection={activeSection}
        onSectionChange={setActiveSection}
        user={user}
        onLoginClick={() => setAuthModalOpen(true)}
        onLogout={handleLogout}
      />

      <main className="app__main">
        {activeSection === 'chat' && <ChatSection {...sharedCardProps} />}
        {activeSection === 'browse' && <BrowseClubs {...sharedCardProps} />}
        {activeSection === 'my-clubs' && (
          <MyClubs token={token} onRequireLogin={() => setAuthModalOpen(true)} {...sharedCardProps} />
        )}
      </main>

      {authModalOpen && (
        <AuthModal onClose={() => setAuthModalOpen(false)} onAuthSuccess={handleAuthSuccess} />
      )}

      <CalendarBar
        selectedCount={selectedCount}
        onAddToCalendar={handleAddToCalendar}
        statusMessage={calendarStatus}
      />
    </div>
  )
}
