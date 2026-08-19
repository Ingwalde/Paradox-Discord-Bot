"""One-off migration: add expression indexes for the search queries in main.py.

main.py opens its databases read-only (mode=ro) by design, so it cannot create
these itself. Run this script once per database after pulling new data:

    python scripts/add_search_indexes.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent.parent / "databases"

STATEMENTS = [
    (
        "CREATE INDEX IF NOT EXISTS idx_pages_norm_title "
        "ON Pages (LOWER(REPLACE(title, '_', ' ')))"
    ),
    (
        "CREATE INDEX IF NOT EXISTS idx_redirects_norm_title "
        "ON Redirects (LOWER(REPLACE(redirect_title, '_', ' ')))"
    ),
]


def add_indexes(db_file: Path) -> None:
    conn = sqlite3.connect(db_file)
    try:
        for statement in STATEMENTS:
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    db_files = sorted(DB_DIR.glob("*.db"))
    if not db_files:
        print(f"No .db files found in {DB_DIR}", file=sys.stderr)
        raise SystemExit(1)
    for db_file in db_files:
        add_indexes(db_file)
        print(f"Indexed {db_file}")


if __name__ == "__main__":
    main()
