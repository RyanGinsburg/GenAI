import { useState } from 'react'
import ChatAssistant from './ChatAssistant'
import MatchResults from './MatchResults'
import LoadingIndicator from './LoadingIndicator'
import { postMatchingFromProfile } from '../api'

export default function ChatSection({ research, selections, onGetInfo, onToggleSelection, savedUrls, onToggleSave }) {
  const [profile, setProfile] = useState(null)
  const [groups, setGroups] = useState(null)
  const [matchingLoading, setMatchingLoading] = useState(false)
  const [error, setError] = useState(null)

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

  function startOver() {
    setProfile(null)
    setGroups(null)
    setError(null)
  }

  if (!profile) {
    return <ChatAssistant onProfileReady={handleProfileReady} />
  }

  if (matchingLoading) {
    return <LoadingIndicator variant="bar" label="Finding your clubs..." />
  }

  if (error) {
    return (
      <div>
        <p className="error-banner">{error}</p>
        <button type="button" onClick={startOver}>
          Start over
        </button>
      </div>
    )
  }

  return (
    <div>
      <div className="chat-section__results-header">
        <p className="chat-section__profile-summary">
          Based on: {profile.interests.join(', ')}
        </p>
        <button type="button" onClick={startOver}>
          Start a new search
        </button>
      </div>
      <MatchResults
        groups={groups}
        research={research}
        selections={selections}
        onGetInfo={onGetInfo}
        onToggleSelection={onToggleSelection}
        savedUrls={savedUrls}
        onToggleSave={onToggleSave}
      />
    </div>
  )
}
