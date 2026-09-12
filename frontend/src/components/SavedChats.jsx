import { useEffect, useState } from 'react'
import MatchResults from './MatchResults'
import LoadingIndicator from './LoadingIndicator'
import { getSavedChats, getSavedChatDetail, removeSavedChat } from '../api'
import { summarizeProfile } from '../utils/summarizeProfile'

// Read-only: reopening a saved chat shows the profile summary + the
// results as they were saved. No refine bar, no resuming the
// conversation - the point is to look back at a past result, not
// continue it.
export default function SavedChats({ token, research, selections, onGetInfo, onToggleSelection, savedUrls, onToggleSave }) {
  const [chats, setChats] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [openChatId, setOpenChatId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  function refreshList() {
    setLoading(true)
    getSavedChats(token)
      .then((data) => setChats(data.chats))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(refreshList, [token])

  function openChat(chatId) {
    setOpenChatId(chatId)
    setDetail(null)
    setDetailLoading(true)
    getSavedChatDetail(token, chatId)
      .then(setDetail)
      .catch((err) => setError(err.message))
      .finally(() => setDetailLoading(false))
  }

  async function deleteChat(chatId) {
    await removeSavedChat(token, chatId)
    if (openChatId === chatId) setOpenChatId(null)
    refreshList()
  }

  if (loading) return <LoadingIndicator label="Loading your saved chats..." />
  if (error) return <p className="error-banner">{error}</p>

  if (openChatId !== null) {
    return (
      <div>
        <button type="button" onClick={() => setOpenChatId(null)}>
          Back to list
        </button>
        {detailLoading || !detail ? (
          <LoadingIndicator label="Loading this chat..." />
        ) : (
          <div className="saved-chats__detail">
            <p className="chat-section__profile-summary">Based on: {summarizeProfile(detail.profile)}</p>
            <MatchResults
              groups={detail.groups}
              profile={detail.profile}
              research={research}
              selections={selections}
              onGetInfo={onGetInfo}
              onToggleSelection={onToggleSelection}
              savedUrls={savedUrls}
              onToggleSave={onToggleSave}
            />
          </div>
        )}
      </div>
    )
  }

  if (chats.length === 0) {
    return <p className="research-status">You haven't saved any chats yet. Save one from Chat once you have results.</p>
  }

  return (
    <ul className="saved-chats__list">
      {chats.map((chat) => (
        <li key={chat.id} className="saved-chats__item">
          <div>
            <p className="saved-chats__label">{chat.label}</p>
            <p className="saved-chats__date">{chat.created_at}</p>
          </div>
          <div className="saved-chats__actions">
            <button type="button" onClick={() => openChat(chat.id)}>
              View
            </button>
            <button type="button" onClick={() => deleteChat(chat.id)}>
              Delete
            </button>
          </div>
        </li>
      ))}
    </ul>
  )
}
