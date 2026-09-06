const SECTIONS = [
  { key: 'chat', label: 'Chat' },
  { key: 'browse', label: 'Browse Clubs' },
  { key: 'my-clubs', label: 'My Clubs' },
]

export default function NavBar({ activeSection, onSectionChange, user, onLoginClick, onLogout }) {
  return (
    <header className="nav-bar">
      <h1 className="nav-bar__title">Cornell Clubs</h1>
      <nav className="nav-bar__tabs">
        {SECTIONS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            aria-current={activeSection === key ? 'page' : undefined}
            onClick={() => onSectionChange(key)}
          >
            {label}
          </button>
        ))}
      </nav>
      <div className="nav-bar__auth">
        {user ? (
          <>
            <span className="nav-bar__greeting">Hi, {user.name.split(' ')[0]}</span>
            <button type="button" className="nav-bar__link-button" onClick={onLogout}>
              Log out
            </button>
          </>
        ) : (
          <button type="button" className="nav-bar__link-button" onClick={onLoginClick}>
            Log in
          </button>
        )}
      </div>
    </header>
  )
}
