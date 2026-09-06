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
"""


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


if __name__ == "__main__":
    init_db()
    print(f"Initialized {DB_PATH}")
    with _connect() as conn:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print("Tables:", [t["name"] for t in tables])
