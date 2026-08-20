from __future__ import annotations

import pytest

from paradox_bot import search
from paradox_bot.config import settings
from tests.conftest import insert_page, insert_redirect


def test_normalize_lowercases_and_folds_underscores() -> None:
    assert search.normalize("  Holy_Roman_Empire  ") == "holy roman empire"


def test_escape_like_escapes_wildcards() -> None:
    assert search.escape_like("100%_done\\") == "100\\%\\_done\\\\"


def test_db_path_known_game() -> None:
    assert search.db_path("eu4") == settings.db_dir / "eu4.db"


def test_db_path_unknown_game_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        search.db_path("not-a-game")


def test_search_pages_exact_match_ranks_first(game_db) -> None:
    insert_page(game_db, "Absolutism", "https://wiki/Absolutism")
    insert_page(game_db, "Age of Absolutism", "https://wiki/Ages#Age_of_Absolutism")
    results = search.search_pages("test", "absolutism")
    assert [r["title"] for r in results][:2] == ["Absolutism", "Age of Absolutism"]


def test_search_pages_prefix_before_contains(game_db) -> None:
    insert_page(game_db, "Trade company", "https://wiki/Trade_company")
    insert_page(game_db, "Merchant trade power", "https://wiki/Merchant_trade_power")
    results = search.search_pages("test", "trade")
    titles = [r["title"] for r in results]
    assert titles.index("Trade company") < titles.index("Merchant trade power")


def test_search_pages_ties_broken_by_title_length(game_db) -> None:
    insert_page(game_db, "Trade league", "https://wiki/Trade_league")
    insert_page(game_db, "Trade", "https://wiki/Trade")
    results = search.search_pages("test", "trade")
    assert [r["title"] for r in results] == ["Trade", "Trade league"]


def test_search_pages_finds_redirect_target(game_db) -> None:
    insert_page(game_db, "Holy Roman Empire (mechanic)", "https://wiki/HRE")
    insert_redirect(game_db, "HRE", "https://wiki/HRE")
    results = search.search_pages("test", "hre")
    assert results[0]["title"] == "Holy Roman Empire (mechanic)"
    assert results[0]["url"] == "https://wiki/HRE"


def test_search_pages_redirect_keeps_fragment_but_resolves_metadata(game_db) -> None:
    insert_page(game_db, "Absolutism", "https://wiki/Absolutism", image_url="https://wiki/img.png")
    insert_redirect(game_db, "Yearly absolutism", "https://wiki/Absolutism#Yearly_absolutism")
    results = search.search_pages("test", "yearly absolutism")
    assert len(results) == 1
    assert results[0]["title"] == "Absolutism"
    assert results[0]["url"] == "https://wiki/Absolutism#Yearly_absolutism"
    assert results[0]["image_url"] == "https://wiki/img.png"


def test_search_pages_dedups_page_hit_via_multiple_fragment_redirects(game_db) -> None:
    insert_page(game_db, "Absolutism", "https://wiki/Absolutism")
    insert_redirect(game_db, "Maximum absolutism", "https://wiki/Absolutism#Max")
    insert_redirect(game_db, "Yearly absolutism", "https://wiki/Absolutism#Yearly")
    results = search.search_pages("test", "absolutism")
    titles = [r["title"] for r in results]
    assert titles.count("Absolutism") == 1


def test_search_pages_empty_query_returns_nothing(game_db) -> None:
    insert_page(game_db, "Absolutism", "https://wiki/Absolutism")
    assert search.search_pages("test", "   ") == []


def test_search_pages_missing_database_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "db_dir", tmp_path)
    with pytest.raises(Exception):  # noqa: B017 - sqlite3.OperationalError via mode=ro
        search.search_pages("eu4", "anything")


def test_suggest_similar_finds_close_typo(game_db) -> None:
    insert_page(game_db, "Absolutism", "https://wiki/Absolutism")
    results = search.suggest_similar("test", "absolutsm")
    assert [r["title"] for r in results] == ["Absolutism"]


def test_suggest_similar_ignores_unrelated_titles(game_db) -> None:
    insert_page(game_db, "Absolutism", "https://wiki/Absolutism")
    insert_page(game_db, "Naval combat", "https://wiki/Naval_combat")
    results = search.suggest_similar("test", "absolutsm")
    assert [r["title"] for r in results] == ["Absolutism"]


def test_suggest_similar_empty_query_returns_nothing(game_db) -> None:
    insert_page(game_db, "Absolutism", "https://wiki/Absolutism")
    assert search.suggest_similar("test", "   ") == []


def test_suggest_similar_no_close_match_returns_nothing(game_db) -> None:
    insert_page(game_db, "Absolutism", "https://wiki/Absolutism")
    assert search.suggest_similar("test", "xyzzy plugh") == []


def test_db_stats_missing_database_returns_none(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "db_dir", tmp_path)
    assert search.db_stats("eu4") is None


def test_db_stats_counts_pages_and_redirects(game_db) -> None:
    insert_page(game_db, "Absolutism", "https://wiki/Absolutism")
    insert_page(game_db, "Trade", "https://wiki/Trade")
    insert_redirect(game_db, "HRE", "https://wiki/HRE")
    stats = search.db_stats("test")
    assert stats is not None
    assert stats["pages"] == 2
    assert stats["redirects"] == 1
    assert stats["modified"] > 0


def test_random_page_returns_a_page(game_db) -> None:
    insert_page(game_db, "Absolutism", "https://wiki/Absolutism")
    page = search.random_page("test")
    assert page is not None
    assert page["title"] == "Absolutism"


def test_random_page_empty_database_returns_none(game_db) -> None:
    assert search.random_page("test") is None


def test_random_page_picks_among_all_rows(game_db) -> None:
    for i in range(20):
        insert_page(game_db, f"Page {i}", f"https://wiki/Page_{i}")
    seen = {search.random_page("test")["title"] for _ in range(30)}
    # Overwhelmingly unlikely to land on the same one of 20 pages 30 times running.
    assert len(seen) > 1
