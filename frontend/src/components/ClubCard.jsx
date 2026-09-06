// One matched club: its basic info, a "Get info" button that triggers
// POST /research on demand (never automatic - see CLAUDE.md Step 5), and,
// once researched, checkboxes for whichever dated fields were actually
// found (the calendar-eligible ones) plus a plain link for coffee_chat_link
// (a booking link, not something with its own start/end time).
//
// Visual concept: the results grid reads as a pinboard of flyers, not a
// feed - each card sits at a small resting tilt and straightens/lifts on
// hover. TILT_SEQUENCE gives each card a stable-but-varied angle (not a
// mechanical left/right alternation) based on its position in the grid.

const EVENT_FIELDS = [
  { key: 'application_deadline', label: 'Application deadline' },
  { key: 'next_meeting', label: 'Next meeting' },
  { key: 'info_session', label: 'Info session' },
]

const TILT_SEQUENCE = [-1.1, 0.6, -0.3, 0.9, -0.7, 0.4, -0.2, 1.0]

function ResearchPanel({ state, selections, onToggleSelection }) {
  if (state.loading) {
    return <p className="research-status">Checking their website…</p>
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
          ? "Couldn't check this site right now — try visiting it directly."
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

export default function ClubCard({ club, index, researchState, selections, onGetInfo, onToggleSelection }) {
  const hasResearched = !!researchState
  const tilt = TILT_SEQUENCE[index % TILT_SEQUENCE.length]

  return (
    <article className="club-card" style={{ '--tilt': `${tilt}deg` }}>
      <div className="club-card__header">
        <h3>{club.name}</h3>
        <span className="club-card__score" title="Match score">
          {Math.round(club.score * 100)}%
        </span>
      </div>
      <p className="club-card__category">{club.category}</p>
      {club.description && <p className="club-card__description">{club.description}</p>}
      <div className="club-card__footer">
        <a href={club.website_url} target="_blank" rel="noreferrer">
          Visit site
        </a>
        {!hasResearched && (
          <button type="button" onClick={onGetInfo}>
            Get info
          </button>
        )}
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
