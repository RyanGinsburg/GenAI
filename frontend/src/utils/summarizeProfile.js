// Shared by ChatSection.jsx (live results) and SavedChats.jsx (reopened
// saved chats) so this one-line "based on..." summary logic isn't
// duplicated across the two places that display a built profile.
export function summarizeProfile(profile) {
  const bits = []
  if (!profile) return 'your interests'
  if (profile.major) bits.push(profile.major)
  if (profile.school_or_college) bits.push(profile.school_or_college)
  if (profile.vibe) bits.push(profile.vibe === 'both' ? 'social + professional' : profile.vibe)
  if (profile.activity_level) bits.push(`${profile.activity_level} time commitment`)
  ;(profile.specific_interests_in_mind || []).forEach((p) => bits.push(p))
  ;(profile.hobbies || []).forEach((p) => bits.push(p))
  return bits.join(', ') || 'your interests'
}
