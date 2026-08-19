"""SQLite-backed wiki page search: direct titles plus redirects, ranked."""

from __future__ import annotations

import asyncio
import difflib
import sqlite3
from pathlib import Path
from typing import Any

from paradox_bot.config import settings
from paradox_bot.games import GAMES

FUZZY_MATCH_LIMIT = 5
FUZZY_MATCH_CUTOFF = 0.6


def normalize(text: str) -> str:
    """Fold a title or query into the form used for comparison."""
    return text.lower().replace("_", " ").strip()


def escape_like(text: str) -> str:
    """Escape LIKE wildcards so a query of '100%' is matched literally."""
    for char in ("\\", "%", "_"):
        text = text.replace(char, f"\\{char}")
    return text


def db_path(game_key: str) -> Path:
    """Resolve the SQLite file for a game.

    Raises:
        KeyError: If the key is not one of the configured games. Callers only
            ever pass keys from GAMES, so this is a defensive assertion that
            no user input can reach the filesystem.
    """
    if game_key not in GAMES:
        raise KeyError(game_key)
    return settings.db_dir / f"{game_key}.db"


# Redirects.target_page_url may carry a #section fragment (e.g. a patch-notes
# anchor); the base page it points at is everything before that fragment.
_STRIP_FRAGMENT_SQL = (
    "CASE WHEN instr(target_page_url, '#') > 0 "
    "THEN substr(target_page_url, 1, instr(target_page_url, '#') - 1) "
    "ELSE target_page_url END"
)

_SEARCH_SQL = f"""
WITH matches AS (
    SELECT
        title, url, image_url,
        CASE
            WHEN LOWER(REPLACE(title, '_', ' ')) = :exact THEN 0
            WHEN LOWER(REPLACE(title, '_', ' ')) LIKE :prefix ESCAPE '\\' THEN 1
            ELSE 2
        END AS rank
    FROM Pages
    WHERE LOWER(REPLACE(title, '_', ' ')) LIKE :contains ESCAPE '\\'

    UNION ALL

    SELECT
        p.title, r.target_page_url AS url, p.image_url,
        CASE
            WHEN LOWER(REPLACE(r.redirect_title, '_', ' ')) = :exact THEN 0
            WHEN LOWER(REPLACE(r.redirect_title, '_', ' ')) LIKE :prefix ESCAPE '\\' THEN 1
            ELSE 2
        END AS rank
    FROM Redirects r
    JOIN Pages p ON p.url = {_STRIP_FRAGMENT_SQL}
    WHERE LOWER(REPLACE(r.redirect_title, '_', ' ')) LIKE :contains ESCAPE '\\'
)
-- Group by title, not url: several redirects can point at the same page with
-- different #fragments, which must collapse to one result, not repeat it.
-- SQLite's min()/max() extension: bare columns take values from the row that
-- produced the aggregate, so url/image_url come from the best-ranked match.
SELECT title, url, image_url, MIN(rank) AS best_rank
FROM matches
GROUP BY title
ORDER BY best_rank, LENGTH(title), title
LIMIT :limit
"""


def search_pages(
    game_key: str, query: str, limit: int | None = None
) -> list[dict[str, Any]]:
    """Find wiki pages matching a query, via direct titles and redirects.

    Ranking: exact title/redirect match first, then names starting with the
    query, then names containing it elsewhere; ties broken by title length
    (shorter, more likely canonical titles first) then alphabetically.

    Args:
        game_key: One of the keys in GAMES.
        query: Raw user query.
        limit: Maximum number of results (defaults to settings.search_result_limit).

    Returns:
        Page dicts with title, url and image_url keys.

    Raises:
        sqlite3.Error: If the game database is missing or unreadable.
    """
    normalized = normalize(query)
    if not normalized:
        return []
    if limit is None:
        limit = settings.search_result_limit

    escaped = escape_like(normalized)
    path = db_path(game_key)
    # mode=ro means a missing database raises instead of being created silently.
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=settings.db_timeout_seconds)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            _SEARCH_SQL,
            {
                "exact": normalized,
                "prefix": f"{escaped}%",
                "contains": f"%{escaped}%",
                "limit": limit,
            },
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


async def search_pages_async(
    game_key: str, query: str, limit: int | None = None
) -> list[dict[str, Any]]:
    """Run search_pages off the event loop; sqlite3 is blocking."""
    return await asyncio.to_thread(search_pages, game_key, query, limit)


def random_page(game_key: str) -> dict[str, Any] | None:
    """Return a random page for the game, or None if it has no pages yet.

    Raises:
        sqlite3.Error: If the game database is missing or unreadable.
    """
    path = db_path(game_key)
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=settings.db_timeout_seconds)
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT title, url, image_url FROM Pages ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


async def random_page_async(game_key: str) -> dict[str, Any] | None:
    """Run random_page off the event loop; sqlite3 is blocking."""
    return await asyncio.to_thread(random_page, game_key)


def suggest_similar(
    game_key: str, query: str, limit: int = FUZZY_MATCH_LIMIT
) -> list[dict[str, Any]]:
    """Fuzzy "did you mean" suggestions for when search_pages finds nothing.

    Only meant for the empty-result path: it loads every title in the game's
    Pages table and fuzzy-matches with difflib, which is too slow to run on
    every search but cheap for the rare case of zero hits at a few thousand
    rows per game.

    Raises:
        sqlite3.Error: If the game database is missing or unreadable.
    """
    normalized = normalize(query)
    if not normalized:
        return []

    path = db_path(game_key)
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=settings.db_timeout_seconds)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT title, url, image_url FROM Pages").fetchall()
    finally:
        conn.close()

    # If two titles normalize the same, the later one silently wins; harmless
    # for a "did you mean" hint.
    by_normalized = {normalize(row["title"]): row for row in rows}
    close = difflib.get_close_matches(
        normalized, by_normalized.keys(), n=limit, cutoff=FUZZY_MATCH_CUTOFF
    )
    return [dict(by_normalized[title]) for title in close]


async def suggest_similar_async(
    game_key: str, query: str, limit: int = FUZZY_MATCH_LIMIT
) -> list[dict[str, Any]]:
    """Run suggest_similar off the event loop; sqlite3 is blocking."""
    return await asyncio.to_thread(suggest_similar, game_key, query, limit)


def db_stats(game_key: str) -> dict[str, Any] | None:
    """Return {"pages", "redirects", "modified"} for a game's database, or
    None if it doesn't exist yet. Used by the /admin status command.
    """
    path = db_path(game_key)
    if not path.exists():
        return None

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=settings.db_timeout_seconds)
    try:
        pages = conn.execute("SELECT COUNT(*) FROM Pages").fetchone()[0]
        redirects = conn.execute("SELECT COUNT(*) FROM Redirects").fetchone()[0]
    finally:
        conn.close()

    return {
        "pages": pages,
        "redirects": redirects,
        "modified": path.stat().st_mtime,
    }
