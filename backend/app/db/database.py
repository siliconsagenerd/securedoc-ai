"""Minimal stdlib SQLite helper.

The audit trail lives in an append-only JSONL file (see audit_service).
This module exists for lightweight structured storage without pulling in an
ORM dependency. It creates the data directory and a connection factory.
"""

import sqlite3
from pathlib import Path

from app.core.config import settings


def _db_path() -> Path:
    # DATABASE_URL looks like "sqlite:///./data/securedoc.db"
    raw = settings.database_url.removeprefix("sqlite:///")
    return Path(raw)


def connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create base tables if they do not exist yet."""
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                action TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
