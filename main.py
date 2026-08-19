"""Discord bot that searches Ukrainian Paradox game wikis.

Users run `-eu4 <query>` (and the same for the other five games) and get an
embed with the best matching wiki pages. Save files can be pushed to pdx.tools
via `-tools`.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import os
import sqlite3
import sys
from collections.abc import Iterable
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Thread
from typing import Any

import aiohttp
import discord
from discord import ui
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask

load_dotenv()

# --- Logging -----------------------------------------------------------------

LOG_DIR = Path("logs")


def setup_logging() -> logging.Logger:
    """Configure console (INFO) and rotating file (DEBUG) handlers."""
    LOG_DIR.mkdir(exist_ok=True)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s:%(funcName)s:%(lineno)d %(message)s"
    )

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)

    logfile = RotatingFileHandler(
        LOG_DIR / "bot.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    logfile.setLevel(logging.DEBUG)
    logfile.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    root.addHandler(console)
    root.addHandler(logfile)
    return logging.getLogger("paradox-bot")


logger = setup_logging()

# --- Configuration -----------------------------------------------------------

DB_DIR = Path(os.getenv("DB_DIR", "databases"))
BOT_PREFIX = os.getenv("BOT_PREFIX", "-")
SERVER_PORT = int(os.getenv("PORT", "8080"))
SEARCH_RESULT_LIMIT = 7
MAX_BUTTONS = 5
MAX_QUERY_LENGTH = 100
DB_TIMEOUT_SECONDS = 5.0

UPLOAD_DB_PATH = Path("pdx_tools.db")
UPLOAD_WAIT_SECONDS = 60.0
MAX_SAVE_BYTES = 25 * 1024 * 1024
ZIP_MAGIC = b"PK\x03\x04"

PDX_TOOLS_USER_ID = os.getenv("PDX_TOOLS_USER_ID", "").strip()
PDX_TOOLS_API_KEY = os.getenv("PDX_TOOLS_API_KEY", "").strip()
PDX_TOOLS_API_URL = os.getenv("PDX_TOOLS_API_URL", "https://pdx.tools/api/saves").strip()
# Kept in the environment because the public docs could not be reached to confirm
# the exact shape; change it there rather than in code if pdx.tools moves it.
PDX_TOOLS_SAVE_URL = os.getenv("PDX_TOOLS_SAVE_URL", "https://pdx.tools/saves/{save_id}").strip()
PDX_TOOLS_TIMEOUT_SECONDS = 300


def _parse_log_channel_id() -> int | None:
    """Read LOG_CHANNEL_ID once at startup instead of on every request."""
    raw = os.getenv("LOG_CHANNEL_ID", "").strip()
    if not raw:
        logger.warning("LOG_CHANNEL_ID is not set; search requests will not be mirrored")
        return None
    try:
        return int(raw)
    except ValueError:
        logger.error("LOG_CHANNEL_ID=%r is not a valid integer; logging disabled", raw)
        return None


LOG_CHANNEL_ID = _parse_log_channel_id()

GAME_STYLES: dict[str, dict[str, Any]] = {
    "eu4": {
        "name": "Europa Universalis 4",
        "color": 0x1F2B5D,
        "logo": "https://eu4.paradoxwikis.com/images/wiki.PNG",
    },
    "hoi4": {
        "name": "Hearts of Iron 4",
        "color": 0x1E321E,
        "logo": "https://hoi4.paradoxwikis.com/images/wiki.PNG?wordmark",
    },
    "stl": {
        "name": "Stellaris",
        "color": 0x6A4791,
        "logo": "https://stellaris.paradoxwikis.com/images/wiki.PNG",
    },
    "imp": {
        "name": "Imperator",
        "color": 0x660947,
        "logo": "https://imperator.paradoxwikis.com/images/wiki.PNG?wordmark",
    },
    "vic3": {
        "name": "Victoria 3",
        "color": 0x321A24,
        "logo": "https://vic3.paradoxwikis.com/images/wiki.PNG?wordmark",
    },
    "ck3": {
        "name": "Crusader Kings 3",
        "color": 0x780A02,
        "logo": "https://ck3.paradoxwikis.com/images/wiki.PNG?wordmark",
    },
}

# --- Search ------------------------------------------------------------------


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
            ever pass keys from GAME_STYLES, so this is a defensive assertion
            that no user input can reach the filesystem.
    """
    if game_key not in GAME_STYLES:
        raise KeyError(game_key)
    return DB_DIR / f"{game_key}.db"


def search_pages(game_key: str, query: str, limit: int = SEARCH_RESULT_LIMIT) -> list[dict[str, Any]]:
    """Find wiki pages matching a query, exact title first then substrings.

    Args:
        game_key: One of the keys in GAME_STYLES.
        query: Raw user query.
        limit: Maximum number of results.

    Returns:
        Page dicts with title, url and image_url keys.

    Raises:
        sqlite3.Error: If the game database is missing or unreadable.
    """
    normalized = normalize(query)
    if not normalized:
        return []

    pattern = f"%{escape_like(normalized)}%"
    path = db_path(game_key)
    # mode=ro means a missing database raises instead of being created silently.
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=DB_TIMEOUT_SECONDS)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        results: list[dict[str, Any]] = []

        cursor.execute(
            """
            SELECT title, url, image_url FROM Pages
            WHERE LOWER(REPLACE(title, '_', ' ')) = ?
            LIMIT 1
            """,
            (normalized,),
        )
        exact = cursor.fetchone()
        if exact:
            results.append(dict(exact))

        if len(results) < limit:
            cursor.execute(
                """
                SELECT title, url, image_url FROM Pages
                WHERE LOWER(REPLACE(title, '_', ' ')) LIKE ? ESCAPE '\\'
                ORDER BY title
                LIMIT ?
                """,
                (pattern, limit),
            )
            seen = {row["title"] for row in results}
            for row in cursor.fetchall():
                if row["title"] in seen:
                    continue
                results.append(dict(row))
                seen.add(row["title"])
                if len(results) >= limit:
                    break

        return results[:limit]
    finally:
        conn.close()


async def search_pages_async(
    game_key: str, query: str, limit: int = SEARCH_RESULT_LIMIT
) -> list[dict[str, Any]]:
    """Run search_pages off the event loop; sqlite3 is blocking."""
    return await asyncio.to_thread(search_pages, game_key, query, limit)


# --- Discord presentation ----------------------------------------------------


class LinksView(ui.View):
    """Row of link buttons for the top results."""

    def __init__(self, pages: Iterable[dict[str, Any]]) -> None:
        super().__init__(timeout=None)
        for page in list(pages)[:MAX_BUTTONS]:
            # Discord rejects button labels longer than 80 characters.
            self.add_item(ui.Button(label=page["title"][:80], url=page["url"]))


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents, help_command=None)


async def send_wiki_embed(ctx: commands.Context, game_key: str, query: str) -> None:
    """Search one game's wiki and reply with an embed plus link buttons."""
    game = GAME_STYLES[game_key]

    if len(query) > MAX_QUERY_LENGTH:
        await ctx.send(f"❌ Запит задовгий (максимум {MAX_QUERY_LENGTH} символів).")
        return

    try:
        pages = await search_pages_async(game_key, query)
    except sqlite3.Error:
        logger.exception("Database search failed for %s: %r", game_key, query)
        await ctx.send("⚠️ Не вдалося виконати пошук. Спробуйте пізніше.")
        return

    view: ui.View | None = None
    if pages:
        embed = discord.Embed(
            title=pages[0]["title"], url=pages[0]["url"], color=game["color"]
        )
        embed.set_thumbnail(url=game["logo"])
        if pages[0].get("image_url"):
            embed.set_image(url=pages[0]["image_url"])
        links_text = "\n".join(f"[{p['title']}]({p['url']})" for p in pages)
        embed.add_field(name="🔗 Посилання", value=links_text, inline=False)
        view = LinksView(pages)
    else:
        embed = discord.Embed(
            title=f"За запитом '{query}' нічого не знайдено",
            description="Спробуйте інший запит або перевірте написання.",
            color=game["color"],
        )
        if game["logo"]:
            embed.set_thumbnail(url=game["logo"])
    embed.set_footer(text=f"{game['name']} Wiki")

    msg = await ctx.send(embed=embed, view=view) if view else await ctx.send(embed=embed)
    for emoji in ("✅", "❌"):
        try:
            await msg.add_reaction(emoji)
        except discord.HTTPException:
            logger.warning("Could not add reaction %s", emoji, exc_info=True)

    await log_request(
        ctx=ctx,
        game_key=game_key,
        query=query,
        found=bool(pages),
        result_count=len(pages),
        has_image=bool(pages and pages[0].get("image_url")),
    )


async def log_request(
    ctx: commands.Context,
    game_key: str,
    query: str,
    found: bool,
    result_count: int,
    has_image: bool,
) -> None:
    """Mirror a search request into the log channel. Never fails the command."""
    logger.info(
        "search game=%s user=%s query=%r results=%d", game_key, ctx.author.id, query, result_count
    )
    if LOG_CHANNEL_ID is None:
        return

    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel is None:
        logger.warning("Log channel %s not found or not cached", LOG_CHANNEL_ID)
        return

    game = GAME_STYLES[game_key]
    embed = discord.Embed(title="📄 Paradox Wiki Запит", color=game["color"])
    embed.add_field(name="**User**", value=f"<@{ctx.author.id}>", inline=False)
    embed.add_field(name="**Request**", value=f"`{BOT_PREFIX}{game_key} {query}`", inline=False)
    embed.add_field(
        name="**Result**",
        value=(
            f"Знайдено: {'так' if found else 'ні'}\n"
            f"Кількість результатів: {result_count}\n"
            f"Картинка: {'так' if has_image else 'ні'}"
        ),
        inline=False,
    )
    try:
        await channel.send(embed=embed)
    except discord.DiscordException:
        logger.exception("Failed to write to log channel %s", LOG_CHANNEL_ID)


def register_game_commands() -> None:
    """Register one command per game.

    The game key is bound by the enclosing function scope, not by a default
    argument -- a default would make it an optional positional the user could
    override from chat, which previously let arbitrary text reach db_path().
    """
    for key, style in GAME_STYLES.items():

        def make_command(game_key: str):
            async def game_command(ctx: commands.Context, *, query: str) -> None:
                await send_wiki_embed(ctx, game_key, query)

            return game_command

        bot.command(name=key, help=f"Пошук у вікі {style['name']}")(make_command(key))


register_game_commands()


# --- pdx.tools upload --------------------------------------------------------


class PdxToolsError(Exception):
    """Raised when pdx.tools rejects an upload or replies unexpectedly."""


def prepare_save_payload(raw: bytes) -> bytes:
    """Return the save in a form pdx.tools accepts.

    Zip saves go up untouched; anything else must be gzip-compatible.
    """
    if raw.startswith(ZIP_MAGIC):
        return raw
    return gzip.compress(raw)


def _extract_save_url(status: int, body: str) -> str:
    """Turn the API response into a user-facing URL.

    Raises:
        PdxToolsError: If the response carries no recognisable save id.
    """
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise PdxToolsError(f"HTTP {status}, відповідь не JSON: {body[:200]}") from exc

    if not isinstance(payload, dict):
        raise PdxToolsError(f"HTTP {status}, несподівана відповідь: {body[:200]}")

    for field in ("save_id", "saveId", "id"):
        save_id = payload.get(field)
        if save_id:
            return PDX_TOOLS_SAVE_URL.format(save_id=save_id)

    raise PdxToolsError(f"HTTP {status}, немає ідентифікатора збереження: {body[:200]}")


async def upload_to_pdx_tools(filename: str, payload: bytes) -> str:
    """POST a save to pdx.tools and return its URL.

    The API takes the raw bytes as the body (multipart is not supported), the
    filename in a `pdx-tools-filename` header, and basic auth credentials.

    Raises:
        PdxToolsError: On any non-success response or unreadable payload.
    """
    auth = aiohttp.BasicAuth(PDX_TOOLS_USER_ID, PDX_TOOLS_API_KEY)
    timeout = aiohttp.ClientTimeout(total=PDX_TOOLS_TIMEOUT_SECONDS)
    headers = {
        "pdx-tools-filename": filename,
        "Content-Type": "application/octet-stream",
    }

    try:
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.post(PDX_TOOLS_API_URL, data=payload, auth=auth, headers=headers) as response,
        ):
            body = await response.text()
            if response.status >= 400:
                raise PdxToolsError(f"HTTP {response.status}: {body[:200]}")
            return _extract_save_url(response.status, body)
    except TimeoutError as exc:
        raise PdxToolsError("час очікування відповіді pdx.tools вичерпано") from exc
    except aiohttp.ClientError as exc:
        raise PdxToolsError(f"мережева помилка: {exc}") from exc


def record_upload(user_id: str, filename: str, url: str) -> None:
    """Persist a successful upload. Blocking; call via asyncio.to_thread."""
    conn = sqlite3.connect(UPLOAD_DB_PATH, timeout=DB_TIMEOUT_SECONDS)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS Uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                filename TEXT,
                url TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "INSERT INTO Uploads (user_id, filename, url) VALUES (?, ?, ?)",
            (user_id, filename, url),
        )
        conn.commit()
    finally:
        conn.close()


@bot.command(name="tools", help="Завантажити сейв на pdx.tools")
async def tools(ctx: commands.Context) -> None:
    """Take a save file attachment and upload it to pdx.tools."""
    if not (PDX_TOOLS_USER_ID and PDX_TOOLS_API_KEY):
        await ctx.send(
            "⚠️ Завантаження на pdx.tools не налаштоване на цьому боті.\n"
            "Ви можете завантажити сейв вручну: <https://pdx.tools>"
        )
        return

    await ctx.send("📤 Завантажте свій сейв-файл для PDX Tools протягом 60 секунд.")

    def check(message: discord.Message) -> bool:
        return (
            message.author == ctx.author
            and message.channel == ctx.channel
            and bool(message.attachments)
        )

    try:
        message = await bot.wait_for("message", timeout=UPLOAD_WAIT_SECONDS, check=check)
    except TimeoutError:
        await ctx.send("⏱️ Час очікування вичерпано. Спробуйте ще раз.")
        return

    attachment = message.attachments[0]
    if attachment.size > MAX_SAVE_BYTES:
        await ctx.send(f"❌ Файл завеликий (ліміт {MAX_SAVE_BYTES // 1024 // 1024} МБ).")
        return

    await ctx.send("⏳ Завантажую на https://pdx.tools ...")
    try:
        # Read straight into memory: no temp file means no leftover saves on disk
        # and no user-controlled path touching the filesystem.
        raw = await attachment.read()
        payload = await asyncio.to_thread(prepare_save_payload, raw)
        url = await upload_to_pdx_tools(attachment.filename, payload)
    except discord.DiscordException:
        logger.exception("Could not read attachment %s", attachment.filename)
        await ctx.send("❌ Не вдалося прочитати вкладення. Спробуйте ще раз.")
        return
    except PdxToolsError as exc:
        logger.error("pdx.tools upload failed for %s: %s", attachment.filename, exc)
        await ctx.send(f"❌ pdx.tools відхилив завантаження: {exc}")
        return
    except Exception:
        logger.exception("Unexpected error uploading %s", attachment.filename)
        await ctx.send("❌ Несподівана помилка під час завантаження.")
        return

    try:
        await asyncio.to_thread(record_upload, str(ctx.author.id), attachment.filename, url)
    except sqlite3.Error:
        # The upload succeeded; a bookkeeping failure must not hide that.
        logger.exception("Could not record upload of %s", attachment.filename)

    logger.info("uploaded %s for user %s -> %s", attachment.filename, ctx.author.id, url)
    await ctx.send(f"✅ Завантажено: {url}")


# --- Help and error handling -------------------------------------------------


@bot.command(name="help", help="Показати довідку")
async def help_command(ctx: commands.Context) -> None:
    """List every registered game command, derived from GAME_STYLES."""
    lines = [
        f"`{BOT_PREFIX}{key} <запит>` — {style['name']}" for key, style in GAME_STYLES.items()
    ]
    lines.append(f"`{BOT_PREFIX}tools` — завантажити сейв на pdx.tools")
    embed = discord.Embed(
        title="Paradox Wiki Bot — Довідка",
        description="Команди:\n" + "\n".join(lines),
        color=0x8F1B1B,
    )
    await ctx.send(embed=embed)


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    """Turn framework errors into user-facing messages instead of stderr noise."""
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❓ Вкажіть запит: `{BOT_PREFIX}{ctx.invoked_with} <запит>`")
        return
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Зачекайте {error.retry_after:.0f} с перед наступним запитом.")
        return

    original = getattr(error, "original", error)
    logger.error("Command %s failed", ctx.command, exc_info=original)
    await ctx.send("⚠️ Сталася помилка під час виконання команди.")


@bot.event
async def on_ready() -> None:
    logger.info("Logged in as %s", bot.user)


# --- Keep-alive endpoint -----------------------------------------------------

app = Flask(__name__)


@app.route("/")
@app.route("/health")
def home() -> tuple[str, int]:
    logger.debug("Keep-alive ping received")
    return "I'm alive!", 200


def keep_alive() -> None:
    """Serve the keep-alive endpoint so the host does not idle the bot out."""
    thread = Thread(
        target=lambda: app.run(host="0.0.0.0", port=SERVER_PORT), daemon=True
    )
    thread.start()


def write_pid(filename: str = "WIKI.pid") -> None:
    Path(filename).write_text(str(os.getpid()), encoding="utf-8")


def main() -> None:
    token = os.getenv("TOKEN", "").strip()
    if not token:
        logger.critical("TOKEN is not set; copy .env.example to .env and fill it in")
        raise SystemExit(1)

    write_pid()
    keep_alive()
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
