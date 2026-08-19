"""Shared fixtures for the test suite."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture()
def game_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Build a throwaway 'test' game database wired into paradox_bot.search."""
    from paradox_bot.config import settings
    from paradox_bot.games import GAMES, GameInfo

    db_dir = tmp_path / "databases"
    db_dir.mkdir()
    db_file = db_dir / "test.db"

    conn = sqlite3.connect(db_file)
    conn.executescript(
        """
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
    conn.commit()
    conn.close()

    monkeypatch.setattr(settings, "db_dir", db_dir)
    monkeypatch.setitem(
        GAMES,
        "test",
        GameInfo(key="test", name="Test Game", color=0, logo="", wiki_subdomain="test"),
    )
    yield db_file
    del GAMES["test"]


def insert_page(db_file: Path, title: str, url: str, image_url: str = "") -> None:
    conn = sqlite3.connect(db_file)
    try:
        conn.execute(
            "INSERT INTO Pages (title, url, image_url) VALUES (?, ?, ?)",
            (title, url, image_url),
        )
        conn.commit()
    finally:
        conn.close()


def insert_redirect(db_file: Path, redirect_title: str, target_page_url: str) -> None:
    conn = sqlite3.connect(db_file)
    try:
        conn.execute(
            "INSERT INTO Redirects (redirect_title, redirect_url, target_page_url) "
            "VALUES (?, '', ?)",
            (redirect_title, target_page_url),
        )
        conn.commit()
    finally:
        conn.close()
