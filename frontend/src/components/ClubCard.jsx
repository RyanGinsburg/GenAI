// One club: its basic info, an optional match score, a Save button, a
// "Get info" button that triggers POST /research on demand (never
// automatic), and, once researched, checkboxes for whichever dated fields
// were actually found (the calendar-eligible ones) plus a plain link for
// coffee_chat_link (a booking link, not something with its own start/end
// time). Shared across the Chat results, Browse Clubs, and My Clubs
// sections - showScore hides the match-score badge where it isn't
// meaningful (Browse, My Clubs).

const EVENT_FIELDS = [
  { key: 'application_deadline', label: 'Application deadline' },
  { key: 'next_meeting', label: 'Next meeting' },
  { key: 'info_session', label: 'Info session' },
]

function ResearchPanel({ state, selections, onToggleSelection }) {
  if (state.loading) {
    return (
      <div className="research-status">
        <span className="spinner" aria-hidden="true" />
        <span>Checking their website...</span>
      </div>
    )
  }
  if (state.error) {
    return <p className="research-status research-status--error">{state.error}</p>
  }
  if (!state.result) {
    return null
  }

  const { result } = state
  const foundEventFields = EVENT_FIELDS.filter((f) => result[f.key])

  if (result.not_found) {
    return (
      <p className="research-status">
        {result.error
          ? "Couldn't check this site right now. Try visiting it directly."
          : "This club hasn't posted concrete deadline/meeting info on their site yet."}
      </p>
    )
  }

  return (
    <div className="research-panel">
      {foundEventFields.map(({ key, label }) => (
        <label key={key} className="event-checkbox">
          <input
            type="checkbox"
            checked={!!selections[key]}
            onChange={() => onToggleSelection(key)}
          />
          <span>
            <strong>{label}:</strong> {result[key]}
          </span>
        </label>
      ))}
      {result.coffee_chat_link && (
        <a
          className="coffee-chat-link"
          href={result.coffee_chat_link}
          target="_blank"
          rel="noreferrer"
        >
          ☕ Coffee chat sign-up
        </a>
      )}
      {foundEventFields.length === 0 && !result.coffee_chat_link && (
        <p className="research-status">No concrete details found.</p>
      )}
    </div>
  )
}

export default function ClubCard({
  club,
  researchState,
  selections,
  onGetInfo,
  onToggleSelection,
  showScore = true,
  saved = false,
  onToggleSave,
}) {
  const hasResearched = !!researchState

  return (
    <article className="club-card">
      <div className="club-card__header">
        <h3>{club.name}</h3>
        {showScore && typeof club.score === 'number' && (
          <span className="club-card__score" title="Match score">
            {Math.round(club.score * 100)}%
          </span>
        )}
      </div>
      <p className="club-card__category">{club.category}</p>
      {club.description && <p className="club-card__description">{club.description}</p>}
      <div className="club-card__footer">
        <a href={club.website_url} target="_blank" rel="noreferrer">
          Visit site
        </a>
        <div className="club-card__actions">
          {onToggleSave && (
            <button
              type="button"
              className={saved ? 'club-card__save club-card__save--active' : 'club-card__save'}
              onClick={onToggleSave}
            >
              {saved ? 'Saved' : 'Save'}
            </button>
          )}
          {!hasResearched && (
            <button type="button" onClick={onGetInfo}>
              Get info
            </button>
          )}
        </div>
      </div>
      {hasResearched && (
        <ResearchPanel
          state={researchState}
          selections={selections}
          onToggleSelection={onToggleSelection}
        />
      )}
    </article>
  )
}
