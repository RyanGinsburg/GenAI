import { useEffect, useState } from 'react'
import ClubCard from './ClubCard'

// groups: {"Professional": [...], "Social/Fun": [...], "Community Service": [...]},
// only non-empty categories present (see categorize.py's group_clubs_by_category).
// Mirrors categorize.py's CATEGORY_ORDER - not exposed over the wire, so kept in
// sync here by hand.
const CATEGORY_ORDER = ['Professional', 'Cultural/Affinity', 'Social/Fun', 'Community Service']

// profile is optional (only present for a live chat result or a reopened
// saved chat that has one) - used only to infer which tab to default to.
function computeDefaultTab(profile, groups, presentCategories) {
  const vibe = profile?.vibe
  if (vibe === 'professional') {
    return presentCategories.includes('Professional') ? 'Professional' : 'All'
  }
  if (vibe === 'social') {
    return presentCategories.includes('Social/Fun') ? 'Social/Fun' : 'All'
  }
  // "both" or unset/null: default to whichever of Professional/Social-Fun
  // has more results (the larger bucket reads as the "primary" one); an
  // exact tie (including neither present) defaults to "All" since neither
  // side is more primary than the other.
  const profLen = groups['Professional']?.length || 0
  const socialLen = groups['Social/Fun']?.length || 0
  if (profLen === socialLen) return 'All'
  return profLen > socialLen ? 'Professional' : 'Social/Fun'
}

function computeSecondaryBadge(defaultTab, groups) {
  if (defaultTab !== 'Professional' && defaultTab !== 'Social/Fun') return null
  const other = defaultTab === 'Professional' ? 'Social/Fun' : 'Professional'
  return groups[other]?.length ? other : null
}

export default function MatchResults({ groups, profile, research, selections, onGetInfo, onToggleSelection, savedUrls, onToggleSave }) {
  const presentCategories = CATEGORY_ORDER.filter((c) => groups?.[c]?.length)
  const tabs = ['All', ...presentCategories]

  const [activeTab, setActiveTab] = useState(() => computeDefaultTab(profile, groups || {}, presentCategories))

  // Recompute the default whenever a brand-new result set arrives (a new
  // search, a refine, or a reopened saved chat) rather than only on mount.
  useEffect(() => {
    setActiveTab(computeDefaultTab(profile, groups || {}, presentCategories))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [groups])

  if (presentCategories.length === 0) {
    return <p className="research-status">No matches found. Try a new search with different interests.</p>
  }

  const secondaryBadge = computeSecondaryBadge(activeTab, groups)
  const categoriesToShow = activeTab === 'All' ? presentCategories : [activeTab]

  return (
    <div>
      <div className="match-results__tabs">
        {tabs.map((tab) => (
          <button
            key={tab}
            type="button"
            aria-current={activeTab === tab ? 'true' : undefined}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
            {tab === secondaryBadge && <span className="match-results__badge">✨</span>}
          </button>
        ))}
      </div>

      {categoriesToShow.map((category) => (
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
    </div>
  )
}
