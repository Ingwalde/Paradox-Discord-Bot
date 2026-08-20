"""Registry of supported games: Discord command key, styling, and wiki subdomain.

Single source of truth -- both paradox_bot.search (via db_path) and
scripts/import_wiki.py (via wiki_subdomain) read from GAMES, so a new game
only needs one entry here instead of two dicts drifting apart.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GameInfo:
    key: str
    name: str
    color: int
    logo: str
    wiki_subdomain: str


GAMES: dict[str, GameInfo] = {
    "eu4": GameInfo(
        key="eu4",
        name="Europa Universalis 4",
        color=0x1F2B5D,
        logo="https://eu4.paradoxwikis.com/images/wiki.PNG",
        wiki_subdomain="eu4",
    ),
    "eu5": GameInfo(
        key="eu5",
        name="Europa Universalis 5",
        color=0x2B4570,
        logo="https://eu5.paradoxwikis.com/images/wiki.PNG",
        wiki_subdomain="eu5",
    ),
    "hoi4": GameInfo(
        key="hoi4",
        name="Hearts of Iron 4",
        color=0x1E321E,
        logo="https://hoi4.paradoxwikis.com/images/wiki.PNG?wordmark",
        wiki_subdomain="hoi4",
    ),
    "stl": GameInfo(
        key="stl",
        name="Stellaris",
        color=0x6A4791,
        logo="https://stellaris.paradoxwikis.com/images/wiki.PNG",
        wiki_subdomain="stellaris",
    ),
    "imp": GameInfo(
        key="imp",
        name="Imperator",
        color=0x660947,
        logo="https://imperator.paradoxwikis.com/images/wiki.PNG?wordmark",
        wiki_subdomain="imperator",
    ),
    "vic3": GameInfo(
        key="vic3",
        name="Victoria 3",
        color=0x321A24,
        logo="https://vic3.paradoxwikis.com/images/wiki.PNG?wordmark",
        wiki_subdomain="vic3",
    ),
    "ck3": GameInfo(
        key="ck3",
        name="Crusader Kings 3",
        color=0x780A02,
        logo="https://ck3.paradoxwikis.com/images/wiki.PNG?wordmark",
        wiki_subdomain="ck3",
    ),
}
