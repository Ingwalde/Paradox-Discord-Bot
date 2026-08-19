"""Search-result feedback: in-memory reaction context plus persisted votes."""

from __future__ import annotations

import sqlite3
from typing import Any

from paradox_bot.config import settings

FEEDBACK_EMOJIS = {"✅": "up", "❌": "down"}

# Correlates a search-result message id back to what was searched, so the
# ✅/❌ reaction handler can log which query/result the feedback is about.
# In-memory and capped: feedback on a message from before the last restart,
# or the oldest entries once the cap is hit, is simply not attributable.
MAX_SEARCH_CONTEXT = 1000
_search_context: dict[int, dict[str, Any]] = {}


def _remember_search_context(message_id: int, **context: Any) -> None:
    _search_context[message_id] = context
    while len(_search_context) > MAX_SEARCH_CONTEXT:
        _search_context.pop(next(iter(_search_context)))


def _pluralize_results(count: int) -> str:
    """Ukrainian plural of 'результат' for the given count."""
    if count % 10 == 1 and count % 100 != 11:
        return "результат"
    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return "результати"
    return "результатів"


def record_feedback(
    user_id: str,
    game_key: str,
    query: str,
    vote: str,
    top_title: str | None,
    top_url: str | None,
) -> None:
    """Persist a ✅/❌ vote. Blocking; call via asyncio.to_thread."""
    conn = sqlite3.connect(settings.feedback_db_path, timeout=settings.db_timeout_seconds)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS Feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                game_key TEXT,
                query TEXT,
                vote TEXT,
                top_title TEXT,
                top_url TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "INSERT INTO Feedback (user_id, game_key, query, vote, top_title, top_url) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, game_key, query, vote, top_title, top_url),
        )
        conn.commit()
    finally:
        conn.close()


def recent_feedback(limit: int = 10) -> list[dict[str, Any]]:
    """Return the most recent votes, newest first. Blocking; call via asyncio.to_thread."""
    conn = sqlite3.connect(settings.feedback_db_path, timeout=settings.db_timeout_seconds)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT user_id, game_key, query, vote, top_title, top_url, timestamp "
            "FROM Feedback ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        # Feedback table doesn't exist yet: nothing has ever been recorded.
        return []
    finally:
        conn.close()
