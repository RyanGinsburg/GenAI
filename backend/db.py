"""SQLite storage for accounts and saved clubs.

Explicit, discussed exception to CLAUDE.md's "JSON files only, no full
database (for MVP)" rule: passwords and a per-user saved-clubs list are
exactly the kind of data that gets risky on hand-written JSON files (a
concurrent signup/save can corrupt a file with no locking). SQLite is
still "just a local file" (data/app.db) but gives real transactions.

This module owns the connection and raw CRUD only - no validation, no
password hashing, no business rules (those live in services/accounts.py
and services/auth.py). saved_clubs is deliberately denormalized: it
stores only (user_id, website_url), not club details - full club info is
looked up from data/clubs_filtered.json at read time (see
services/saved_clubs.py) so there's one source of truth for club data.

saved_chats is NOT denormalized the same way, deliberately: a saved chat
is a point-in-time match result (the specific clubs, scores, and
categorization at the moment that search ran), which can't be
regenerated later from club data alone - re-running matching on the same
profile isn't guaranteed to reproduce the same result if club data or the
matching algorithm changes since. So the full profile/groups JSON is
stored directly (see services/saved_chats.py). This does mean per-user
storage grows faster than saved_clubs does; acceptable at this app's
local-SQLite scale, same risk tolerance already accepted for the
saved_clubs SQLite-over-JSON deviation above - worth revisiting with a
cleanup/expiry policy if that ever changes.

google_calendar_tokens stores one row per user (user_id is the primary
key, not a separate id) - a student connects at most one Google account
for Calendar. See services/calendar_sync.py for the OAuth flow that
populates/refreshes it; this module just stores whatever it's handed.
"""

from __future__ import annotations

import sqlite3

from backend.paths import DATA_DIR, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS saved_clubs (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    website_url TEXT NOT NULL,
    saved_at    TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, website_url)
);

CREATE INDEX IF NOT EXISTS idx_saved_clubs_user_id ON saved_clubs(user_id);

CREATE TABLE IF NOT EXISTS saved_chats (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label        TEXT NOT NULL,
    profile_json TEXT NOT NULL,
    groups_json  TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_saved_chats_user_id ON saved_chats(user_id);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    used_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);

CREATE TABLE IF NOT EXISTS google_calendar_tokens (
    user_id       INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    access_token  TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at    TEXT NOT NULL
);
"""

# Sign-up via Google has no password to hash. This fixed sentinel is stored
# in password_hash instead of a real hash - it doesn't match the
# self-describing "pbkdf2_sha256$<iter>$<salt>$<hash>" format services/
# auth.py's verify_password() expects, so a password-login attempt on a
# Google-only account fails that split() cleanly (returns False) rather
# than raising. reset_password() overwrites this with a real hash the first
# time a Google-only user sets a password.
GOOGLE_OAUTH_SENTINEL = "google_oauth_no_password"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables/indexes if they don't already exist. Safe to call on
    every process start (idempotent)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(SCHEMA)

        # google_id was added after the original users table - ADD COLUMN
        # isn't covered by "IF NOT EXISTS" the way CREATE TABLE/INDEX are,
        # so guard it with an explicit existence check to keep init_db()
        # idempotent. SQLite can't add a UNIQUE constraint via ADD COLUMN,
        # so uniqueness is enforced by a separate partial index instead
        # (partial so multiple password-only accounts, which have no
        # google_id, don't collide on NULL).
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        if "google_id" not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN google_id TEXT")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id "
            "ON users(google_id) WHERE google_id IS NOT NULL"
        )


def create_user(name: str, email: str, password_hash: str) -> int:
    """Insert a new user. Raises sqlite3.IntegrityError if email is already
    registered - callers (accounts.py) should catch that and translate it
    into a clean user-facing error."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash),
        )
        return cur.lastrowid


def get_user_by_email(email: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_user_by_google_id(google_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE google_id = ?", (google_id,)).fetchone()
        return dict(row) if row else None


def create_google_user(name: str, email: str, google_id: str) -> int:
    """Insert a new Google-only account (password_hash = the sentinel, not
    a real hash - see GOOGLE_OAUTH_SENTINEL above). Raises
    sqlite3.IntegrityError on a duplicate email or google_id."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash, google_id) VALUES (?, ?, ?, ?)",
            (name, email, GOOGLE_OAUTH_SENTINEL, google_id),
        )
        return cur.lastrowid


def link_google_id_to_user(user_id: int, google_id: str) -> None:
    """Attach a google_id to an existing (password-based) account, e.g.
    when a Google sign-in's verified email matches an existing account."""
    with _connect() as conn:
        conn.execute("UPDATE users SET google_id = ? WHERE id = ?", (google_id, user_id))


def update_user_password(user_id: int, password_hash: str) -> None:
    """Overwrites password_hash - used both for a normal password reset
    and for a Google-only account (sentinel password_hash) setting its
    first real password."""
    with _connect() as conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))


def create_password_reset_token(token: str, user_id: int, expires_at: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO password_reset_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at),
        )


def get_password_reset_token(token: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM password_reset_tokens WHERE token = ?", (token,)
        ).fetchone()
        return dict(row) if row else None


def mark_password_reset_token_used(token: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE password_reset_tokens SET used_at = datetime('now') WHERE token = ?",
            (token,),
        )


def add_saved_club(user_id: int, website_url: str) -> None:
    """Idempotent - saving an already-saved club is a no-op, not an error."""
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO saved_clubs (user_id, website_url) VALUES (?, ?)",
            (user_id, website_url),
        )


def remove_saved_club(user_id: int, website_url: str) -> None:
    with _connect() as conn:
        conn.execute(
            "DELETE FROM saved_clubs WHERE user_id = ? AND website_url = ?",
            (user_id, website_url),
        )


def list_saved_clubs(user_id: int) -> list[dict]:
    """Returns [{"website_url": ..., "saved_at": ...}, ...], most recently
    saved first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT website_url, saved_at FROM saved_clubs WHERE user_id = ? ORDER BY saved_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def add_saved_chat(user_id: int, label: str, profile_json: str, groups_json: str) -> int:
    """Insert a new saved chat. Unlike add_saved_club there's no natural
    composite key to dedupe on - every save is a new row. Returns the new
    row's id."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO saved_chats (user_id, label, profile_json, groups_json) VALUES (?, ?, ?, ?)",
            (user_id, label, profile_json, groups_json),
        )
        return cur.lastrowid


def remove_saved_chat(user_id: int, chat_id: int) -> None:
    """Scoped by user_id too, so one user can't delete another's row by
    guessing an id."""
    with _connect() as conn:
        conn.execute(
            "DELETE FROM saved_chats WHERE user_id = ? AND id = ?",
            (user_id, chat_id),
        )


def list_saved_chats(user_id: int) -> list[dict]:
    """Returns [{"id", "label", "created_at"}, ...], most recently saved
    first - deliberately omits the heavy profile_json/groups_json blobs;
    fetch those only on open via get_saved_chat(). Ties on created_at
    (only second-resolution) break by id DESC, so two saves within the
    same second still come back in actual insertion order."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, label, created_at FROM saved_chats WHERE user_id = ? "
            "ORDER BY created_at DESC, id DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_saved_chat(user_id: int, chat_id: int) -> dict | None:
    """Full row (including profile_json/groups_json), or None if not
    found or not owned by user_id."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM saved_chats WHERE user_id = ? AND id = ?",
            (user_id, chat_id),
        ).fetchone()
        return dict(row) if row else None


def upsert_google_calendar_tokens(
    user_id: int, access_token: str, refresh_token: str, expires_at: str
) -> None:
    """Insert or overwrite this user's stored Calendar OAuth tokens - called
    both right after the initial connect and after every access-token
    refresh. Google's refresh response often omits a new refresh_token
    (the existing one is still valid); it's the caller's job (see
    services/calendar_sync.py) to pass through the existing refresh_token
    unchanged in that case rather than overwrite it with a blank value -
    this function just stores whatever it's given verbatim."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO google_calendar_tokens (user_id, access_token, refresh_token, expires_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                expires_at = excluded.expires_at
            """,
            (user_id, access_token, refresh_token, expires_at),
        )


def get_google_calendar_tokens(user_id: int) -> dict | None:
    """Returns {"user_id", "access_token", "refresh_token", "expires_at"},
    or None if this user has never connected Google Calendar."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM google_calendar_tokens WHERE user_id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None


def delete_google_calendar_tokens(user_id: int) -> None:
    """No route calls this yet (no "disconnect" UI) - included for CRUD
    symmetry with the rest of this module, ready for that later."""
    with _connect() as conn:
        conn.execute("DELETE FROM google_calendar_tokens WHERE user_id = ?", (user_id,))


if __name__ == "__main__":
    init_db()
    print(f"Initialized {DB_PATH}")
    with _connect() as conn:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print("Tables:", [t["name"] for t in tables])
