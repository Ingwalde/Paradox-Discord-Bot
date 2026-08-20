"""The ParadoxBot class: intents, dynamic per-game commands, and event handlers."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from collections.abc import Awaitable, Callable, Iterable
from datetime import UTC, datetime
from typing import Any

import discord
from discord import ui
from discord.ext import commands

from paradox_bot import stats
from paradox_bot.config import settings
from paradox_bot.feedback import (
    FEEDBACK_EMOJIS,
    _pluralize_results,
    _remember_search_context,
    _search_context,
    record_feedback,
)
from paradox_bot.games import GAMES, GameInfo
from paradox_bot.search import search_pages_async, suggest_similar_async

logger = logging.getLogger(__name__)


def build_links_field(pages: Iterable[dict[str, Any]]) -> str:
    """Render result links, dropping any that would overflow the field limit.

    Long mod subpage titles can push a full page of results past Discord's
    1024-character field cap, which would fail the whole message with 400.
    """
    lines: list[str] = []
    used = 0
    for page in pages:
        line = f"[{page['title']}]({page['url']})"
        cost = len(line) + (1 if lines else 0)  # the newline that joins it
        if used + cost > settings.embed_field_limit:
            break
        lines.append(line)
        used += cost
    return "\n".join(lines)


class LinksView(ui.View):
    """Row of link buttons for a short, non-paginated list (fuzzy suggestions)."""

    def __init__(self, pages: Iterable[dict[str, Any]]) -> None:
        super().__init__(timeout=None)
        for page in list(pages)[: settings.max_buttons]:
            # Discord rejects button labels longer than 80 characters.
            self.add_item(ui.Button(label=page["title"][:80], url=page["url"]))


class _NavButton(ui.Button):
    """A ◀/▶ button whose click runs the given async callback.

    Overriding callback() as a real method, rather than assigning a function
    to button.callback after construction, is what mypy can actually verify
    against discord.py's Item.callback signature.
    """

    def __init__(
        self,
        *,
        label: str,
        disabled: bool,
        on_click: Callable[[discord.Interaction], Awaitable[None]],
    ) -> None:
        super().__init__(label=label, style=discord.ButtonStyle.secondary, disabled=disabled)
        self._on_click = on_click

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._on_click(interaction)


class PaginatedResultsView(ui.View):
    """Search results: direct link buttons for the current page, plus ◀/▶
    navigation once there's more than one page (fetched up to
    settings.search_max_results, settings.search_result_limit per page).
    """

    def __init__(self, pages: list[dict[str, Any]], game: GameInfo) -> None:
        super().__init__(timeout=300)
        self.pages = pages
        self.game = game
        self.page_size = settings.search_result_limit
        self.index = 0
        self._render()

    @property
    def total_pages(self) -> int:
        return (len(self.pages) - 1) // self.page_size + 1

    def _current_slice(self) -> list[dict[str, Any]]:
        start = self.index * self.page_size
        return self.pages[start : start + self.page_size]

    def _render(self) -> None:
        self.clear_items()
        for page in self._current_slice()[: settings.max_buttons]:
            self.add_item(ui.Button(label=page["title"][:80], url=page["url"]))
        if self.total_pages > 1:
            self.add_item(
                _NavButton(label="◀", disabled=self.index == 0, on_click=self._go_prev)
            )
            self.add_item(
                _NavButton(
                    label="▶",
                    disabled=self.index >= self.total_pages - 1,
                    on_click=self._go_next,
                )
            )

    def build_embed(self) -> discord.Embed:
        chunk = self._current_slice()
        embed = discord.Embed(title=chunk[0]["title"], url=chunk[0]["url"], color=self.game.color)
        embed.set_thumbnail(url=self.game.logo)
        if chunk[0].get("image_url"):
            embed.set_image(url=chunk[0]["image_url"])
        # The top result of the page is already the embed title/link; listing
        # it again here would be the third copy of the same link.
        rest = chunk[1:]
        if rest:
            links_text = build_links_field(rest)
            if links_text:
                embed.add_field(name="🔗 Ще результати", value=links_text, inline=False)
        page_note = (
            f" · стор. {self.index + 1}/{self.total_pages}" if self.total_pages > 1 else ""
        )
        embed.set_footer(
            text=f"{self.game.name} Wiki · {len(self.pages)} "
            f"{_pluralize_results(len(self.pages))}{page_note}"
        )
        return embed

    async def _go_prev(self, interaction: discord.Interaction) -> None:
        self.index = max(0, self.index - 1)
        self._render()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _go_next(self, interaction: discord.Interaction) -> None:
        self.index = min(self.total_pages - 1, self.index + 1)
        self._render()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


class ParadoxBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix=settings.bot_prefix,
            intents=intents,
            help_command=None,
            # Without this, -EU4 raises CommandNotFound and is swallowed
            # silently, so anything but lowercase looks like a dead bot.
            case_insensitive=True,
        )
        self.started_at = datetime.now(UTC)
        self._register_game_commands()

    def _register_game_commands(self) -> None:
        """Register one prefix command per game.

        Data-driven (one entry per GAMES key), so it stays a plain loop
        instead of a Cog: forcing a dynamic command set into a Cog's
        decorator-based style would add friction for no benefit.

        The game key is bound by the enclosing function scope, not by a
        default argument -- a default would make it an optional positional
        the user could override from chat, which previously let arbitrary
        text reach db_path().
        """
        for key, game in GAMES.items():

            def make_command(game_key: str):
                @commands.cooldown(
                    settings.search_cooldown_uses,
                    settings.search_cooldown_seconds,
                    commands.BucketType.user,
                )
                async def game_command(ctx: commands.Context, *, query: str) -> None:
                    await send_wiki_embed(self, ctx, game_key, query)

                return game_command

            self.command(name=key, help=f"Пошук у вікі {game.name}")(make_command(key))

    async def setup_hook(self) -> None:
        from paradox_bot.cogs.admin import AdminGroup
        from paradox_bot.cogs.extras import ExtrasCog
        from paradox_bot.cogs.help import HelpCog
        from paradox_bot.cogs.tools import ToolsCog

        await self.add_cog(ToolsCog(self))
        await self.add_cog(HelpCog(self))
        await self.add_cog(ExtrasCog(self))
        self.tree.add_command(AdminGroup(self))

        if settings.dev_guild_id:
            guild = discord.Object(id=settings.dev_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Synced admin commands to dev guild %s", settings.dev_guild_id)
        else:
            await self.tree.sync()
            logger.info("Synced admin commands globally (can take up to an hour to appear)")

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Turn framework errors into user-facing messages instead of stderr noise."""
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❓ Вкажіть запит: `{settings.bot_prefix}{ctx.invoked_with} <запит>`")
            return
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Зачекайте {error.retry_after:.0f} с перед наступним запитом.")
            return
        if isinstance(error, commands.MaxConcurrencyReached):
            await ctx.send("⏳ Попереднє завантаження ще триває. Завершіть його спершу.")
            return

        original = getattr(error, "original", error)
        logger.error("Command %s failed", ctx.command, exc_info=original)
        await ctx.send("⚠️ Сталася помилка під час виконання команди.")

    async def on_ready(self) -> None:
        logger.info("Logged in as %s", self.user)

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Record ✅/❌ feedback on a search-result message.

        Uses the raw event, not on_reaction_add, so feedback still registers
        on messages the message cache has evicted.
        """
        if self.user is not None and payload.user_id == self.user.id:
            return
        vote = FEEDBACK_EMOJIS.get(str(payload.emoji))
        if vote is None:
            return
        context = _search_context.get(payload.message_id)
        if context is None:
            return

        logger.info(
            "feedback vote=%s user=%s game=%s query=%r top_title=%r top_url=%r",
            vote,
            payload.user_id,
            context["game_key"],
            context["query"],
            context["top_title"],
            context["top_url"],
        )
        try:
            await asyncio.to_thread(
                record_feedback,
                str(payload.user_id),
                context["game_key"],
                context["query"],
                vote,
                context["top_title"],
                context["top_url"],
            )
        except sqlite3.Error:
            logger.exception("Could not record feedback for message %s", payload.message_id)


async def send_wiki_embed(
    bot: commands.Bot, ctx: commands.Context, game_key: str, query: str
) -> None:
    """Search one game's wiki and reply with an embed plus link buttons."""
    game = GAMES[game_key]

    if len(query) > settings.max_query_length:
        await ctx.send(f"❌ Запит задовгий (максимум {settings.max_query_length} символів).")
        return

    try:
        pages = await search_pages_async(game_key, query, limit=settings.search_max_results)
    except sqlite3.Error:
        logger.exception("Database search failed for %s: %r", game_key, query)
        await ctx.send("⚠️ Не вдалося виконати пошук. Спробуйте пізніше.")
        return

    try:
        await asyncio.to_thread(stats.record_search, game_key, query)
    except sqlite3.Error:
        logger.exception("Could not record search stats for %s: %r", game_key, query)

    view: ui.View | None = None
    if pages:
        results_view = PaginatedResultsView(pages, game)
        embed = results_view.build_embed()
        view = results_view
    else:
        embed = discord.Embed(
            title=f"За запитом '{query}' нічого не знайдено",
            description="Спробуйте інший запит або перевірте написання.",
            color=game.color,
        )
        if game.logo:
            embed.set_thumbnail(url=game.logo)
        try:
            suggestions = await suggest_similar_async(game_key, query)
        except sqlite3.Error:
            logger.exception("Fuzzy suggestion lookup failed for %s: %r", game_key, query)
            suggestions = []
        if suggestions:
            links_text = build_links_field(suggestions)
            if links_text:
                embed.add_field(
                    name="🔎 Можливо ви мали на увазі", value=links_text, inline=False
                )
            view = LinksView(suggestions)
        embed.set_footer(text=f"{game.name} Wiki")

    msg = await ctx.send(embed=embed, view=view) if view else await ctx.send(embed=embed)
    _remember_search_context(
        msg.id,
        game_key=game_key,
        query=query,
        top_title=pages[0]["title"] if pages else None,
        top_url=pages[0]["url"] if pages else None,
    )
    for emoji in FEEDBACK_EMOJIS:
        try:
            await msg.add_reaction(emoji)
        except discord.HTTPException:
            logger.warning("Could not add reaction %s", emoji, exc_info=True)

    await log_request(
        bot=bot,
        ctx=ctx,
        game_key=game_key,
        query=query,
        found=bool(pages),
        result_count=len(pages),
        has_image=bool(pages and pages[0].get("image_url")),
    )


async def log_request(
    bot: commands.Bot,
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
    if settings.log_channel_id is None:
        return

    channel = bot.get_channel(settings.log_channel_id)
    if channel is None:
        logger.warning("Log channel %s not found or not cached", settings.log_channel_id)
        return
    if not isinstance(channel, discord.abc.Messageable):
        logger.error(
            "LOG_CHANNEL_ID %s is a %s, which can't receive messages",
            settings.log_channel_id,
            type(channel).__name__,
        )
        return

    game = GAMES[game_key]
    embed = discord.Embed(title="📄 Paradox Wiki Запит", color=game.color)
    embed.add_field(name="**User**", value=f"<@{ctx.author.id}>", inline=False)
    embed.add_field(
        name="**Request**", value=f"`{settings.bot_prefix}{game_key} {query}`", inline=False
    )
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
        logger.exception("Failed to write to log channel %s", settings.log_channel_id)
