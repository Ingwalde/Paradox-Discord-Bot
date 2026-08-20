"""Search-frequency tracking for the -trending command."""

from __future__ import annotations

import sqlite3
from typing import Any

from paradox_bot.config import settings


def record_search(game_key: str, query: str) -> None:
    """Log a search. Blocking; call via asyncio.to_thread."""
    conn = sqlite3.connect(settings.stats_db_path, timeout=settings.db_timeout_seconds)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS SearchLog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_key TEXT,
                query TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "INSERT INTO SearchLog (game_key, query) VALUES (?, ?)",
            (game_key, query),
        )
        conn.commit()
    finally:
        conn.close()


def trending(game_key: str, days: int = 7, limit: int = 5) -> list[dict[str, Any]]:
    """Most frequent queries for a game in the last `days` days, newest tie-winner first.

    Blocking; call via asyncio.to_thread.
    """
    conn = sqlite3.connect(settings.stats_db_path, timeout=settings.db_timeout_seconds)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT query, COUNT(*) AS count
            FROM SearchLog
            WHERE game_key = ? AND timestamp >= datetime('now', ? || ' days')
            GROUP BY LOWER(query)
            ORDER BY count DESC, MAX(id) DESC
            LIMIT ?
            """,
            (game_key, -days, limit),
        )
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        # SearchLog table doesn't exist yet: nothing has ever been recorded.
        return []
    finally:
        conn.close()
