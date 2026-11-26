"""SQLite storage.

The schema evolves through MIGRATIONS, applied in order and tracked by
`PRAGMA user_version`. Never edit a migration that was already released: add a
new one at the end.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from jobhunt.text import normalize

MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE jobs (
        id          INTEGER PRIMARY KEY,
        site        TEXT NOT NULL,
        external_id TEXT NOT NULL,
        url         TEXT NOT NULL,
        title       TEXT NOT NULL,
        company     TEXT NOT NULL DEFAULT '',
        location    TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        dedup_key   TEXT NOT NULL,
        status      TEXT NOT NULL DEFAULT 'new',
        found_at    TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (site, external_id)
    );
    CREATE INDEX jobs_status ON jobs (status);
    CREATE INDEX jobs_dedup_key ON jobs (dedup_key);
    """,
)


class DatabaseError(RuntimeError):
    pass


@dataclass(frozen=True)
class Posting:
    """A job posting as a source returns it, before any filtering or analysis."""

    site: str
    external_id: str
    url: str
    title: str
    company: str = ""
    location: str = ""
    description: str = ""

    @property
    def dedup_key(self) -> str:
        # Same company, title and place on two sites is most likely the same job.
        return normalize(f"{self.company} {self.title} {self.location}")


def connect(path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        _migrate(connection)
    except BaseException:
        connection.close()
        raise
    return connection


def add_postings(connection: sqlite3.Connection, postings: Iterable[Posting]) -> int:
    """Store new postings and return how many were new; repeats are ignored."""
    rows = [
        (p.site, p.external_id, p.url, p.title, p.company, p.location, p.description, p.dedup_key)
        for p in postings
    ]
    with connection:
        cursor = connection.executemany(
            """
            INSERT OR IGNORE INTO jobs
                (site, external_id, url, title, company, location, description, dedup_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    return cursor.rowcount


def _migrate(connection: sqlite3.Connection) -> None:
    (version,) = connection.execute("PRAGMA user_version").fetchone()
    if version > len(MIGRATIONS):
        raise DatabaseError(
            f"o banco está na versão {version}, mais nova que esta versão do jobhunt "
            f"({len(MIGRATIONS)}); atualize o código"
        )
    for number, script in enumerate(MIGRATIONS[version:], start=version + 1):
        # One transaction per migration: the schema and its version change together.
        try:
            connection.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {number};\nCOMMIT;")
        except sqlite3.Error:
            connection.rollback()
            raise
