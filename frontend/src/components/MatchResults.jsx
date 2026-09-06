import ClubCard from './ClubCard'

// groups: {"Professional": [...], "Social/Fun": [...], "Community Service": [...]},
// only non-empty categories present (see categorize.py's group_clubs_by_category).
export default function MatchResults({ groups, research, selections, onGetInfo, onToggleSelection, savedUrls, onToggleSave }) {
  const categoryNames = Object.keys(groups || {})

  if (categoryNames.length === 0) {
    return <p className="research-status">No matches found. Try a new search with different interests.</p>
  }

  return (
    <>
      {categoryNames.map((category) => (
        <section key={category} className="category-group">
          <h2 className="category-group__heading">{category}</h2>
          <div className="results">
            {groups[category].map((club) => (
              <ClubCard
                key={club.website_url}
                club={club}
                researchState={research[club.website_url]}
                selections={selections[club.website_url] || {}}
                onGetInfo={() => onGetInfo(club.website_url)}
                onToggleSelection={(fieldKey) => onToggleSelection(club.website_url, fieldKey)}
                saved={savedUrls.has(club.website_url)}
                onToggleSave={() => onToggleSave(club.website_url)}
              />
            ))}
          </div>
        </section>
      ))}
    </>
  )
}
