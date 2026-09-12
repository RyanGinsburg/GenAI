import { useEffect, useState } from 'react'
import ClubCard from './ClubCard'
import LoadingIndicator from './LoadingIndicator'
import SavedChats from './SavedChats'
import { getSavedClubs } from '../api'

export default function MyClubs({
  token,
  onRequireLogin,
  research,
  selections,
  onGetInfo,
  onToggleSelection,
  savedUrls,
  onToggleSave,
}) {
  const [view, setView] = useState('clubs') // 'clubs' | 'chats'
  const [clubs, setClubs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!token) return
    setLoading(true)
    getSavedClubs(token)
      .then((data) => setClubs(data.clubs))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [token, savedUrls])

  if (!token) {
    return (
      <div className="my-clubs__login-prompt">
        <p>Log in to see the clubs and chats you've saved.</p>
        <button type="button" onClick={onRequireLogin}>
          Log in
        </button>
      </div>
    )
  }

  return (
    <div>
      <div className="browse-clubs__categories my-clubs__tabs">
        <button type="button" aria-current={view === 'clubs' ? 'true' : undefined} onClick={() => setView('clubs')}>
          Saved Clubs
        </button>
        <button type="button" aria-current={view === 'chats' ? 'true' : undefined} onClick={() => setView('chats')}>
          Saved Chats
        </button>
      </div>

      {view === 'chats' ? (
        <SavedChats
          token={token}
          research={research}
          selections={selections}
          onGetInfo={onGetInfo}
          onToggleSelection={onToggleSelection}
          savedUrls={savedUrls}
          onToggleSave={onToggleSave}
        />
      ) : loading ? (
        <LoadingIndicator label="Loading your clubs..." />
      ) : error ? (
        <p className="error-banner">{error}</p>
      ) : clubs.length === 0 ? (
        <p className="research-status">You haven't saved any clubs yet. Save one from Chat or Browse Clubs.</p>
      ) : (
        <div className="results">
          {clubs.map((club) => (
            <ClubCard
              key={club.website_url}
              club={club}
              showScore={false}
              researchState={research[club.website_url]}
              selections={selections[club.website_url] || {}}
              onGetInfo={() => onGetInfo(club.website_url)}
              onToggleSelection={(fieldKey) => onToggleSelection(club.website_url, fieldKey, club.name)}
              saved
              onToggleSave={() => onToggleSave(club.website_url)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
