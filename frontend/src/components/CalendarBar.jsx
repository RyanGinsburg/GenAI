// Confirmation step before anything touches a real calendar. Clicking "Add
// to Google Calendar" either starts the one-time Google OAuth connect flow
// (a real browser redirect - see App.jsx's handleAddToCalendar) or, once
// connected, POSTs the checked events and reports a per-event outcome here
// (added / skipped because the date/time couldn't be pinned down / failed)
// so nothing is ever silently dropped. A connect/add notification (status
// message or results) auto-dismisses itself after a few seconds (see
// App.jsx) and can also be dismissed immediately via the "x" button, so this
// bar doesn't stay pinned to the bottom of the page indefinitely.

function resultsSummary(results) {
  const added = results.filter((r) => r.status === 'added').length
  const skipped = results.filter((r) => r.status === 'skipped_unparseable').length
  const failed = results.filter((r) => r.status === 'failed').length

  if (added === 0 && skipped === 0 && failed === 0) return null

  const parts = []
  if (added > 0) parts.push(`Added ${added} event${added === 1 ? '' : 's'} to your calendar`)
  if (skipped > 0) parts.push(`${skipped} skipped`)
  if (failed > 0) parts.push(`${failed} failed`)
  return parts.join(', ')
}

export default function CalendarBar({
  selectedCount,
  onAddToCalendar,
  statusMessage,
  connected,
  results,
  onDismiss,
}) {
  if (selectedCount === 0 && !statusMessage && !results) return null

  const summary = results && resultsSummary(results)

  return (
    <div className="calendar-bar">
      <div className="calendar-bar__row">
        <span>
          {selectedCount} event{selectedCount === 1 ? '' : 's'} selected
        </span>
        <button type="button" disabled={selectedCount === 0} onClick={onAddToCalendar}>
          Add to Google Calendar
        </button>
        {(statusMessage || results) && (
          <button
            type="button"
            className="calendar-bar__dismiss"
            onClick={onDismiss}
            aria-label="Dismiss notification"
            title="Dismiss"
          >
            &times;
          </button>
        )}
      </div>
      {!connected && selectedCount > 0 && (
        <p className="calendar-bar__hint">You'll be asked to connect Google Calendar first.</p>
      )}
      {statusMessage && <p className="calendar-bar__status">{statusMessage}</p>}
      {results && (
        <div className="calendar-bar__notification">
          {summary && <p className="calendar-bar__summary">{summary}</p>}
          <ul className="calendar-bar__results">
            {results.map((r) => (
              <li
                key={`${r.website_url}-${r.field_key}`}
                className={`calendar-bar__result calendar-bar__result--${r.status}`}
              >
                {r.status === 'added' && '✓ '}
                {r.status === 'skipped_unparseable' && '⚠ '}
                {r.status === 'failed' && '✗ '}
                {r.message}
                {r.event_link && (
                  <a href={r.event_link} target="_blank" rel="noreferrer">
                    {' '}
                    View
                  </a>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
