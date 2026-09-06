import { useEffect, useState } from 'react'
import ClubCard from './ClubCard'
import LoadingIndicator from './LoadingIndicator'
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
        <p>Log in to see the clubs you've saved.</p>
        <button type="button" onClick={onRequireLogin}>
          Log in
        </button>
      </div>
    )
  }

  if (loading) return <LoadingIndicator label="Loading your clubs..." />
  if (error) return <p className="error-banner">{error}</p>
  if (clubs.length === 0) {
    return <p className="research-status">You haven't saved any clubs yet. Save one from Chat or Browse Clubs.</p>
  }

  return (
    <div className="results">
      {clubs.map((club) => (
        <ClubCard
          key={club.website_url}
          club={club}
          showScore={false}
          researchState={research[club.website_url]}
          selections={selections[club.website_url] || {}}
          onGetInfo={() => onGetInfo(club.website_url)}
          onToggleSelection={(fieldKey) => onToggleSelection(club.website_url, fieldKey)}
          saved
          onToggleSave={() => onToggleSave(club.website_url)}
        />
      ))}
    </div>
  )
}
