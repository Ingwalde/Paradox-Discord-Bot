"""Keep-alive HTTP endpoint so the host does not idle the bot out."""

from __future__ import annotations

import logging
from threading import Thread

from flask import Flask

from paradox_bot.config import settings

logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/")
@app.route("/health")
def home() -> tuple[str, int]:
    logger.debug("Keep-alive ping received")
    return "I'm alive!", 200


def keep_alive() -> None:
    """Serve the keep-alive endpoint in a background thread."""
    thread = Thread(
        target=lambda: app.run(host="0.0.0.0", port=settings.server_port), daemon=True
    )
    thread.start()
