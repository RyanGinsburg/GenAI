"""Shared filesystem paths for the accounts/db layer.

matching.py, resume_parser.py, and research_agent.py each already compute
their own DATA_DIR the same way and aren't touched here - this exists so
the new db.py/accounts.py/saved_clubs.py modules (and main.py) don't each
repeat that computation.
"""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RESUME_DIR = DATA_DIR / "resumes"
DB_PATH = DATA_DIR / "app.db"
