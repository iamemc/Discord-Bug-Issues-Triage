"""Feed a report through the cascade and print the verdict - no Discord or
GitLab needed. Useful for sanity-checking thresholds and the file index
before wiring up the live bot.

Usage: python scripts/dry_run.py "Player falls through the floor near the docks"
Run from the project root (so the 'src' package resolves).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config
from src.vector_store import Store
from src.triage import Triage


def main():
    text = " ".join(sys.argv[1:]) or input("Paste a bug report: ")
    cfg = load_config()
    store = Store(cfg.paths.chroma_dir)
    result = Triage(cfg, store).run(text)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
