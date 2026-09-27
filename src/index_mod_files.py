"""(Re)indexes the mod's static file tree into the mod_files collection.

Run this once at setup, then again any time files are added or changed -
unchanged files are skipped automatically via a content hash cache, so it's
cheap to re-run on a schedule or after every content update.

Usage: python -m src.index_mod_files
"""
import hashlib
import json
from pathlib import Path

from .config import load_config
from .ollama_client import get_client, embed
from .vector_store import Store

HASH_CACHE = Path("data/file_hashes.json")

# Skip obviously irrelevant files - adjust to your mod's file types.
SKIP_SUFFIXES = {".png", ".jpg", ".dds", ".bin", ".exe", ".dll"}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(path: Path, max_chars: int = 800) -> str:
    """Cheap heuristic summary: filename + a chunk of content.

    Swap the body of this function for a tier1 model call (ollama_client.summarize)
    if you want richer, more semantic per-file summaries - the static-file
    assumption means you only pay that cost once per file, ever.
    """
    text = path.read_text(errors="ignore")[:max_chars]
    return f"{path.name}\n{text}"


def main():
    cfg = load_config()
    client = get_client(cfg.ollama.host)
    store = Store(cfg.paths.chroma_dir)

    cache = json.loads(HASH_CACHE.read_text()) if HASH_CACHE.exists() else {}

    root = Path(cfg.paths.mod_files_root)
    if not root.exists():
        print(f"'{root}' doesn't exist - create it and drop your mod files in, or fix paths.mod_files_root")
        return

    changed = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() in SKIP_SUFFIXES:
            continue

        rel = str(path.relative_to(root))
        h = file_hash(path)
        if cache.get(rel) == h:
            continue  # unchanged since last run - skip re-embedding

        summary = summarize(path)
        emb = embed(client, cfg.models.embed, summary)
        store.upsert_file(id=rel, embedding=emb, summary=summary, path=rel)
        cache[rel] = h
        changed += 1

    HASH_CACHE.parent.mkdir(parents=True, exist_ok=True)
    HASH_CACHE.write_text(json.dumps(cache, indent=2))
    print(f"Indexed {changed} new/changed file(s). {len(cache)} total tracked.")


if __name__ == "__main__":
    main()
