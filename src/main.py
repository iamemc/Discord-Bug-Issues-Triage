"""Runs the Discord bot and the GitLab merge-webhook server together.

Usage: python -m src.main
"""
import threading

import uvicorn

from .discord_bot import run as run_discord
from .merge_webhook import app as webhook_app


def run_webhook_server():
    uvicorn.run(webhook_app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    t = threading.Thread(target=run_webhook_server, daemon=True)
    t.start()
    run_discord()
