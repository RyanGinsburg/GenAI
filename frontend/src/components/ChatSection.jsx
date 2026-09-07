import { useState } from 'react'
import ChatAssistant from './ChatAssistant'
import MatchResults from './MatchResults'
import RefineBar from './RefineBar'
import LoadingIndicator from './LoadingIndicator'
import { postMatchingFromProfile, postMatchingRefine } from '../api'

function summarizeProfile(profile) {
  const bits = []
  if (!profile) return 'your interests'
  if (profile.major) bits.push(profile.major)
  if (profile.school_or_college) bits.push(profile.school_or_college)
  if (profile.vibe) bits.push(profile.vibe === 'both' ? 'social + professional' : profile.vibe)
  if (profile.activity_level) bits.push(`${profile.activity_level} time commitment`)
  ;(profile.specific_interests_in_mind || []).forEach((p) => bits.push(p))
  ;(profile.hobbies || []).forEach((p) => bits.push(p))
  return bits.join(', ') || 'your interests'
}

export default function ChatSection({ research, selections, onGetInfo, onToggleSelection, savedUrls, onToggleSave }) {
  const [profile, setProfile] = useState(null)
  const [groups, setGroups] = useState(null)
  const [matchingLoading, setMatchingLoading] = useState(false)
  const [refining, setRefining] = useState(false)
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
        <button type="button" onClick={startOver}>
          Start a new search
        </button>
      </div>

      <RefineBar onSubmit={handleRefine} busy={refining} />
      {refining && <LoadingIndicator label="Updating your results..." />}

      {error && <p className="error-banner">{error}</p>}

      {groups && (
        <MatchResults
          groups={groups}
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
