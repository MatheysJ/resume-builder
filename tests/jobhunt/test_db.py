import sqlite3
from contextlib import closing

import pytest

from jobhunt import db


def posting(external_id: str, **fields) -> db.Posting:
    return db.Posting(
        site=fields.pop("site", "linkedin"),
        external_id=external_id,
        url=f"https://example.com/jobs/{external_id}",
        title=fields.pop("title", "Desenvolvedor Back-end"),
        **fields,
    )


def test_connect_applies_every_migration(tmp_path):
    with closing(db.connect(tmp_path / "jobs.db")) as connection:
        (version,) = connection.execute("PRAGMA user_version").fetchone()
        tables = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master")}

    assert version == len(db.MIGRATIONS)
    assert "jobs" in tables


def test_connect_twice_keeps_the_data(tmp_path):
    path = tmp_path / "jobs.db"
    with closing(db.connect(path)) as connection:
        db.add_postings(connection, [posting("1")])

    with closing(db.connect(path)) as connection:
        (count,) = connection.execute("SELECT count(*) FROM jobs").fetchone()

    assert count == 1


def test_add_postings_counts_only_new_ones(tmp_path):
    with closing(db.connect(tmp_path / "jobs.db")) as connection:
        assert db.add_postings(connection, [posting("1"), posting("2")]) == 2
        assert db.add_postings(connection, [posting("2"), posting("3")]) == 1
        assert db.add_postings(connection, [posting("1", site="glassdoor")]) == 1

        query = "SELECT status, found_at FROM jobs WHERE external_id = '3'"
        row = connection.execute(query).fetchone()

    assert row["status"] == "new"
    assert row["found_at"]


def test_dedup_key_ignores_case_accents_and_punctuation():
    a = posting("1", company="Itaú Unibanco", title="Dev Back-End Sênior", location="São Paulo")
    b = posting("2", company="itau unibanco", title="dev back end senior", location="Sao Paulo, ")

    assert a.dedup_key == b.dedup_key == "itau unibanco dev back end senior sao paulo"


def test_newer_database_is_rejected(tmp_path):
    path = tmp_path / "jobs.db"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(f"PRAGMA user_version = {len(db.MIGRATIONS) + 1}")

    with pytest.raises(db.DatabaseError, match="mais nova"):
        db.connect(path)


def test_failed_migration_changes_nothing(tmp_path, monkeypatch):
    broken = (*db.MIGRATIONS, "CREATE TABLE extra (id INTEGER); SELECT * FROM nao_existe;")
    monkeypatch.setattr(db, "MIGRATIONS", broken)
    path = tmp_path / "jobs.db"

    with pytest.raises(sqlite3.OperationalError):
        db.connect(path)

    with closing(sqlite3.connect(path)) as connection:
        (version,) = connection.execute("PRAGMA user_version").fetchone()
        tables = {name for (name,) in connection.execute("SELECT name FROM sqlite_master")}

    assert version == len(broken) - 1
    assert "extra" not in tables
