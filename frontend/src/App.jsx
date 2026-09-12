import { useEffect, useState } from 'react'
import './App.css'
import NavBar from './components/NavBar'
import AuthModal from './components/AuthModal'
import ResetPasswordModal from './components/ResetPasswordModal'
import LandingPage from './components/LandingPage'
import ChatSection from './components/ChatSection'
import BrowseClubs from './components/BrowseClubs'
import MyClubs from './components/MyClubs'
import CalendarBar from './components/CalendarBar'
import { EVENT_FIELDS, infoSessionLabel } from './components/ClubCard'
import {
  addEventsToCalendar,
  getCalendarConnectUrl,
  getCalendarStatus,
  getSavedClubs,
  postResearch,
  saveClub,
  unsaveClub,
} from './api'

export default function App() {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem('ccma_user')
    return stored ? JSON.parse(stored) : null
  })
  const [token, setToken] = useState(() => localStorage.getItem('ccma_token'))
  const [activeSection, setActiveSection] = useState('browse')
  const [authModalOpen, setAuthModalOpen] = useState(false)
  const [authModalMode, setAuthModalMode] = useState('login')
  const [savedUrls, setSavedUrls] = useState(new Set())

  // Landing page: shown before the main app whenever there's no stored
  // token. Intentionally simple - a guest sees it again on every fresh
  // page load (no separate "already chose guest" flag); only a stored
  // token skips it automatically.
  const [hasEnteredApp, setHasEnteredApp] = useState(() => !!localStorage.getItem('ccma_token'))

  function openAuthModal(mode) {
    setAuthModalMode(mode)
    setAuthModalOpen(true)
  }

  // A password-reset email link lands here as ?resetToken=... - there's no
  // router, so this is read straight off the URL on mount, same "modal,
  // not a route" pattern as authModalOpen. Cleared only on the modal's
  // success/close (not immediately on open) so a page refresh mid-flow
  // re-derives it from the still-present URL param instead of stranding
  // the user.
  const [resetToken, setResetToken] = useState(null)

  useEffect(() => {
    const fromUrl = new URLSearchParams(window.location.search).get('resetToken')
    if (fromUrl) setResetToken(fromUrl)
  }, [])

  function clearResetToken() {
    setResetToken(null)
    window.history.replaceState({}, '', window.location.pathname)
  }

  // Shared across Chat/Browse/My Clubs since ClubCard is reused everywhere.
  const [research, setResearch] = useState({})
  const [selections, setSelections] = useState({})
  // selections/research are keyed by website_url only - neither carries a
  // club's display name, which a calendar event's summary needs. This is a
  // parallel lookup populated alongside selections (see
  // handleToggleSelection) rather than restructuring either of those two
  // states, which are consumed as-is across Chat/Browse/My Clubs.
  const [clubNames, setClubNames] = useState({})
  const [calendarStatus, setCalendarStatus] = useState(null)
  const [calendarConnected, setCalendarConnected] = useState(false)
  const [calendarResults, setCalendarResults] = useState(null)

  useEffect(() => {
    if (!token) return
    getSavedClubs(token)
      .then((data) => setSavedUrls(new Set(data.clubs.map((c) => c.website_url))))
      .catch(() => {
        // Token expired/invalid - clear it quietly rather than looping errors.
        handleLogout()
      })
    getCalendarStatus(token)
      .then((data) => setCalendarConnected(data.connected))
      .catch(() => setCalendarConnected(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  // A Google Calendar OAuth redirect lands here as ?calendarConnected=true|
  // false - same "no client-side router, read straight off the URL" pattern
  // as resetToken above. Unlike resetToken there's no modal to wait on: the
  // whole connect flow already completed server-side by the time this page
  // reloads, so the query param is cleared immediately and this just reports
  // the outcome.
  useEffect(() => {
    const flag = new URLSearchParams(window.location.search).get('calendarConnected')
    if (!flag) return
    window.history.replaceState({}, '', window.location.pathname)
    if (flag === 'true') {
      setCalendarConnected(true)
      setCalendarStatus('Google Calendar connected!')
    } else {
      setCalendarStatus("Couldn't connect Google Calendar. Please try again.")
    }
  }, [])

  // Neither calendarStatus (e.g. "Google Calendar connected!") nor
  // calendarResults (the per-event added/skipped/failed list) used to clear
  // themselves, so CalendarBar stayed pinned at the bottom of every page
  // indefinitely - even showing "0 events selected" once a successful add
  // reset `selections`. Auto-dismiss either one a few seconds after it's
  // set; handleDismissCalendarNotice below covers the earlier manual case.
  useEffect(() => {
    if (!calendarStatus && !calendarResults) return
    const timer = setTimeout(() => {
      setCalendarStatus(null)
      setCalendarResults(null)
    }, 6000)
    return () => clearTimeout(timer)
  }, [calendarStatus, calendarResults])

  function handleDismissCalendarNotice() {
    setCalendarStatus(null)
    setCalendarResults(null)
  }

  function handleAuthSuccess(newUser, newToken) {
    setUser(newUser)
    setToken(newToken)
    localStorage.setItem('ccma_user', JSON.stringify(newUser))
    localStorage.setItem('ccma_token', newToken)
    setAuthModalOpen(false)
    setHasEnteredApp(true)
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

  function handleToggleSelection(websiteUrl, fieldKey, clubName) {
    setSelections((prev) => ({
      ...prev,
      [websiteUrl]: {
        ...prev[websiteUrl],
        [fieldKey]: !prev[websiteUrl]?.[fieldKey],
      },
    }))
    if (clubName) {
      setClubNames((prev) => ({ ...prev, [websiteUrl]: clubName }))
    }
  }

  const selectedCount = Object.values(selections).reduce(
    (total, fields) => total + Object.values(fields).filter(Boolean).length,
    0,
  )

  async function handleAddToCalendar() {
    if (!token) {
      setAuthModalOpen(true)
      return
    }

    if (!calendarConnected) {
      // One-time connect step - a real browser redirect, so this can't
      // carry the Authorization header itself. getCalendarConnectUrl()
      // does the authenticated part (proving who's connecting) via
      // fetch() first; window.location.href is a plain, header-less
      // navigation to the URL that call returns.
      try {
        const { authorization_url: authorizationUrl } = await getCalendarConnectUrl(token)
        window.location.href = authorizationUrl
      } catch (err) {
        setCalendarStatus(err.message)
      }
      return
    }

    const events = []
    for (const [websiteUrl, fields] of Object.entries(selections)) {
      for (const [fieldKey, checked] of Object.entries(fields)) {
        if (!checked) continue
        const result = research[websiteUrl]?.result

        // info_session is list-valued (a club can hold more than one
        // session) - ClubCard renders one checkbox per entry keyed
        // "info_session:<index>" instead of the flat EVENT_FIELDS mapping.
        const infoSessionMatch = /^info_session:(\d+)$/.exec(fieldKey)
        let rawText
        let fieldLabel
        if (infoSessionMatch) {
          const index = Number(infoSessionMatch[1])
          const sessions = result?.info_session
          rawText = Array.isArray(sessions) ? sessions[index] : undefined
          fieldLabel = infoSessionLabel(index, Array.isArray(sessions) ? sessions.length : 1)
        } else {
          rawText = result?.[fieldKey]
          fieldLabel = EVENT_FIELDS.find((f) => f.key === fieldKey)?.label || fieldKey
        }
        if (!rawText) continue // shouldn't happen - a checkbox only exists for a found field

        events.push({
          website_url: websiteUrl,
          club_name: clubNames[websiteUrl] || websiteUrl,
          field_key: fieldKey,
          field_label: fieldLabel,
          raw_text: rawText,
        })
      }
    }

    try {
      const data = await addEventsToCalendar(token, events)
      if (data.notConnected) {
        // Status went stale since the last check (e.g. access was
        // revoked mid-session) - fall back to the connect flow again.
        setCalendarConnected(false)
        setCalendarStatus('Google Calendar needs to be reconnected.')
        return
      }
      setCalendarResults(data.results)
      setCalendarStatus(null)
      setSelections({}) // clear checkboxes so a re-click doesn't re-add the same events
    } catch (err) {
      setCalendarStatus(err.message)
    }
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
      {hasEnteredApp ? (
        <>
          <NavBar
            activeSection={activeSection}
            onSectionChange={setActiveSection}
            user={user}
            onLoginClick={() => openAuthModal('login')}
            onLogout={handleLogout}
            onTitleClick={() => setActiveSection('browse')}
          />

          <main className="app__main">
            {activeSection === 'chat' && (
              <ChatSection token={token} onRequireLogin={() => openAuthModal('login')} {...sharedCardProps} />
            )}
            {activeSection === 'browse' && (
              <BrowseClubs onGoToChat={() => setActiveSection('chat')} {...sharedCardProps} />
            )}
            {activeSection === 'my-clubs' && (
              <MyClubs token={token} onRequireLogin={() => openAuthModal('login')} {...sharedCardProps} />
            )}
          </main>

          <CalendarBar
            selectedCount={selectedCount}
            onAddToCalendar={handleAddToCalendar}
            statusMessage={calendarStatus}
            connected={calendarConnected}
            results={calendarResults}
            onDismiss={handleDismissCalendarNotice}
          />
        </>
      ) : (
        <LandingPage
          onContinueAsGuest={() => setHasEnteredApp(true)}
          onLoginClick={() => openAuthModal('login')}
          onCreateAccountClick={() => openAuthModal('register')}
        />
      )}

      {authModalOpen && (
        <AuthModal
          initialMode={authModalMode}
          onClose={() => setAuthModalOpen(false)}
          onAuthSuccess={handleAuthSuccess}
        />
      )}

      {resetToken && (
        <ResetPasswordModal
          token={resetToken}
          onSuccess={(newUser, newToken) => {
            handleAuthSuccess(newUser, newToken)
            clearResetToken()
          }}
          onClose={clearResetToken}
        />
      )}
    </div>
  )
}
