// Confirmation step before anything would touch a real calendar. The
// button is a stub for now (per BUILD_PROMPTS.md Step 6 - "can be a stub/
// fake button for now, we'll wire real calendar auth in the next step") -
// clicking it never contacts Google; it just confirms what would be added,
// so the shape of the "review before adding" flow is real even though the
// backend behind it (Step 7) isn't built yet.

export default function CalendarBar({ selectedCount, onAddToCalendar, statusMessage }) {
  if (selectedCount === 0 && !statusMessage) return null

  return (
    <div className="calendar-bar">
      <span>
        {selectedCount} event{selectedCount === 1 ? '' : 's'} selected
      </span>
      <button type="button" disabled={selectedCount === 0} onClick={onAddToCalendar}>
        Add to Google Calendar
      </button>
      {statusMessage && <p className="calendar-bar__status">{statusMessage}</p>}
    </div>
  )
}
