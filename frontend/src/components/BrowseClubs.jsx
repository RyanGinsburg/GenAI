import { useEffect, useState } from 'react'
import ClubCard from './ClubCard'
import LoadingIndicator from './LoadingIndicator'
import { browseClubs } from '../api'

const CATEGORIES = ['All', 'Professional', 'Cultural/Affinity', 'Social/Fun', 'Community Service']

export default function BrowseClubs({ research, selections, onGetInfo, onToggleSelection, savedUrls, onToggleSave }) {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('All')
  const [page, setPage] = useState(1)
  const [clubs, setClubs] = useState([])
  const [total, setTotal] = useState(0)
  const [pageSize, setPageSize] = useState(24)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setPage(1)
  }, [query, category])

  useEffect(() => {
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
  }, [query, category, page])

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div>
      <div className="browse-clubs__filters">
        <input
          type="text"
          placeholder="Search clubs..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
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
    </div>
  )
}
