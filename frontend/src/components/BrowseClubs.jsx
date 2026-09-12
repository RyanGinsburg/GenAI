import { useEffect, useState } from 'react'
import ClubCard from './ClubCard'
import LoadingIndicator from './LoadingIndicator'
import { browseClubs, aiSearchClubs } from '../api'

const CATEGORIES = ['All', 'Professional', 'Cultural/Affinity', 'Social/Fun', 'Community Service']

export default function BrowseClubs({
  research,
  selections,
  onGetInfo,
  onToggleSelection,
  savedUrls,
  onToggleSave,
  onGoToChat,
}) {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('All')
  const [page, setPage] = useState(1)
  const [clubs, setClubs] = useState([])
  const [total, setTotal] = useState(0)
  const [pageSize, setPageSize] = useState(24)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // AI ("search by meaning") search - a separate, submit-triggered mode
  // that replaces the plain paginated grid above while active, since a
  // semantic query is a deliberate action (and a bit slower) rather than
  // cheap live-typing substring filtering.
  const [aiInput, setAiInput] = useState('')
  const [aiQuery, setAiQuery] = useState(null) // the last submitted query, or null when inactive
  const [aiResults, setAiResults] = useState([])
  const [aiLoading, setAiLoading] = useState(false)
  const [aiError, setAiError] = useState(null)
  const aiActive = aiQuery !== null

  useEffect(() => {
    setPage(1)
  }, [query, category])

  useEffect(() => {
    if (aiActive) return // plain browsing is paused while an AI search is active
    let cancelled = false
    setLoading(true)
    const timeoutId = setTimeout(async () => {
      try {
        const data = await browseClubs({ search: query, category, page })
        if (cancelled) return
        setClubs(data.clubs)
        setTotal(data.total)
        setPageSize(data.page_size)
        setError(null)
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }, 300)

    return () => {
      cancelled = true
      clearTimeout(timeoutId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, category, page, aiActive])

  async function runAiSearch(q) {
    setAiLoading(true)
    setAiError(null)
    try {
      const data = await aiSearchClubs({ q, category })
      setAiResults(data.clubs)
    } catch (err) {
      setAiError(err.message)
    } finally {
      setAiLoading(false)
    }
  }

  function handleAiSubmit(e) {
    e.preventDefault()
    if (!aiInput.trim()) return
    setAiQuery(aiInput.trim())
    runAiSearch(aiInput.trim())
  }

  function clearAiSearch() {
    setAiQuery(null)
    setAiInput('')
    setAiResults([])
    setAiError(null)
  }

  // Category pills stay live while an AI search is active - switching
  // categories re-runs the same AI query instead of silently going stale.
  useEffect(() => {
    if (aiActive) runAiSearch(aiQuery)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category])

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div>
      <div className="browse-clubs__chat-cta">
        <p className="browse-clubs__chat-cta-text">
          Not sure where to start? Chat with us to get matched.
        </p>
        <button type="button" className="browse-clubs__chat-cta-button" onClick={onGoToChat}>
          Chat with us
        </button>
      </div>

      <div className="browse-clubs__filters">
        <input
          type="text"
          placeholder="Search clubs..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={aiActive}
        />
        <form className="browse-clubs__ai-search" onSubmit={handleAiSubmit}>
          <label className="browse-clubs__ai-search-label" htmlFor="ai-search-input">
            Or search by meaning
          </label>
          <div className="browse-clubs__ai-search-row">
            <input
              id="ai-search-input"
              type="text"
              placeholder='e.g. "find my cs clubs"'
              value={aiInput}
              onChange={(e) => setAiInput(e.target.value)}
            />
            <button type="submit" disabled={aiLoading || !aiInput.trim()}>
              Search
            </button>
            {aiActive && (
              <button type="button" onClick={clearAiSearch}>
                Clear AI search
              </button>
            )}
          </div>
        </form>
        <div className="browse-clubs__categories">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              type="button"
              aria-current={category === c ? 'true' : undefined}
              onClick={() => setCategory(c)}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {aiActive ? (
        <>
          {aiError && <p className="error-banner">{aiError}</p>}
          {aiLoading ? (
            <LoadingIndicator label="Searching by meaning..." />
          ) : (
            <>
              <p className="browse-clubs__count">
                {aiResults.length} AI search result{aiResults.length === 1 ? '' : 's'} for &quot;{aiQuery}&quot;
              </p>
              {aiResults.length === 0 ? (
                <p className="research-status">No clubs matched that. Try rephrasing, or clear the AI search.</p>
              ) : (
                <div className="results">
                  {aiResults.map((club) => (
                    <ClubCard
                      key={club.website_url}
                      club={club}
                      showScore
                      researchState={research[club.website_url]}
                      selections={selections[club.website_url] || {}}
                      onGetInfo={() => onGetInfo(club.website_url)}
                      onToggleSelection={(fieldKey) => onToggleSelection(club.website_url, fieldKey)}
                      saved={savedUrls.has(club.website_url)}
                      onToggleSave={() => onToggleSave(club.website_url)}
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </>
      ) : (
        <>
          {error && <p className="error-banner">{error}</p>}

          {loading ? (
            <LoadingIndicator label="Loading clubs..." />
          ) : (
            <>
              <p className="browse-clubs__count">{total} clubs</p>
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
                    saved={savedUrls.has(club.website_url)}
                    onToggleSave={() => onToggleSave(club.website_url)}
                  />
                ))}
              </div>
              {totalPages > 1 && (
                <div className="pagination">
                  <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                    Previous
                  </button>
                  <span>
                    Page {page} of {totalPages}
                  </span>
                  <button type="button" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
