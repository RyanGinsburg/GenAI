const SECTIONS = [
  { key: 'chat', label: 'Chat' },
  { key: 'browse', label: 'Browse Clubs' },
  { key: 'my-clubs', label: 'My Clubs' },
]

export default function NavBar({ activeSection, onSectionChange, user, onLoginClick, onLogout, onTitleClick }) {
  return (
    <header className="nav-bar">
      <button type="button" className="nav-bar__title" onClick={onTitleClick}>
        <img className="nav-bar__logo" src="/logo.png" alt="" />
        Cornell Clubs
      </button>
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
