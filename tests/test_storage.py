from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from paradox_bot import storage


@pytest.fixture(autouse=True)
def _clean_cache() -> None:
    storage.reset_schema_cache()


def test_connect_creates_the_schema(tmp_path: Path) -> None:
    conn = storage.connect(tmp_path / "x.db", storage.SEARCH_LOG_SCHEMA)
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    assert "SearchLog" in tables


def test_connect_enables_wal(tmp_path: Path) -> None:
    conn = storage.connect(tmp_path / "x.db", storage.SEARCH_LOG_SCHEMA)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_schema_runs_once_per_file(tmp_path: Path) -> None:
    db = tmp_path / "x.db"
    storage.connect(db, storage.SEARCH_LOG_SCHEMA).close()
    # A second connect must not re-run the DDL; a schema that would fail on a
    # second execution proves it is skipped.
    poisoned = "CREATE TABLE SearchLog (boom INTEGER)"
    storage.connect(db, poisoned).close()


def test_schema_cache_is_per_resolved_path(tmp_path: Path) -> None:
    storage.connect(tmp_path / "a.db", storage.FEEDBACK_SCHEMA).close()
    conn = storage.connect(tmp_path / "b.db", storage.FEEDBACK_SCHEMA)
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    assert "Feedback" in tables


def test_connect_closes_the_connection_when_schema_fails(tmp_path: Path) -> None:
    with pytest.raises(sqlite3.Error):
        storage.connect(tmp_path / "x.db", "THIS IS NOT SQL")
    # A leaked connection would keep the file locked; reopening proves it did not.
    storage.connect(tmp_path / "x.db", storage.SEARCH_LOG_SCHEMA).close()


@pytest.mark.parametrize(
    "schema",
    [storage.UPLOADS_SCHEMA, storage.FEEDBACK_SCHEMA, storage.SEARCH_LOG_SCHEMA],
)
def test_every_schema_is_valid_sql(tmp_path: Path, schema: str) -> None:
    storage.connect(tmp_path / f"{hash(schema)}.db", schema).close()
