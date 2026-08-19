"""Entrypoint: wires up the bot and keep-alive server, then runs them.

Users run `-eu4 <query>` (and the same for the other games) and get an embed
with the best matching wiki pages. Save files can be pushed to pdx.tools via
`-tools`. Admins get `/admin status` and `/admin feedback`. See paradox_bot/
for the actual implementation.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from paradox_bot.bot import ParadoxBot
from paradox_bot.config import settings
from paradox_bot.web import keep_alive

logger = logging.getLogger(__name__)


def write_pid(filename: str = "WIKI.pid") -> None:
    Path(filename).write_text(str(os.getpid()), encoding="utf-8")


def main() -> None:
    if not settings.token:
        logger.critical("TOKEN is not set; copy .env.example to .env and fill it in")
        raise SystemExit(1)

    write_pid()
    keep_alive()
    bot = ParadoxBot()
    bot.run(settings.token, log_handler=None)


if __name__ == "__main__":
    main()
