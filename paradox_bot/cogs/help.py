"""The -help command: list every registered game command."""

from __future__ import annotations

import discord
from discord.ext import commands

from paradox_bot.config import settings
from paradox_bot.games import GAMES


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="help", help="Показати довідку")
    async def help_command(self, ctx: commands.Context) -> None:
        """List every registered game command, derived from GAMES."""
        lines = [
            f"`{settings.bot_prefix}{key} <запит>` — {game.name}" for key, game in GAMES.items()
        ]
        lines.append(f"`{settings.bot_prefix}tools` — завантажити сейв на pdx.tools")
        lines.append(f"`{settings.bot_prefix}random <гра>` — випадкова стаття")
        lines.append(f"`{settings.bot_prefix}trending <гра>` — топ запитів за тиждень")
        embed = discord.Embed(
            title="Paradox Wiki Bot — Довідка",
            description="Команди:\n" + "\n".join(lines),
            color=0x8F1B1B,
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))
