from __future__ import annotations

from paradox_bot import stats
from paradox_bot.config import settings


def test_trending_no_table_yet_returns_empty(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "stats_db_path", tmp_path / "stats.db")
    assert stats.trending("eu4") == []


def test_trending_counts_and_orders_by_frequency(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "stats_db_path", tmp_path / "stats.db")
    stats.record_search("eu4", "absolutism")
    stats.record_search("eu4", "absolutism")
    stats.record_search("eu4", "prussia")
    rows = stats.trending("eu4")
    assert rows[0]["query"] == "absolutism"
    assert rows[0]["count"] == 2
    assert rows[1]["query"] == "prussia"
    assert rows[1]["count"] == 1


def test_trending_is_scoped_to_game(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "stats_db_path", tmp_path / "stats.db")
    stats.record_search("eu4", "absolutism")
    stats.record_search("hoi4", "germany")
    rows = stats.trending("eu4")
    assert [r["query"] for r in rows] == ["absolutism"]


def test_trending_respects_limit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "stats_db_path", tmp_path / "stats.db")
    for query in ("a", "b", "c", "d"):
        stats.record_search("eu4", query)
    assert len(stats.trending("eu4", limit=2)) == 2


def test_trending_excludes_old_searches(tmp_path, monkeypatch) -> None:
    db_file = tmp_path / "stats.db"
    monkeypatch.setattr(settings, "stats_db_path", db_file)
    stats.record_search("eu4", "absolutism")

    import sqlite3

    conn = sqlite3.connect(db_file)
    try:
        conn.execute(
            "UPDATE SearchLog SET timestamp = datetime('now', '-30 days') WHERE query = ?",
            ("absolutism",),
        )
        conn.commit()
    finally:
        conn.close()

    assert stats.trending("eu4", days=7) == []
