import { useState } from 'react'
import ChatAssistant from './ChatAssistant'
import MatchResults from './MatchResults'
import RefineBar from './RefineBar'
import LoadingIndicator from './LoadingIndicator'
import { postMatchingFromProfile, postMatchingRefine, saveChat } from '../api'
import { summarizeProfile } from '../utils/summarizeProfile'

export default function ChatSection({
  research,
  selections,
  onGetInfo,
  onToggleSelection,
  savedUrls,
  onToggleSave,
  token,
  onRequireLogin,
}) {
  const [profile, setProfile] = useState(null)
  const [groups, setGroups] = useState(null)
  const [matchingLoading, setMatchingLoading] = useState(false)
  const [refining, setRefining] = useState(false)
  const [error, setError] = useState(null)
  const [saveChatStatus, setSaveChatStatus] = useState(null) // null | 'saving' | 'saved' | 'error'

  async function handleProfileReady(builtProfile) {
    setProfile(builtProfile)
    setMatchingLoading(true)
    setError(null)
    try {
      const data = await postMatchingFromProfile(builtProfile)
      setGroups(data.groups)
    } catch (err) {
      setError(err.message)
    } finally {
      setMatchingLoading(false)
    }
  }

  async function handleRefine(message) {
    setRefining(true)
    setError(null)
    try {
      const data = await postMatchingRefine(profile, message)
      if (data.error) setError(data.error)
      setProfile(data.profile)
      if (data.groups) setGroups(data.groups)
    } catch (err) {
      setError(err.message)
    } finally {
      setRefining(false)
    }
  }

  function startOver() {
    setProfile(null)
    setGroups(null)
    setError(null)
    setSaveChatStatus(null)
  }

  async function handleSaveChat() {
    if (!token) {
      onRequireLogin()
      return
    }
    setSaveChatStatus('saving')
    try {
      await saveChat(token, profile, groups)
      setSaveChatStatus('saved')
      setTimeout(() => setSaveChatStatus(null), 2500)
    } catch (err) {
      setSaveChatStatus('error')
    }
  }

  if (!profile) {
    return <ChatAssistant onProfileReady={handleProfileReady} />
  }

  if (matchingLoading) {
    return <LoadingIndicator variant="bar" label="Finding your clubs..." />
  }

  return (
    <div>
      <div className="chat-section__results-header">
        <p className="chat-section__profile-summary">Based on: {summarizeProfile(profile)}</p>
        <div className="chat-section__results-actions">
          {groups && (
            <button type="button" onClick={handleSaveChat} disabled={saveChatStatus === 'saving'}>
              {saveChatStatus === 'saved' ? 'Saved!' : saveChatStatus === 'saving' ? 'Saving...' : 'Save chat'}
            </button>
          )}
          <button type="button" onClick={startOver}>
            Start a new search
          </button>
        </div>
      </div>
      {saveChatStatus === 'error' && <p className="error-banner">Could not save this chat. Try again.</p>}

      <RefineBar onSubmit={handleRefine} busy={refining} />
      {refining && <LoadingIndicator label="Updating your results..." />}

      {error && <p className="error-banner">{error}</p>}

      {groups && (
        <MatchResults
          groups={groups}
          profile={profile}
          research={research}
          selections={selections}
          onGetInfo={onGetInfo}
          onToggleSelection={onToggleSelection}
          savedUrls={savedUrls}
          onToggleSave={onToggleSave}
        />
      )}
    </div>
  )
}
