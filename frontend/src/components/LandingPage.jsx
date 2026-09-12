// Shown before the main app (NavBar + the Chat/Browse/My Clubs sections)
// whenever there's no stored login token - lets a student either sign in
// (or create an account) or just continue as a guest. Chatting and
// browsing stay fully anonymous either way; only saving a club or a chat
// is gated behind an account (see App.jsx's handleToggleSave/handleSaveChat).
export default function LandingPage({ onContinueAsGuest, onLoginClick, onCreateAccountClick }) {
  return (
    <div className="landing-page">
      <div className="landing-page__card">
        <img className="landing-page__logo" src="/logo.png" alt="" />
        <h1 className="landing-page__title">Cornell Clubs</h1>
        <p className="landing-page__subtitle">
          Chat about what you're looking for, or upload your resume, and find student
          organizations at Cornell worth checking out.
        </p>
        <div className="landing-page__actions">
          <button type="button" className="landing-page__primary" onClick={onCreateAccountClick}>
            Create account
          </button>
          <button type="button" className="landing-page__secondary" onClick={onLoginClick}>
            Log in
          </button>
          <button type="button" className="landing-page__guest" onClick={onContinueAsGuest}>
            Continue as guest
          </button>
        </div>
      </div>
    </div>
  )
}
