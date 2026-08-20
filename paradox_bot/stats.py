"""Search-frequency tracking for the -trending command."""

from __future__ import annotations

import sqlite3
from typing import Any

from paradox_bot import storage
from paradox_bot.config import settings


def record_search(game_key: str, query: str) -> None:
    """Log a search. Blocking; call via asyncio.to_thread."""
    conn = storage.connect(settings.stats_db_path, storage.SEARCH_LOG_SCHEMA)
    try:
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
    conn = storage.connect(settings.stats_db_path, storage.SEARCH_LOG_SCHEMA)
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
        # Reachable only if the file was removed after this process cached its
        # schema as applied; storage.connect() creates the table otherwise.
        return []
    finally:
        conn.close()
