from __future__ import annotations

import pytest

from paradox_bot import feedback
from paradox_bot.config import settings


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (1, "результат"),
        (21, "результат"),
        (2, "результати"),
        (3, "результати"),
        (4, "результати"),
        (22, "результати"),
        (5, "результатів"),
        (0, "результатів"),
        (11, "результатів"),
        (12, "результатів"),
        (14, "результатів"),
        (111, "результатів"),
    ],
)
def test_pluralize_results(count: int, expected: str) -> None:
    assert feedback._pluralize_results(count) == expected


def test_remember_search_context_stores_by_message_id() -> None:
    feedback._search_context.clear()
    feedback._remember_search_context(
        123, game_key="eu4", query="rome", top_title="Rome", top_url="u"
    )
    assert feedback._search_context[123]["query"] == "rome"


def test_remember_search_context_prunes_oldest_beyond_cap(monkeypatch) -> None:
    feedback._search_context.clear()
    monkeypatch.setattr(feedback, "MAX_SEARCH_CONTEXT", 3)
    for message_id in range(5):
        feedback._remember_search_context(message_id, game_key="eu4", query=str(message_id))
    assert len(feedback._search_context) == 3
    # The three most recently added ids survive; the oldest two are pruned.
    assert set(feedback._search_context) == {2, 3, 4}


def test_record_feedback_round_trips_through_recent_feedback(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "feedback_db_path", tmp_path / "feedback.db")
    feedback.record_feedback("user-1", "eu4", "rome", "up", "Rome", "https://wiki/Rome")
    rows = feedback.recent_feedback()
    assert len(rows) == 1
    assert rows[0]["user_id"] == "user-1"
    assert rows[0]["game_key"] == "eu4"
    assert rows[0]["vote"] == "up"
    assert rows[0]["top_title"] == "Rome"


def test_recent_feedback_orders_newest_first(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "feedback_db_path", tmp_path / "feedback.db")
    feedback.record_feedback("user-1", "eu4", "first", "up", "A", "u")
    feedback.record_feedback("user-1", "eu4", "second", "down", "B", "u")
    rows = feedback.recent_feedback()
    assert [r["query"] for r in rows] == ["second", "first"]


def test_recent_feedback_respects_limit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "feedback_db_path", tmp_path / "feedback.db")
    for i in range(5):
        feedback.record_feedback("user-1", "eu4", str(i), "up", "A", "u")
    assert len(feedback.recent_feedback(limit=2)) == 2


def test_recent_feedback_no_table_yet_returns_empty(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "feedback_db_path", tmp_path / "feedback.db")
    assert feedback.recent_feedback() == []
