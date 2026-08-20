# Changelog

All notable changes to this project will be documented in this file.

---

## [Unreleased]

### Fixed
- Commands now resolve regardless of case. `-EU4` raised `CommandNotFound`,
  which the handler swallows by design, so anything but lowercase looked like
  a dead bot.
- Rate limiting actually exists. `on_command_error` had a `CommandOnCooldown`
  branch but no command carried a cooldown, so the branch was unreachable and
  one user could stream 25 MB uploads back to back. Per-game commands,
  `-random` and `-trending` allow 4 uses / 10 s; `-tools` allows 1 / 60 s and
  carries `max_concurrency` so a single user cannot hold several `wait_for`
  sessions open at once.
- Result links can no longer overflow Discord's 1024-character embed field
  and fail the message with 400. Unreachable with today's data (the worst
  real query renders 737 characters) but the theoretical worst case is 1131
  for stl and 1076 for hoi4.

### Removed
- `scripts/add_search_indexes.py`. Its expression indexes were never used:
  the search filters with `LIKE '%query%'`, whose leading wildcard no B-tree
  can serve. Query plans with and without them are identical (`SCAN Pages`),
  timings match, and they added ~217 KB to `eu4.db`. See ROADMAP.md for the
  stored-column approach that would make indexing work.
- `write_pid()` and the `WIKI.pid` file it wrote. Nothing read it — a leftover
  from the earlier Replit setup.
- `IMPLEMENTATION_PROMPT.md`, superseded by this changelog and ROADMAP.md.

### Changed
- `.replit` no longer lists a `replit.nix` that does not exist; the `modules`
  field replaces it. Documented that this bot needs a Reserved VM deployment,
  since an Autoscale deployment scales to zero and a gateway bot never
  receives the HTTP request that would wake it.

## [0.1.0] - 2026-08-19

### Added
- `paradox_bot/` package: the bot split out of one `main.py` into
  `config.py` (typed `Settings` dataclass), `games.py` (`GameInfo` registry,
  single source of truth for game key → wiki subdomain, replacing two
  drifting dicts), `search.py`, `pdx_tools.py`, `feedback.py`, `stats.py`,
  `bot.py`, `web.py`, and `cogs/` (`tools`, `help`, `admin`, `extras`).
  `main.py` is now a thin entrypoint.
- `Redirects` table is searched alongside `Pages` (was collected but never
  read). Results ranked exact → prefix → contains, ties broken by title
  length.
- Fuzzy "did you mean" suggestions (`difflib`) when a search finds nothing.
- Result pagination: ◀/▶ buttons once a search has more than one page of
  results (was hard-capped at 7 with no way to see the rest).
- `-random <гра>`, `-trending <гра>`.
- ✅/❌ reactions on search results now persist votes (`Feedback` table) and
  are queryable — previously added but with no handler at all.
- `/admin status`, `/admin feedback` — Discord-native admin-gated
  (`default_permissions(administrator=True)`) slash commands. First use of
  `app_commands` in the project; regular commands stay prefix-based
  (`message_content` intent kept on purpose — see Known limitations).
- Optional daily "fact of the day" auto-post (`DAILY_FACT_CHANNEL_ID`,
  `discord.ext.tasks`, 12:00 UTC).
- Europa Universalis 5 support, plus `scripts/import_wiki.py`: populates a
  game's database from the paradoxwikis.com MediaWiki Action API (no key
  needed). Reusable for any future game in `GAMES`.
- Test suite (65 tests, pytest) covering every pure function; `-tools`
  upload tested against a real local `aiohttp` server (auth, headers, byte-
  for-byte body). GitHub Actions CI runs ruff + mypy + pytest.
- mypy (gradual/pragmatic config) and pre-commit (ruff, mypy,
  `detect-private-key`, `check-added-large-files` — the class of mistake
  that put a 12 MB save file in git once already, see 0.0.2).
- `LICENSE` (MIT) — the project had none before.

### Fixed
- pdx.tools upload: save URL was missing the `/eu4/` game segment
  (`/saves/{id}` → `/eu4/saves/{id}`, confirmed against
  `https://pdx.tools/docs/api/` — the docs only document EU4), and
  `Content-Type` was always `application/octet-stream` instead of
  `application/zip` for zip payloads.
- Duplicate `-tools` uploads ("save already exists") now resolve to the
  previously-recorded link instead of surfacing pdx.tools' raw JSON error.

### Changed
- Search result field no longer repeats the top result a second time (it's
  already the embed title); footer shows the result count.

## [0.0.2] - date not recorded

### Fixed
- Command argument injection: the game key was accepted from chat and could
  reach the database file path. Now bound by closure in
  `register_game_commands()`, never user input.

### Added
- Real pdx.tools upload (previously a fabricated URL).
- Repo hygiene: removed a 12 MB save file, `pdx_tools.db`, and `WIKI.pid`
  from git; added `.env.example` and this project's first README.

## [0.0.1] - date not recorded

Initial working version: SQLite-backed wiki search, one command per game.

[0.1.0]: https://github.com/Ingwalde/Paradox-Discord-Bot/compare/v0.0.2...v0.1.0
[0.0.2]: https://github.com/Ingwalde/Paradox-Discord-Bot/compare/v0.0.1...v0.0.2
