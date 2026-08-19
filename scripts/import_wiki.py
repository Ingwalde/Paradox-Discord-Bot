"""Populate a game's SQLite database from its paradoxwikis.com MediaWiki API.

No API key needed. Usage:

    python scripts/import_wiki.py eu5

Writes databases/<game_key>.db with Pages and Redirects tables, matching the
schema paradox_bot.search expects (see databases/eu4.db for reference). Safe
to re-run: recreates both tables from scratch each time, so it always
reflects current wiki state.

To add a new game: add it to GAMES in paradox_bot/games.py (with its
wiki_subdomain), then run this script.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from paradox_bot.games import GAMES

DB_DIR = Path(__file__).resolve().parent.parent / "databases"

USER_AGENT = "paradox-discord-bot-wiki-import/1.0"
REQUEST_DELAY_SECONDS = 0.2
# Characters MediaWiki leaves literal in page URLs (observed in existing
# databases, e.g. "Holy_Roman_Empire_(mechanic)"); everything else is
# percent-encoded so titles with &, #, % etc. don't break the URL.
URL_SAFE_CHARS = "()_,'!.-/:"


def _api_get(subdomain: str, params: dict) -> dict:
    url = f"https://{subdomain}.paradoxwikis.com/api.php?" + urllib.parse.urlencode(
        {**params, "format": "json"}
    )
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def _page_url(subdomain: str, title: str, fragment: str = "") -> str:
    path = urllib.parse.quote(title.replace(" ", "_"), safe=URL_SAFE_CHARS)
    url = f"https://{subdomain}.paradoxwikis.com/{path}"
    if fragment:
        url += "#" + urllib.parse.quote(fragment.replace(" ", "_"), safe=URL_SAFE_CHARS)
    return url


def _redirect_index_url(subdomain: str, title: str) -> str:
    encoded_title = urllib.parse.quote(title.replace(" ", "_"), safe=URL_SAFE_CHARS)
    return f"https://{subdomain}.paradoxwikis.com/index.php?title={encoded_title}&redirect=no"


def fetch_pages(subdomain: str) -> list[tuple[str, str, str]]:
    """Return (title, url, image_url) for every non-redirect content page."""
    pages: list[tuple[str, str, str]] = []
    params: dict = {
        "action": "query",
        "generator": "allpages",
        "gapfilterredir": "nonredirects",
        "gaplimit": "500",
        "prop": "pageimages",
        "piprop": "original",
    }
    while True:
        data = _api_get(subdomain, params)
        for page in data.get("query", {}).get("pages", {}).values():
            title = page["title"]
            image = page.get("original", {}).get("source", "")
            pages.append((title, _page_url(subdomain, title), image))
        cont = data.get("continue")
        if not cont:
            break
        params.update(cont)
        time.sleep(REQUEST_DELAY_SECONDS)
    return pages


def fetch_redirects(subdomain: str) -> list[tuple[str, str, str]]:
    """Return (redirect_title, redirect_url, target_page_url) for every redirect.

    list=allredirects gives the redirect's own page id ("fromid") and its
    TARGET title/fragment -- not the redirect's own title -- so a second,
    batched query resolves those ids back to titles.
    """
    raw: list[tuple[int, str, str]] = []  # (fromid, target_title, fragment)
    params: dict = {
        "action": "query",
        "list": "allredirects",
        "arlimit": "500",
        "arprop": "ids|title|fragment",
    }
    while True:
        data = _api_get(subdomain, params)
        for entry in data.get("query", {}).get("allredirects", []):
            raw.append((entry["fromid"], entry["title"], entry.get("fragment", "")))
        cont = data.get("continue")
        if not cont:
            break
        params.update(cont)
        time.sleep(REQUEST_DELAY_SECONDS)

    titles_by_id: dict[int, str] = {}
    ids = [fromid for fromid, _, _ in raw]
    for i in range(0, len(ids), 50):
        chunk = ids[i : i + 50]
        data = _api_get(
            subdomain, {"action": "query", "pageids": "|".join(str(x) for x in chunk)}
        )
        for page in data.get("query", {}).get("pages", {}).values():
            if "missing" not in page:
                titles_by_id[page["pageid"]] = page["title"]
        time.sleep(REQUEST_DELAY_SECONDS)

    redirects = []
    for fromid, target_title, fragment in raw:
        redirect_title = titles_by_id.get(fromid)
        if redirect_title is None:
            continue
        redirects.append(
            (
                redirect_title,
                _redirect_index_url(subdomain, redirect_title),
                _page_url(subdomain, target_title, fragment),
            )
        )
    return redirects


def write_database(
    game_key: str,
    pages: list[tuple[str, str, str]],
    redirects: list[tuple[str, str, str]],
) -> None:
    db_file = DB_DIR / f"{game_key}.db"
    conn = sqlite3.connect(db_file)
    try:
        conn.executescript(
            """
            DROP TABLE IF EXISTS Pages;
            DROP TABLE IF EXISTS Redirects;
            CREATE TABLE Pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT UNIQUE,
                url TEXT UNIQUE,
                image_url TEXT,
                lang TEXT
            );
            CREATE TABLE Redirects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                redirect_title TEXT,
                redirect_url TEXT,
                target_page_url TEXT,
                FOREIGN KEY(target_page_url) REFERENCES Pages(url)
            );
            """
        )
        conn.executemany(
            "INSERT OR IGNORE INTO Pages (title, url, image_url) VALUES (?, ?, ?)", pages
        )
        conn.executemany(
            "INSERT INTO Redirects (redirect_title, redirect_url, target_page_url) "
            "VALUES (?, ?, ?)",
            redirects,
        )
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game_key", choices=sorted(GAMES))
    args = parser.parse_args()

    subdomain = GAMES[args.game_key].wiki_subdomain
    print(f"Fetching pages from {subdomain}.paradoxwikis.com ...")
    pages = fetch_pages(subdomain)
    print(f"  {len(pages)} pages")
    print(f"Fetching redirects from {subdomain}.paradoxwikis.com ...")
    redirects = fetch_redirects(subdomain)
    print(f"  {len(redirects)} redirects")

    DB_DIR.mkdir(exist_ok=True)
    write_database(args.game_key, pages, redirects)
    print(f"Wrote {DB_DIR / (args.game_key + '.db')}")


if __name__ == "__main__":
    main()
