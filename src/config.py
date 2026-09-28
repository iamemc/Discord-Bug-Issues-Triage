"""Loads config.yaml + .env into one namespace. This is the only place
that reads environment variables or the yaml file - everything else
receives a config object, so nothing downstream hardcodes a value.
"""
import os
from types import SimpleNamespace

import yaml
from dotenv import load_dotenv

def load_config(path: str = "config.yaml") -> SimpleNamespace:
    load_dotenv()

    with open(path) as f:
        raw = yaml.safe_load(f)

    raw.setdefault("discord", {})["token"] = os.environ.get("DISCORD_BOT_TOKEN", "")
    raw.setdefault("gitlab", {})
    raw["gitlab"]["url"] = os.environ.get("GITLAB_URL", raw["gitlab"].get("url", "https://gitlab.com"))
    raw["gitlab"]["token"] = os.environ.get("GITLAB_TOKEN", "")
    raw["gitlab"]["webhook_secret"] = os.environ.get("GITLAB_WEBHOOK_SECRET", "")

    return (raw)

if __name__ == "__main__":
    config = load_config("../config.yaml")
    print("Config loaded successfully:", config)